from typing import Dict, List, Optional, Set, Tuple
from node.NodeType import (
    Program, Stmt, Expr, TypeNode, ResultType,
    GenericType, NamedType, OptionalType as AstOptionalType, ListType as AstListType, DictType as AstDictType,
    Pattern, IdentifierPattern, TuplePattern, EnumPattern, LiteralPattern, WildcardPattern,
    Block, ExprStmt, Param, FnDecl, StructDecl, EnumDecl, ImportDecl,
    InterfaceDecl, ClassDecl, ClassField, MethodDecl,
    LetDecl, WhileStmt, ForStmt, ReturnStmt, BreakStmt, ContinueStmt,
    IntLiteral, FloatLiteral, StringLiteral, BoolLiteral, NoneLiteral, IdentExpr,
    ThisExpr, SuperExpr, NewExpr,
    UnaryExpr, BinaryExpr, CoalesceExpr, RangeExpr, PostfixTryExpr, ElseErrExpr,
    CallExpr, MemberExpr, IndexExpr, AssignmentExpr, StructInitExpr,
    ListExpr, DictExpr, TupleExpr, IfExpr, MatchExpr
)
from parser.Parser import Parser
from common.Telemetry import CodegenTelemetry


class CleanupScope:
    def __init__(self, kind: str) -> None:
        self.kind = kind  # "fn" | "loop" | "block"
        self.vars: List[str] = []


class CCodeGen:
    """
    Canonical W v0.1 to C99 Transpiler Backend.
    Preserves exact value semantics (Deterministic RC + Copy-on-Write via runtime/w_runtime.h),
    reference semantics for OOP classes, dynamic dispatch, fallible error handling,
    and deterministic LIFO lifetime cleanup across all control-flow paths (v0.1.3).
    """
    def __init__(self, file: str = "<stdin>"):
        self.file = file
        self.temp_counter = 0
        self.aux_counter = 0
        self.enum_names: Set[str] = {"Option", "Result"}
        self.enum_variants: Dict[str, str] = {
            "Some": "Option",
            "None": "Option",
            "Ok": "Result",
            "Err": "Result",
        }
        self.classes: Dict[str, ClassDecl] = {}
        self.class_order: List[str] = []
        self.dispatch_methods: List[Tuple[str, int]] = []
        self.current_class: Optional[ClassDecl] = None
        self.fallible_fns: Dict[str, bool] = {}
        self.fn_err_types: Dict[str, str] = {}
        self.current_fn_fallible: bool = False
        self.current_fn_err_type: str = ""
        self.current_ns: str = ""
        self.imported_modules: Set[str] = set()
        self.global_vars: List[str] = []
        self.fn_Prototypes: List[str] = []
        self.fn_Definitions: List[str] = []
        self.scope_stack: List[CleanupScope] = []
        self.telemetry: CodegenTelemetry = CodegenTelemetry()

    def new_temp(self) -> str:
        name = f"_t{self.temp_counter}"
        self.temp_counter += 1
        return name

    def new_aux(self, prefix: str = "_aux") -> str:
        name = f"{prefix}{self.aux_counter}"
        self.aux_counter += 1
        return name

    def _push_scope(self, kind: str) -> None:
        self.scope_stack.append(CleanupScope(kind))

    def _register_var(self, var_name: str) -> None:
        if self.scope_stack:
            self.scope_stack[-1].vars.append(var_name)

    def _declare_owned_var(self, var_name: str, init_c_expr: str, out: List[str]) -> str:
        out.append(f"WVal {var_name} = {init_c_expr};")
        self._register_var(var_name)
        return var_name

    def _pop_scope(self, out: List[str]) -> None:
        if not self.scope_stack:
            return
        scope = self.scope_stack.pop()
        for v in reversed(scope.vars):
            out.append(f"w_release({v});")

    def _emit_cleanup_until_fn(self, out: List[str]) -> None:
        for scope in reversed(self.scope_stack):
            for v in reversed(scope.vars):
                out.append(f"w_release({v});")
            if scope.kind == "fn":
                break

    def _emit_cleanup_until_loop(self, out: List[str]) -> None:
        for scope in reversed(self.scope_stack):
            for v in reversed(scope.vars):
                out.append(f"w_release({v});")
            if scope.kind == "loop":
                break

    def _snapshot(self, value: str, out: List[str]) -> str:
        """Protect an evaluated value before later operands can mutate its owner."""
        if value.startswith("_t"):
            return value
        if value.startswith(("w_make_", "w_new_")):
            return self._bind_call(value, out)
        return self._bind_call(f"w_clone({value})", out)

    def emit_value(self, expr, out: List[str]) -> str:
        return self._snapshot(self.emit_expr(expr, out), out)

    def _own_expr(self, val_expr: str) -> str:
        if val_expr.startswith("_t"):
            return f"w_move(&{val_expr})"
        if val_expr.startswith("w_make_") or val_expr.startswith("w_new_") or val_expr.startswith("w_clone("):
            return val_expr
        return f"w_clone({val_expr})"

    def _is_local_var(self, c_name: str) -> bool:
        for scope in reversed(self.scope_stack):
            if c_name in scope.vars:
                return True
        return False

    def c_var(self, name: str) -> str:
        local_name = f"v_{name}"
        if self._is_local_var(local_name):
            return local_name
        if self.current_ns and f"v_{self.current_ns}_{name}" in self.global_vars:
            return f"v_{self.current_ns}_{name}"
        return local_name

    def c_fn(self, name: str, ns: str = "") -> str:
        prefix = ns if ns else self.current_ns
        if prefix:
            return f"w_fn_{prefix}__{name}"
        return f"w_fn_{name}"

    def escape_c_str(self, s: str) -> str:
        out: List[str] = ['"']
        for ch in s:
            code = ord(ch)
            if code == 34:
                out.append('\\"')
            elif code == 92:
                out.append("\\\\")
            elif code == 10:
                out.append("\\n")
            elif code == 13:
                out.append("\\r")
            elif code == 9:
                out.append("\\t")
            elif code == 0:
                out.append("\\0")
            else:
                out.append(ch)
        out.append('"')
        return "".join(out)

    def generate(self, program: Program) -> str:
        if hasattr(program, "session"):
            program = program.session.link(program)
        self.interner = getattr(program, "interner", None)
        self._collect_declarations(program, ns="")
        self._prepare_oop_prototypes()

        # Emit all top-level functions, class methods, and imported module functions
        main_stmts: List[str] = []
        self._push_scope("fn")
        self._emit_module_body(program, ns="", out_main_stmts=main_stmts)

        # If there are no top-level executable statements and main() exists in W, call it
        non_decls = [s for s in program.body if not isinstance(s, (FnDecl, StructDecl, EnumDecl, InterfaceDecl, ClassDecl, ImportDecl))]
        if getattr(program, "call_entrypoint", not non_decls) and "w_fn_main" in self.fallible_fns:
            main_stmts.append("w_release(w_fn_main());")

        self._pop_scope(main_stmts)
        self._emit_oop_dispatchers()

        lines: List[str] = [
            '#include "runtime/w_runtime.h"',
            ""
        ]

        if self.global_vars:
            for gv in self.global_vars:
                lines.append(f"static WVal {gv};")
            lines.append("")

        if self.fn_Prototypes:
            lines.extend(self.fn_Prototypes)
            lines.append("")

        if self.fn_Definitions:
            for fd in self.fn_Definitions:
                lines.append(fd)
                lines.append("")

        lines.append("int main(int argc, char** argv) {")
        lines.append("    w_init_args(argc, argv);")
        for s in main_stmts:
            lines.append(f"    {s}")
        for gv in reversed(self.global_vars):
            lines.append(f"    w_release({gv});")
        lines.append("    w_runtime_cleanup();")
        lines.append("    return 0;")
        lines.append("}")
        c_code_str = "\n".join(lines) + "\n"
        struct_count = sum(1 for s in program.body if isinstance(s, StructDecl))
        self.telemetry = CodegenTelemetry(
            generated_functions=len(self.fn_Definitions),
            generated_structs=struct_count,
            generated_enums=len(self.enum_names),
            generated_classes=len(self.classes),
            generated_c_lines=len(c_code_str.splitlines()),
            generated_c_bytes=len(c_code_str.encode("utf-8")),
        )
        return c_code_str

    def _collect_declarations(self, program: Program, ns: str) -> None:
        for stmt in program.body:
            if isinstance(stmt, EnumDecl):
                self.enum_names.add(stmt.name)
                for v in stmt.variants:
                    v_name = v.name if hasattr(v, "name") else str(v)
                    self.enum_variants[v_name] = stmt.name
            elif isinstance(stmt, ClassDecl):
                if stmt.name not in self.classes:
                    self.classes[stmt.name] = stmt
                    self.class_order.append(stmt.name)
                for m in stmt.methods:
                    if m.name != "init":
                        key = (m.name, len(m.params))
                        if key not in self.dispatch_methods:
                            self.dispatch_methods.append(key)
            elif isinstance(stmt, FnDecl):
                c_name = self.c_fn(stmt.name, ns=ns)
                is_fallible = isinstance(stmt.return_type, ResultType)
                self.fallible_fns[c_name] = is_fallible
                if is_fallible and isinstance(stmt.return_type, ResultType) and isinstance(stmt.return_type.err_type, NamedType):
                    self.fn_err_types[c_name] = stmt.return_type.err_type.name
                else:
                    self.fn_err_types[c_name] = ""
                params_sig = ", ".join([f"WVal v_{p.name}" for p in stmt.params]) if stmt.params else "void"
                self.fn_Prototypes.append(f"static WVal {c_name}({params_sig});")
            elif isinstance(stmt, LetDecl):
                gv_name = f"v_{ns}_{stmt.name}" if ns else f"v_{stmt.name}"
                if gv_name not in self.global_vars:
                    self.global_vars.append(gv_name)

    def _find_class_method(self, class_name: str, method_name: str) -> Optional[Tuple[str, MethodDecl]]:
        curr: Optional[str] = class_name
        while curr is not None and curr in self.classes:
            cdecl = self.classes[curr]
            for m in cdecl.methods:
                if m.name == method_name:
                    return (curr, m)
            curr = cdecl.superclass
        return None

    def _collect_class_fields(self, class_name: str) -> List[ClassField]:
        lineage: List[ClassDecl] = []
        curr: Optional[str] = class_name
        while curr is not None and curr in self.classes:
            lineage.append(self.classes[curr])
            curr = self.classes[curr].superclass
        lineage.reverse()
        fields: List[ClassField] = []
        seen: Set[str] = set()
        for cdecl in lineage:
            for f in cdecl.fields:
                if f.name not in seen:
                    seen.add(f.name)
                    fields.append(f)
        return fields

    def _default_c_expr_for_type(self, type_ann: TypeNode) -> str:
        if isinstance(type_ann, NamedType):
            if type_ann.name == "int":
                return "w_int(0LL)"
            if type_ann.name == "float":
                return "w_float(0.0)"
            if type_ann.name == "bool":
                return "w_bool(false)"
            if type_ann.name == "str":
                return 'w_str("")'
        elif isinstance(type_ann, GenericType) and type_ann.name == "Weak":
            return "w_empty_weak()"
        elif isinstance(type_ann, AstOptionalType):
            return "w_none()"
        elif isinstance(type_ann, AstListType):
            return "w_make_list(0, NULL)"
        elif isinstance(type_ann, AstDictType):
            return "w_make_dict(0, NULL, NULL)"
        return "w_none()"

    def _prepare_oop_prototypes(self) -> None:
        for cls_name in self.class_order:
            cdecl = self.classes[cls_name]
            for m in cdecl.methods:
                params = ["WVal v_self"] + [f"WVal v_{p.name}" for p in m.params]
                self.fn_Prototypes.append(f"static WVal w_method_{cls_name}__{m.name}({', '.join(params)});")
            init_res = self._find_class_method(cls_name, "init")
            if init_res is not None:
                _, init_m = init_res
                init_sig = ", ".join([f"WVal v_{p.name}" for p in init_m.params]) if init_m.params else "void"
            else:
                init_sig = "void"
            self.fn_Prototypes.append(f"static WVal w_new_{cls_name}({init_sig});")

        for mname, arity in self.dispatch_methods:
            params = ["WVal v_self"] + [f"WVal _a{i}" for i in range(arity)]
            self.fn_Prototypes.append(f"static WVal w_dispatch__{mname}__{arity}({', '.join(params)});")

    def _emit_class_decl(self, stmt: ClassDecl) -> None:
        prev_cls = self.current_class
        self.current_class = stmt
        try:
            for m in stmt.methods:
                c_name = f"w_method_{stmt.name}__{m.name}"
                params = ["WVal v_self"] + [f"WVal v_{p.name}" for p in m.params]
                prev_fallible = self.current_fn_fallible
                prev_err_type = self.current_fn_err_type
                self.current_fn_fallible = isinstance(m.return_type, ResultType)
                if self.current_fn_fallible and isinstance(m.return_type, ResultType) and isinstance(m.return_type.err_type, NamedType):
                    self.current_fn_err_type = m.return_type.err_type.name
                else:
                    self.current_fn_err_type = ""

                body_stmts: List[str] = []
                self._push_scope("fn")
                ret_expr = self.emit_block_value(m.body, body_stmts)
                ret_hold = self.new_aux("_ret")
                body_stmts.append(f"WVal {ret_hold} = {self._own_expr(ret_expr)};")
                self._pop_scope(body_stmts)
                if self.current_fn_fallible:
                    body_stmts.append(f'return w_wrap_result({ret_hold}, "{self.current_fn_err_type}");')
                else:
                    body_stmts.append(f"return {ret_hold};")

                fn_lines = [f"static WVal {c_name}({', '.join(params)}) {{"]
                for s in body_stmts:
                    fn_lines.append(f"    {s}")
                fn_lines.append("}")
                self.fn_Definitions.append("\n".join(fn_lines))
                self.current_fn_fallible = prev_fallible
                self.current_fn_err_type = prev_err_type

            # Emit constructor helper w_new_<ClassName>
            all_fields = self._collect_class_fields(stmt.name)
            init_res = self._find_class_method(stmt.name, "init")
            if init_res is not None:
                init_cls, init_m = init_res
                init_sig = ", ".join([f"WVal v_{p.name}" for p in init_m.params]) if init_m.params else "void"
                init_args = ["v_self"] + [f"v_{p.name}" for p in init_m.params]
            else:
                init_cls = ""
                init_m = None
                init_sig = "void"
                init_args = []

            new_lines = [f"static WVal w_new_{stmt.name}({init_sig}) {{"]
            if all_fields:
                f_names = ", ".join([f'"{f.name}"' for f in all_fields])
                f_defaults = ", ".join([self._default_c_expr_for_type(f.type_ann) for f in all_fields])
                new_lines.append(f"    const char* _k[{len(all_fields)}] = {{ {f_names} }};")
                new_lines.append(f"    WVal _v[{len(all_fields)}] = {{ {f_defaults} }};")
                new_lines.append(f'    WVal v_self = w_make_object("{stmt.name}", {len(all_fields)}, _k, _v);')
                new_lines.append(f"    w_release_array({len(all_fields)}, _v);")
            else:
                new_lines.append(f'    WVal v_self = w_make_object("{stmt.name}", 0, NULL, NULL);')
            if init_m is not None:
                new_lines.append(f"    w_release(w_method_{init_cls}__init({', '.join(init_args)}));")
            new_lines.append("    return v_self;")
            new_lines.append("}")
            self.fn_Definitions.append("\n".join(new_lines))
        finally:
            self.current_class = prev_cls

    def _emit_oop_dispatchers(self) -> None:
        for mname, arity in self.dispatch_methods:
            params = ["WVal v_self"] + [f"WVal _a{i}" for i in range(arity)]
            call_args = ["v_self"] + [f"_a{i}" for i in range(arity)]
            d_lines = [f"static WVal w_dispatch__{mname}__{arity}({', '.join(params)}) {{"]
            for cls_name in self.class_order:
                resolved = self._find_class_method(cls_name, mname)
                if resolved is not None:
                    def_cls, m_decl = resolved
                    if len(m_decl.params) == arity:
                        d_lines.append(
                            f'    if (v_self.tag == W_OBJECT && strcmp(v_self.as.st->name, "{cls_name}") == 0) '
                            f'return w_method_{def_cls}__{mname}({", ".join(call_args)});'
                        )
            d_lines.append("    return w_none();")
            d_lines.append("}")
            self.fn_Definitions.append("\n".join(d_lines))

    def _emit_module_body(self, program: Program, ns: str, out_main_stmts: List[str]) -> None:
        prev_ns = self.current_ns
        self.current_ns = ns

        for stmt in program.body:
            if isinstance(stmt, ImportDecl):
                self._handle_import(stmt, out_main_stmts)
            elif isinstance(stmt, ClassDecl):
                self._emit_class_decl(stmt)
            elif isinstance(stmt, FnDecl):
                self._emit_fn_decl(stmt, ns=ns)

        for stmt in program.body:
            if not isinstance(stmt, (FnDecl, StructDecl, EnumDecl, InterfaceDecl, ClassDecl, ImportDecl)):
                if isinstance(stmt, LetDecl):
                    gv_name = f"v_{ns}_{stmt.name}" if ns else f"v_{stmt.name}"
                    if isinstance(stmt.initializer, ListExpr) and not stmt.initializer.elements:
                        # A direct global store consumes the fresh constructor immediately.
                        val_expr = "w_make_list(0, NULL)"
                    else:
                        val_expr = self.emit_expr(stmt.initializer, out_main_stmts)
                    out_main_stmts.append(f"w_assign(&{gv_name}, {self._own_expr(val_expr)});")
                else:
                    self.emit_stmt(stmt, out_main_stmts)

        self.current_ns = prev_ns

    def _handle_import(self, stmt: ImportDecl, out_main_stmts: List[str]) -> None:
        from error.Error import WError
        raise WError("AST emission imports require a checked compilation session", file=self.file,
                     line=stmt.line, col=stmt.col, code="W9999", stage="module-linking")

    def _emit_fn_decl(self, stmt: FnDecl, ns: str) -> None:
        c_name = self.c_fn(stmt.name, ns=ns)
        params_sig = ", ".join([f"WVal v_{p.name}" for p in stmt.params]) if stmt.params else "void"
        prev_fallible = self.current_fn_fallible
        prev_err_type = self.current_fn_err_type
        self.current_fn_fallible = isinstance(stmt.return_type, ResultType)
        self.current_fn_err_type = self.fn_err_types.get(c_name, "")

        body_stmts: List[str] = []
        self._push_scope("fn")
        ret_expr = self.emit_block_value(stmt.body, body_stmts)
        ret_hold = self.new_aux("_ret")
        body_stmts.append(f"WVal {ret_hold} = {self._own_expr(ret_expr)};")
        self._pop_scope(body_stmts)
        if self.current_fn_fallible:
            body_stmts.append(f'return w_wrap_result({ret_hold}, "{self.current_fn_err_type}");')
        else:
            body_stmts.append(f"return {ret_hold};")

        fn_lines = [f"static WVal {c_name}({params_sig}) {{"]
        for s in body_stmts:
            fn_lines.append(f"    {s}")
        fn_lines.append("}")
        self.fn_Definitions.append("\n".join(fn_lines))
        self.current_fn_fallible = prev_fallible
        self.current_fn_err_type = prev_err_type

    # ==========================================
    # Statement Emission
    # ==========================================

    def emit_block_value(self, block: Block, out: List[str]) -> str:
        res_var = self.new_temp()
        self._declare_owned_var(res_var, "w_unit()", out)
        inner: List[str] = []
        self._push_scope("block")
        for s in block.statements:
            self.emit_stmt(s, inner)
        if block.tail_expr is not None:
            tail_val = self.emit_expr(block.tail_expr, inner)
            inner.append(f"w_assign(&{res_var}, {self._own_expr(tail_val)});")
        self._pop_scope(inner)
        out.append("{")
        for line in inner:
            out.append(f"    {line}")
        out.append("}")
        return res_var

    def emit_stmt(self, stmt: Stmt, out: List[str]) -> None:
        if isinstance(stmt, ExprStmt):
            val = self.emit_expr(stmt.expr, out)
            out.append(f"(void){val};")
            return

        if isinstance(stmt, LetDecl):
            val = self.emit_expr(stmt.initializer, out)
            c_name = f"v_{stmt.name}"
            self._declare_owned_var(c_name, self._own_expr(val), out)
            return

        if isinstance(stmt, ReturnStmt):
            if stmt.value is not None:
                val = self.emit_expr(stmt.value, out)
                ret_hold = self.new_aux("_ret")
                out.append(f"WVal {ret_hold} = {self._own_expr(val)};")
                self._emit_cleanup_until_fn(out)
                if self.current_fn_fallible:
                    out.append(f'return w_wrap_result({ret_hold}, "{self.current_fn_err_type}");')
                else:
                    out.append(f"return {ret_hold};")
            else:
                self._emit_cleanup_until_fn(out)
                if self.current_fn_fallible:
                    out.append("return w_ok(w_unit());")
                else:
                    out.append("return w_unit();")
            return

        if isinstance(stmt, BreakStmt):
            self._emit_cleanup_until_loop(out)
            out.append("break;")
            return

        if isinstance(stmt, ContinueStmt):
            self._emit_cleanup_until_loop(out)
            out.append("continue;")
            return

        if isinstance(stmt, WhileStmt):
            out.append("while (1) {")
            self._push_scope("loop")
            loop_inner: List[str] = []
            cond_val = self.emit_expr(stmt.condition, loop_inner)
            cond_b = self.new_aux("_cond")
            loop_inner.append(f"bool {cond_b} = ({cond_val}).as.b;")
            cond_cleanup: List[str] = []
            self._emit_cleanup_until_loop(cond_cleanup)
            if cond_cleanup:
                loop_inner.append(f"if (!{cond_b}) {{")
                for cl in cond_cleanup:
                    loop_inner.append(f"    {cl}")
                loop_inner.append("    break;")
                loop_inner.append("}")
            else:
                loop_inner.append(f"if (!{cond_b}) break;")
            body_v = self.emit_block_value(stmt.body, loop_inner)
            loop_inner.append(f"(void){body_v};")
            self._pop_scope(loop_inner)
            for line in loop_inner:
                out.append(f"    {line}")
            out.append("}")
            return

        if isinstance(stmt, ForStmt):
            out.append("{")
            self._push_scope("block")
            for_outer: List[str] = []
            iter_val = self.emit_expr(stmt.iterable, for_outer)
            iter_tmp = self.new_temp()
            idx_tmp = self.new_aux("_idx")
            item_tmp = self.new_aux("_item")
            self._declare_owned_var(iter_tmp, self._own_expr(iter_val), for_outer)
            for_outer.append(f"for (int32_t {idx_tmp} = 0; {idx_tmp} < {iter_tmp}.as.list->len; {idx_tmp}++) {{")
            self._push_scope("loop")
            loop_inner = [f"WVal {item_tmp} = {iter_tmp}.as.list->data[{idx_tmp}];"]
            self._emit_pattern_bindings(stmt.pattern, item_tmp, loop_inner)
            body_v = self.emit_block_value(stmt.body, loop_inner)
            loop_inner.append(f"(void){body_v};")
            self._pop_scope(loop_inner)
            for line in loop_inner:
                for_outer.append(f"    {line}")
            for_outer.append("}")
            self._pop_scope(for_outer)
            for line in for_outer:
                out.append(f"    {line}")
            out.append("}")
            return

    def _emit_pattern_bindings(self, pattern: Pattern, val_expr: str, out: List[str]) -> None:
        if isinstance(pattern, IdentifierPattern):
            if pattern.name not in ("None", "none"):
                self._declare_owned_var(f"v_{pattern.name}", f"w_clone({val_expr})", out)
        elif isinstance(pattern, TuplePattern):
            for idx, elem_pat in enumerate(pattern.elements):
                sub_expr = f"({val_expr}).as.tuple->items[{idx}]"
                self._emit_pattern_bindings(elem_pat, sub_expr, out)
        elif isinstance(pattern, EnumPattern):
            if pattern.variant in ("None", "none") and (pattern.enum_name is None or pattern.enum_name.split("__", 1)[0] == "Option"):
                pass
            elif pattern.variant == "Some" and (pattern.enum_name is None or pattern.enum_name.split("__", 1)[0] == "Option"):
                if pattern.args:
                    sub_val = f"w_unwrap_optional({val_expr})"
                    sub_tmp = self.new_aux("_some_val")
                    self._declare_owned_var(sub_tmp, sub_val, out)
                    self._emit_pattern_bindings(pattern.args[0], sub_tmp, out)
            elif pattern.variant == "Ok" and (pattern.enum_name is None or pattern.enum_name.split("__", 1)[0] == "Result"):
                if pattern.args:
                    sub_val = f"w_unwrap_ok({val_expr})"
                    sub_tmp = self.new_aux("_ok_val")
                    self._declare_owned_var(sub_tmp, sub_val, out)
                    self._emit_pattern_bindings(pattern.args[0], sub_tmp, out)
            elif pattern.variant == "Err" and (pattern.enum_name is None or pattern.enum_name.split("__", 1)[0] == "Result"):
                if pattern.args:
                    sub_val = f"w_unwrap_err({val_expr})"
                    sub_tmp = self.new_aux("_err_val")
                    self._declare_owned_var(sub_tmp, sub_val, out)
                    self._emit_pattern_bindings(pattern.args[0], sub_tmp, out)
            else:
                if len(pattern.args) == 1:
                    sub_val = f"({val_expr}).as.en.box->val"
                    self._emit_pattern_bindings(pattern.args[0], sub_val, out)
                elif len(pattern.args) > 1:
                    for idx, arg_pat in enumerate(pattern.args):
                        sub_val = f"({val_expr}).as.en.box->val.as.tuple->items[{idx}]"
                        self._emit_pattern_bindings(arg_pat, sub_val, out)

    def _emit_pattern_cond(self, pattern: Pattern, val_expr: str, out: List[str]) -> str:
        if isinstance(pattern, WildcardPattern):
            return "true"
        if isinstance(pattern, IdentifierPattern):
            if pattern.name in ("None", "none"):
                return f"(({val_expr}).tag == W_NONE || (({val_expr}).tag == W_ENUM && strcmp(({val_expr}).as.en.enum_name, \"Option\") == 0 && strcmp(({val_expr}).as.en.variant, \"None\") == 0))"
            return "true"
        if isinstance(pattern, LiteralPattern):
            lit_v = self.emit_expr(pattern.literal, out)
            return f"w_eq({val_expr}, {lit_v})"
        if isinstance(pattern, EnumPattern):
            if pattern.variant in ("None", "none") and (pattern.enum_name is None or pattern.enum_name.split("__", 1)[0] == "Option"):
                return f"(({val_expr}).tag == W_NONE || (({val_expr}).tag == W_ENUM && strcmp(({val_expr}).as.en.enum_name, \"Option\") == 0 && strcmp(({val_expr}).as.en.variant, \"None\") == 0))"
            if pattern.variant == "Some" and (pattern.enum_name is None or pattern.enum_name.split("__", 1)[0] == "Option"):
                base_cond = f"(!(({val_expr}).tag == W_NONE || (({val_expr}).tag == W_ENUM && strcmp(({val_expr}).as.en.enum_name, \"Option\") == 0 && strcmp(({val_expr}).as.en.variant, \"None\") == 0)))"
                if not pattern.args:
                    return base_cond
                sub_cond = self._emit_pattern_cond(pattern.args[0], f"w_peek_optional({val_expr})", out)
                if sub_cond == "true":
                    return base_cond
                return f"({base_cond} && {sub_cond})"
            if pattern.variant == "Ok" and (pattern.enum_name is None or pattern.enum_name.split("__", 1)[0] == "Result"):
                base_cond = f"(({val_expr}).tag == W_OK || (({val_expr}).tag == W_ENUM && strcmp(({val_expr}).as.en.enum_name, \"Result\") == 0 && strcmp(({val_expr}).as.en.variant, \"Ok\") == 0))"
                if not pattern.args:
                    return base_cond
                sub_cond = self._emit_pattern_cond(pattern.args[0], f"w_peek_ok({val_expr})", out)
                if sub_cond == "true":
                    return base_cond
                return f"({base_cond} && {sub_cond})"
            if pattern.variant == "Err" and (pattern.enum_name is None or pattern.enum_name.split("__", 1)[0] == "Result"):
                base_cond = f"(({val_expr}).tag == W_ERR || (({val_expr}).tag == W_ENUM && strcmp(({val_expr}).as.en.enum_name, \"Result\") == 0 && strcmp(({val_expr}).as.en.variant, \"Err\") == 0))"
                if not pattern.args:
                    return base_cond
                sub_cond = self._emit_pattern_cond(pattern.args[0], f"w_peek_err({val_expr})", out)
                if sub_cond == "true":
                    return base_cond
                return f"({base_cond} && {sub_cond})"

            conds: List[str] = [f"(({val_expr}).tag == W_ENUM && strcmp(({val_expr}).as.en.variant, \"{pattern.variant}\") == 0)"]
            if pattern.enum_name:
                conds.append(f"(strcmp(({val_expr}).as.en.enum_name, \"{pattern.enum_name}\") == 0)")
            if not pattern.args:
                return "(" + " && ".join(conds) + ")"

            conds.append(f"(({val_expr}).as.en.box != NULL)")
            if len(pattern.args) == 1:
                sub_c = self._emit_pattern_cond(pattern.args[0], f"({val_expr}).as.en.box->val", out)
                if sub_c != "true":
                    conds.append(sub_c)
            else:
                conds.append(f"(({val_expr}).as.en.box->val.tag == W_TUPLE && ({val_expr}).as.en.box->val.as.tuple->len == {len(pattern.args)})")
                for idx, arg_pat in enumerate(pattern.args):
                    sub_c = self._emit_pattern_cond(arg_pat, f"({val_expr}).as.en.box->val.as.tuple->items[{idx}]", out)
                    if sub_c != "true":
                        conds.append(sub_c)
            return "(" + " && ".join(conds) + ")"

        if isinstance(pattern, TuplePattern):
            conds = [f"(({val_expr}).tag == W_TUPLE && ({val_expr}).as.tuple->len == {len(pattern.elements)})"]
            for idx, elem_pat in enumerate(pattern.elements):
                sub_c = self._emit_pattern_cond(elem_pat, f"({val_expr}).as.tuple->items[{idx}]", out)
                if sub_c != "true":
                    conds.append(sub_c)
            return "(" + " && ".join(conds) + ")"
        return "true"

    # ==========================================
    # Expression Emission
    # ==========================================

    def emit_lvalue_ref(self, target: Expr, out: List[str]) -> str:
        if isinstance(target, ThisExpr):
            return "&v_self"
        if isinstance(target, IdentExpr):
            return f"&{self.c_var(target.name)}"
        if isinstance(target, IndexExpr):
            obj_ref = self.emit_lvalue_ref(target.object, out)
            idx_val = self.emit_value(target.index, out)
            return f"w_index_ref({obj_ref}, {idx_val})"
        if isinstance(target, MemberExpr):
            obj_ref = self.emit_lvalue_ref(target.object, out)
            return f'w_member_ref({obj_ref}, "{target.property}")'
        # Fallback for temporary receiver
        val = self.emit_expr(target, out)
        if val.startswith("_t"):
            return f"&{val}"
        tmp = self.new_temp()
        self._declare_owned_var(tmp, self._own_expr(val), out)
        return f"&{tmp}"

    def _bind_call(self, c_call: str, out: List[str]) -> str:
        tmp = self.new_temp()
        self._declare_owned_var(tmp, c_call, out)
        return tmp

    def _enum_name(self, expr, fallback):
        if self.interner is not None:
            entry = self.interner.get_entry(getattr(expr, "inferred_type_id", 0))
            if entry.tag in ("optional", "result"):
                return "Option" if entry.tag == "optional" else "Result"
        return fallback

    def emit_expr(self, expr: Expr, out: List[str]) -> str:
        value = self._emit_expr_impl(expr, out)
        if hasattr(expr, "force_result_wrap_id"):
            return self._bind_call(f"w_ok({self._own_expr(value)})", out)
        return value

    def _emit_expr_impl(self, expr: Expr, out: List[str]) -> str:
        if isinstance(expr, IntLiteral):
            return f"w_int({expr.value}LL)"

        if isinstance(expr, FloatLiteral):
            s = repr(expr.value)
            return f"w_float({s})"

        if isinstance(expr, StringLiteral):
            return f"w_str({self.escape_c_str(expr.value)})"

        if isinstance(expr, BoolLiteral):
            return "w_bool(true)" if expr.value else "w_bool(false)"

        if isinstance(expr, NoneLiteral):
            return "w_none()"

        if isinstance(expr, ThisExpr):
            return "v_self"

        if isinstance(expr, NewExpr):
            arg_vals = [self.emit_value(a, out) for a in expr.args]
            return self._bind_call(f"w_new_{expr.class_name}({', '.join(arg_vals)})", out)

        if isinstance(expr, IdentExpr):
            if expr.name in ("None", "none"):
                return "w_none()"
            if expr.name in self.enum_variants and not self._is_local_var(f"v_{expr.name}"):
                en_name = self.enum_variants[expr.name]
                return f'w_enum("{en_name}", "{expr.name}")'
            return self.c_var(expr.name)

        if isinstance(expr, UnaryExpr):
            op_val = self.emit_expr(expr.operand, out)
            if expr.op == "-":
                return f"w_neg({op_val})"
            if expr.op == "not":
                return f"w_bool(!({op_val}).as.b)"

        if isinstance(expr, BinaryExpr):
            if expr.op == "and":
                lhs = self.emit_expr(expr.left, out)
                res = self.new_temp()
                self._declare_owned_var(res, "w_bool(false)", out)
                out.append(f"if (({lhs}).as.b) {{")
                self._push_scope("block")
                rhs_stmts: List[str] = []
                rhs = self.emit_expr(expr.right, rhs_stmts)
                rhs_stmts.append(f"{res} = w_bool(({rhs}).as.b);")
                self._pop_scope(rhs_stmts)
                for s in rhs_stmts:
                    out.append(f"    {s}")
                out.append("}")
                return res

            if expr.op == "or":
                lhs = self.emit_expr(expr.left, out)
                res = self.new_temp()
                self._declare_owned_var(res, "w_bool(true)", out)
                out.append(f"if (!({lhs}).as.b) {{")
                self._push_scope("block")
                rhs_stmts = []
                rhs = self.emit_expr(expr.right, rhs_stmts)
                rhs_stmts.append(f"{res} = w_bool(({rhs}).as.b);")
                self._pop_scope(rhs_stmts)
                for s in rhs_stmts:
                    out.append(f"    {s}")
                out.append("}")
                return res

            lhs = self.emit_value(expr.left, out)
            rhs = self.emit_expr(expr.right, out)
            op_map = {
                "+": "w_add",
                "-": "w_sub",
                "*": "w_mul",
                "/": "w_div",
                "%": "w_mod",
                "<": "w_lt",
                "<=": "w_le",
                ">": "w_gt",
                ">=": "w_ge",
            }
            if expr.op in op_map:
                call = f"{op_map[expr.op]}({lhs}, {rhs})"
                return self._bind_call(call, out) if expr.op == "+" else call
            if expr.op == "==":
                return f"w_bool(w_eq({lhs}, {rhs}))"
            if expr.op == "!=":
                return f"w_bool(!w_eq({lhs}, {rhs}))"

        if isinstance(expr, CoalesceExpr):
            lhs = self.emit_expr(expr.left, out)
            res = self.new_temp()
            self._declare_owned_var(res, self._own_expr(lhs), out)
            out.append(f"if ({res}.tag == W_NONE) {{")
            self._push_scope("block")
            rhs_stmts = []
            rhs = self.emit_expr(expr.right, rhs_stmts)
            rhs_stmts.append(f"w_assign(&{res}, {self._own_expr(rhs)});")
            self._pop_scope(rhs_stmts)
            for s in rhs_stmts:
                out.append(f"    {s}")
            out.append("} else {")
            out.append(f"    w_assign(&{res}, w_unwrap_optional({res}));")
            out.append("}")
            return res

        if isinstance(expr, RangeExpr):
            s_val = self.emit_value(expr.start, out)
            e_val = self.emit_expr(expr.end, out)
            inc = "true" if expr.inclusive else "false"
            return self._bind_call(f"w_make_range({s_val}, {e_val}, {inc})", out)

        if isinstance(expr, PostfixTryExpr):
            op_val = self.emit_expr(expr.operand, out)
            tmp = self.new_temp()
            self._declare_owned_var(tmp, self._own_expr(op_val), out)

            none_cleanup: List[str] = []
            self._emit_cleanup_until_fn(none_cleanup)
            channel_enabled = expr.propagation_kind == "optional"
            out.append(f"if ({str(channel_enabled).lower()} && ({tmp}.tag == W_NONE)) {{")
            for cl in none_cleanup:
                out.append(f"    {cl}")
            out.append("    return w_none();")
            out.append("}")

            err_hold = self.new_aux("_err")
            err_cleanup: List[str] = []
            self._emit_cleanup_until_fn(err_cleanup)
            channel_enabled = expr.propagation_kind == "result"
            out.append(f"if ({str(channel_enabled).lower()} && ({tmp}.tag == W_ERR)) {{")
            out.append(f"    WVal {err_hold} = w_clone({tmp});")
            for cl in err_cleanup:
                out.append(f"    {cl}")
            out.append(f"    return {err_hold};")
            out.append("}")

            unwrapped = self.new_temp()
            helper = "w_unwrap_optional" if expr.propagation_kind == "optional" else "w_unwrap_ok"
            self._declare_owned_var(unwrapped, f"{helper}({tmp})", out)
            return unwrapped
        if isinstance(expr, ElseErrExpr):
            op_val = self.emit_expr(expr.operand, out)
            tmp = self.new_temp()
            self._declare_owned_var(tmp, self._own_expr(op_val), out)
            res = self.new_temp()
            self._declare_owned_var(res, "w_unit()", out)
            out.append(f"if ({tmp}.tag == W_ERR || {tmp}.tag == W_NONE) {{")
            self._push_scope("block")
            handler_stmts: List[str] = []
            if expr.err_name is not None:
                self._declare_owned_var(f"v_{expr.err_name}", f"w_unwrap_err({tmp})", handler_stmts)
            h_val = self.emit_block_value(expr.handler, handler_stmts)
            handler_stmts.append(f"w_assign(&{res}, {self._own_expr(h_val)});")
            self._pop_scope(handler_stmts)
            for s in handler_stmts:
                out.append(f"    {s}")
            out.append("} else {")
            out.append(f"    w_assign(&{res}, w_unwrap_success({tmp}));")
            out.append("}")
            return res

        if isinstance(expr, AssignmentExpr):
            val = self.emit_expr(expr.value, out)
            rhs_hold = self.new_aux("_rhs")
            self._declare_owned_var(rhs_hold, self._own_expr(val), out)
            if isinstance(expr.target, IdentExpr):
                c_target = self.c_var(expr.target.name)
                out.append(f"w_assign(&{c_target}, w_move(&{rhs_hold}));")
                return c_target
            lref = self.emit_lvalue_ref(expr.target, out)
            out.append(f"w_assign({lref}, w_move(&{rhs_hold}));")
            return "w_unit()"

        if isinstance(expr, MemberExpr):
            if isinstance(expr.object, IdentExpr):
                if expr.object.name in self.enum_names:
                    if expr.object.name == "Option" and expr.property in ("None", "none"):
                        return "w_none()"
                    return f'w_enum("{self._enum_name(expr, expr.object.name)}", "{expr.property}")'
                if f"v_{expr.object.name}_{expr.property}" in self.global_vars:
                    return f"v_{expr.object.name}_{expr.property}"
            obj_val = self.emit_expr(expr.object, out)
            return self._bind_call(f'w_clone(w_member_get({obj_val}, "{expr.property}"))', out)

        if isinstance(expr, IndexExpr):
            obj_val = self.emit_value(expr.object, out)
            idx_val = self.emit_expr(expr.index, out)
            return self._bind_call(f"w_index_get_owned({obj_val}, {idx_val})", out)

        if isinstance(expr, CallExpr):
            # 1. Built-in or top-level function call
            if isinstance(expr.callee, IdentExpr):
                fn_name = expr.callee.name
                arg_vals = [self.emit_value(a, out) for a in expr.args]

                if fn_name == "Some" and len(arg_vals) == 1:
                    return self._bind_call(f"w_enum_payload(\"Option\", \"Some\", {self._own_expr(arg_vals[0])})", out)
                if fn_name == "Ok" and len(arg_vals) == 1:
                    return self._bind_call(f"w_ok({self._own_expr(arg_vals[0])})", out)
                if fn_name == "Err" and len(arg_vals) == 1:
                    return self._bind_call(f"w_err({self._own_expr(arg_vals[0])})", out)

                if fn_name in self.enum_variants and not self._is_local_var(f"v_{fn_name}"):
                    en_name = self.enum_variants[fn_name]
                    if len(arg_vals) == 0:
                        return f'w_enum("{en_name}", "{fn_name}")'
                    elif len(arg_vals) == 1:
                        return self._bind_call(f'w_enum_payload("{en_name}", "{fn_name}", {self._own_expr(arg_vals[0])})', out)
                    else:
                        tup_tmp = self.new_temp()
                        elems_c = ", ".join(arg_vals)
                        out.append(f"WVal _elems_{tup_tmp}[{len(arg_vals)}] = {{ {elems_c} }};")
                        out.append(f"WVal {tup_tmp} = w_make_tuple({len(arg_vals)}, _elems_{tup_tmp});")
                        return self._bind_call(f'w_enum_payload("{en_name}", "{fn_name}", {self._own_expr(tup_tmp)})', out)

                if fn_name == "print":
                    if not arg_vals:
                        return self._bind_call("w_builtin_print(0, NULL)", out)
                    arr_tmp = self.new_aux("_arr")
                    elems_c = ", ".join(arg_vals)
                    out.append(f"WVal {arr_tmp}[{len(arg_vals)}] = {{ {elems_c} }};")
                    return self._bind_call(f"w_builtin_print({len(arg_vals)}, {arr_tmp})", out)

                if fn_name == "eprint":
                    if not arg_vals:
                        return self._bind_call("w_builtin_eprint(0, NULL)", out)
                    arr_tmp = self.new_aux("_arr")
                    elems_c = ", ".join(arg_vals)
                    out.append(f"WVal {arr_tmp}[{len(arg_vals)}] = {{ {elems_c} }};")
                    return self._bind_call(f"w_builtin_eprint({len(arg_vals)}, {arr_tmp})", out)

                if fn_name == "weak" and len(arg_vals) == 1:
                    return self._bind_call(f"w_builtin_weak_owned({self._own_expr(arg_vals[0])})", out)
                builtin_1 = {
                    "weak": "w_builtin_weak", "upgrade": "w_builtin_upgrade",
                    "len": "w_builtin_len",
                    "str": "w_builtin_str",
                    "int": "w_builtin_int",
                    "float": "w_builtin_float",
                    "ord": "w_builtin_ord",
                    "chr": "w_builtin_chr",
                    "bytes": "w_builtin_bytes",
                    "enumerate": "w_builtin_enumerate",
                    "dict_items": "w_builtin_dict_items",
                    "read_file": "w_builtin_read_file",
                }
                if fn_name in builtin_1 and len(arg_vals) == 1:
                    return self._bind_call(f"{builtin_1[fn_name]}({arg_vals[0]})", out)

                if fn_name == "args" and len(arg_vals) == 0:
                    return self._bind_call("w_builtin_args()", out)

                if fn_name == "exit" and len(arg_vals) == 1:
                    return self._bind_call(f"w_builtin_exit({arg_vals[0]})", out)

                if fn_name == "write_file" and len(arg_vals) == 2:
                    return self._bind_call(f"w_builtin_write_file({arg_vals[0]}, {arg_vals[1]})", out)

                if fn_name == "slice" and len(arg_vals) == 3:
                    return self._bind_call(f"w_builtin_slice({arg_vals[0]}, {arg_vals[1]}, {arg_vals[2]})", out)

                if fn_name in self.classes:
                    return self._bind_call(f"w_new_{fn_name}({', '.join(arg_vals)})", out)

                c_callee = self.c_fn(fn_name)
                return self._bind_call(f"{c_callee}({', '.join(arg_vals)})", out)

            # 2. Method call or module function call: obj.method(...)
            if isinstance(expr.callee, MemberExpr):
                obj_expr = expr.callee.object
                method = expr.callee.property

                if isinstance(obj_expr, IdentExpr) and obj_expr.name in self.enum_names:
                    en_name = obj_expr.name
                    arg_vals = [self.emit_value(a, out) for a in expr.args]
                    if (en_name == "Result" or en_name.startswith("Result__")) and method == "Ok" and len(arg_vals) == 1:
                        return self._bind_call(f"w_ok({self._own_expr(arg_vals[0])})", out)
                    if (en_name == "Result" or en_name.startswith("Result__")) and method == "Err" and len(arg_vals) == 1:
                        return self._bind_call(f"w_err({self._own_expr(arg_vals[0])})", out)
                    if (en_name == "Option" or en_name.startswith("Option__")) and method in ("None", "none"):
                        return "w_none()"
                    if len(arg_vals) == 0:
                        return f'w_enum("{en_name}", "{method}")'
                    elif len(arg_vals) == 1:
                        return self._bind_call(f'w_enum_payload("{en_name}", "{method}", {self._own_expr(arg_vals[0])})', out)
                    else:
                        tup_tmp = self.new_temp()
                        elems_c = ", ".join(arg_vals)
                        out.append(f"WVal _elems_{tup_tmp}[{len(arg_vals)}] = {{ {elems_c} }};")
                        out.append(f"WVal {tup_tmp} = w_make_tuple({len(arg_vals)}, _elems_{tup_tmp});")
                        return self._bind_call(f'w_enum_payload("{en_name}", "{method}", {self._own_expr(tup_tmp)})', out)

                # super.init(...) or super.method(...)
                if isinstance(obj_expr, SuperExpr):
                    arg_vals = [self.emit_value(a, out) for a in expr.args]
                    call_args = ["v_self"] + arg_vals
                    if self.current_class is not None and self.current_class.superclass is not None:
                        resolved = self._find_class_method(self.current_class.superclass, method)
                        if resolved is not None:
                            def_cls, _ = resolved
                            return self._bind_call(f"w_method_{def_cls}__{method}({', '.join(call_args)})", out)
                    return "w_unit()"

                # Check if module call: mod.fn(...)
                if isinstance(obj_expr, IdentExpr):
                    mod_fn = self.c_fn(method, ns=obj_expr.name)
                    if mod_fn in self.fallible_fns:
                        arg_vals = [self.emit_value(a, out) for a in expr.args]
                        return self._bind_call(f"{mod_fn}({', '.join(arg_vals)})", out)

                # Collection methods
                if method == "append":
                    lref = self.emit_lvalue_ref(obj_expr, out)
                    arg_v = self.emit_value(expr.args[0], out)
                    return self._bind_call(f"w_list_append({lref}, {arg_v})", out)
                if method == "pop":
                    lref = self.emit_lvalue_ref(obj_expr, out)
                    return self._bind_call(f"w_list_pop({lref})", out)
                if method == "clear":
                    lref = self.emit_lvalue_ref(obj_expr, out)
                    return self._bind_call(f"w_list_clear({lref})", out)
                if method == "get":
                    obj_v = self.emit_value(obj_expr, out)
                    arg_v = self.emit_value(expr.args[0], out)
                    return self._bind_call(f"w_dict_get({obj_v}, {arg_v})", out)
                if method == "keys":
                    obj_v = self.emit_value(obj_expr, out)
                    return self._bind_call(f"w_dict_keys({obj_v})", out)
                if method == "values":
                    obj_v = self.emit_value(obj_expr, out)
                    return self._bind_call(f"w_dict_values({obj_v})", out)

                # OOP dynamic method dispatch
                obj_v = self.emit_value(obj_expr, out)
                arg_vals = [self.emit_value(a, out) for a in expr.args]
                call_args = [obj_v] + arg_vals
                return self._bind_call(f"w_dispatch__{method}__{len(arg_vals)}({', '.join(call_args)})", out)

        if isinstance(expr, ListExpr):
            if not expr.elements:
                return self._bind_call("w_make_list(0, NULL)", out)
            elem_vals = [self.emit_value(e, out) for e in expr.elements]
            arr_tmp = self.new_aux("_arr")
            out.append(f"WVal {arr_tmp}[{len(elem_vals)}] = {{ {', '.join(elem_vals)} }};")
            return self._bind_call(f"w_make_list({len(elem_vals)}, {arr_tmp})", out)

        if isinstance(expr, TupleExpr):
            if not expr.elements:
                return self._bind_call("w_make_tuple(0, NULL)", out)
            elem_vals = [self.emit_value(e, out) for e in expr.elements]
            arr_tmp = self.new_aux("_arr")
            out.append(f"WVal {arr_tmp}[{len(elem_vals)}] = {{ {', '.join(elem_vals)} }};")
            return self._bind_call(f"w_make_tuple({len(elem_vals)}, {arr_tmp})", out)

        if isinstance(expr, DictExpr):
            if not expr.entries:
                return self._bind_call("w_make_dict(0, NULL, NULL)", out)
            pairs = [(self.emit_value(e.key, out), self.emit_value(e.value, out)) for e in expr.entries]
            k_vals = [key for key, _ in pairs]
            v_vals = [value for _, value in pairs]
            k_tmp = self.new_aux("_k")
            v_tmp = self.new_aux("_v")
            out.append(f"WVal {k_tmp}[{len(k_vals)}] = {{ {', '.join(k_vals)} }};")
            out.append(f"WVal {v_tmp}[{len(v_vals)}] = {{ {', '.join(v_vals)} }};")
            return self._bind_call(f"w_make_dict({len(k_vals)}, {k_tmp}, {v_tmp})", out)

        if isinstance(expr, StructInitExpr):
            if not expr.fields:
                return self._bind_call(f'w_make_struct("{expr.struct_name}", 0, NULL, NULL)', out)
            f_names = [f'"{f.name}"' for f in expr.fields]
            f_vals = [self.emit_value(f.value, out) for f in expr.fields]
            k_tmp = self.new_aux("_k")
            v_tmp = self.new_aux("_v")
            out.append(f"const char* {k_tmp}[{len(f_names)}] = {{ {', '.join(f_names)} }};")
            out.append(f"WVal {v_tmp}[{len(f_vals)}] = {{ {', '.join(f_vals)} }};")
            return self._bind_call(f'w_make_struct("{expr.struct_name}", {len(f_names)}, {k_tmp}, {v_tmp})', out)

        if isinstance(expr, IfExpr):
            res = self.new_temp()
            self._declare_owned_var(res, "w_unit()", out)
            cond_v = self.emit_expr(expr.condition, out)
            out.append(f"if (({cond_v}).as.b) {{")
            self._push_scope("block")
            then_stmts: List[str] = []
            then_v = self.emit_block_value(expr.then_branch, then_stmts)
            then_stmts.append(f"w_assign(&{res}, {self._own_expr(then_v)});")
            self._pop_scope(then_stmts)
            for s in then_stmts:
                out.append(f"    {s}")
            out.append("}")

            # Handle elif and else branches with nested else blocks so elif conditions evaluate lazily
            self._emit_elif_chain(expr.elif_branches, 0, expr.else_branch, res, out)
            return res

        if isinstance(expr, MatchExpr):
            subj_v = self.emit_expr(expr.subject, out)
            subj_tmp = self.new_temp()
            self._declare_owned_var(subj_tmp, self._own_expr(subj_v), out)
            res = self.new_temp()
            self._declare_owned_var(res, "w_unit()", out)
            self._emit_match_arms(expr.arms, 0, subj_tmp, res, out)
            return res

        return "w_unit()"

    def _emit_elif_chain(self, elifs: List, idx: int, else_branch: Optional[Block], res_var: str, out: List[str]) -> None:
        if idx < len(elifs):
            eb = elifs[idx]
            out.append("else {")
            self._push_scope("block")
            inner: List[str] = []
            eb_cond = self.emit_expr(eb.condition, inner)
            inner.append(f"if (({eb_cond}).as.b) {{")
            self._push_scope("block")
            eb_stmts: List[str] = []
            eb_v = self.emit_block_value(eb.body, eb_stmts)
            eb_stmts.append(f"w_assign(&{res_var}, {self._own_expr(eb_v)});")
            self._pop_scope(eb_stmts)
            for s in eb_stmts:
                inner.append(f"    {s}")
            inner.append("}")
            self._emit_elif_chain(elifs, idx + 1, else_branch, res_var, inner)
            self._pop_scope(inner)
            for s in inner:
                out.append(f"    {s}")
            out.append("}")
        elif else_branch is not None:
            out.append("else {")
            self._push_scope("block")
            else_stmts: List[str] = []
            else_v = self.emit_block_value(else_branch, else_stmts)
            else_stmts.append(f"w_assign(&{res_var}, {self._own_expr(else_v)});")
            self._pop_scope(else_stmts)
            for s in else_stmts:
                out.append(f"    {s}")
            out.append("}")

    def _emit_match_arms(self, arms: List, idx: int, subj_tmp: str, res_var: str, out: List[str]) -> None:
        if idx >= len(arms):
            return
        arm = arms[idx]
        cond_str = self._emit_pattern_cond(arm.pattern, subj_tmp, out)

        if arm.guard is not None:
            matched = self.new_aux("_matched")
            out.append(f"bool {matched} = false;")
            out.append(f"if ({cond_str}) {{")
            self._push_scope("block")
            inner = []
            self._emit_pattern_bindings(arm.pattern, subj_tmp, inner)
            guard = self.emit_expr(arm.guard, inner)
            inner.append(f"if (({guard}).as.b) {{")
            self._push_scope("block")
            body = []
            result = self.emit_block_value(arm.body, body)
            body.append(f"w_assign(&{res_var}, {self._own_expr(result)});")
            body.append(f"{matched} = true;")
            self._pop_scope(body)
            inner.extend("    " + line for line in body)
            inner.append("}")
            self._pop_scope(inner)
            out.extend("    " + line for line in inner)
            out.append("}")
            out.append(f"if (!{matched}) {{")
            self._push_scope("block")
            fallback = []
            self._emit_match_arms(arms, idx + 1, subj_tmp, res_var, fallback)
            self._pop_scope(fallback)
            out.extend("    " + line for line in fallback)
            out.append("}")
            return
        out.append(f"if ({cond_str}) {{")
        self._push_scope("block")
        arm_stmts: List[str] = []
        self._emit_pattern_bindings(arm.pattern, subj_tmp, arm_stmts)
        arm_v = self.emit_block_value(arm.body, arm_stmts)
        arm_stmts.append(f"w_assign(&{res_var}, {self._own_expr(arm_v)});")
        self._pop_scope(arm_stmts)
        for s in arm_stmts:
            out.append(f"    {s}")
        out.append("}")
        if idx + 1 < len(arms):
            out.append("else {")
            self._push_scope("block")
            else_inner: List[str] = []
            self._emit_match_arms(arms, idx + 1, subj_tmp, res_var, else_inner)
            self._pop_scope(else_inner)
            for s in else_inner:
                out.append(f"    {s}")
            out.append("}")


def compile_to_c(source: str, file: str = "<stdin>") -> str:
    ast = Parser(file=file).parse(source)
    return CCodeGen(file=file).generate(ast)
