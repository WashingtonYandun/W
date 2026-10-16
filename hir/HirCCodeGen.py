from error.Error import WError
"""
hir/HirCCodeGen.py - Direct C99 Code Generator from Typed HIR.

Translates a verified HirModule directly into clean, portable, and memory-safe C99 code.
Guarantees:
1. Exact reference counting (ARC) and deterministic LIFO lifetime management via CleanupScope.
2. Direct lowering from typed HIR nodes without AST re-interpretation.
3. OOP dynamic method dispatch and inheritance preservation.
4. Fallible error handling (T ! E) and Optional (T?) propagation.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from checker.TypeInterner import (
    TypeInterner, TYPE_ERROR, TYPE_UNIT, TYPE_BOOL, TYPE_INT, TYPE_FLOAT, TYPE_STR, TYPE_NONE
)
from hir.HirNodes import (
    HirClosure, HirFunctionRef, HirIndirectCall, Span, HirNode, HirExpr, HirStmt, HirParam, HirBlock, HirFieldDef,
    HirFnDecl, HirStructDecl, HirEnumDecl, HirInterfaceDecl, HirClassDecl, HirModule,
    HirLet, HirBindTemp, HirAssign, HirWhile, HirForList, HirReturn, HirBreak, HirContinue, HirExprStmt,
    HirConstInt, HirConstFloat, HirConstBool, HirConstStr, HirConstNone, HirConstUnit,
    HirLocalRef, HirThisRef, HirUnaryOp, HirBinaryOp,
    HirConstructStruct, HirConstructEnum, HirConstructObject, HirConstructList, HirConstructDict, HirConstructTuple,
    HirDirectCall, HirBuiltinCall, HirMethodCall, HirFieldRead, HirIndexRead,
    HirTryPropagate, HirCoalesce, HirElseHandle, HirIf, HirMatch, HirMatchArm, HirRange, HirSuperRef,
    SymbolId, FieldId, VariantId, CallTarget, DirectCallTarget, BuiltinCallTarget, VirtualCallTarget,
    CowProjection, CowFieldProjection, CowIndexProjection, CowPath,
    HirPattern, HirWildcardPattern, HirBindingPattern, HirLiteralPattern, HirEnumPattern, HirTuplePattern,
    HirCoerce
)
from common.Telemetry import CodegenTelemetry


class CleanupScope:
    def __init__(self, kind: str) -> None:
        self.kind = kind  # "fn" | "loop" | "block"
        self.vars: List[str] = []


class HirCCodeGen:
    def __init__(self, interner: Optional[TypeInterner] = None, file_path: str = "<stdin>"):
        self.interner = interner
        self.file_path = file_path
        self.function_adapters = set()
        self.temp_counter = 0
        self.aux_counter = 0
        self.is_top_level = False
        self.enum_names: Set[str] = set()
        self.classes: Dict[str, HirClassDecl] = {}
        self.class_order: List[str] = []
        self.dispatch_methods: List[Tuple[str, int]] = []
        self.current_class: Optional[HirClassDecl] = None
        self.fallible_fns: Dict[str, bool] = {}
        self.fn_err_types: Dict[str, str] = {}
        self.current_fn_fallible: bool = False
        self.current_fn_err_type: str = ""
        self.global_vars: List[str] = []
        self.fn_prototypes: List[str] = []
        self.fn_definitions: List[str] = []
        self.scope_stack: List[CleanupScope] = []
        self.symbol_names: Dict[int, str] = {}
        self.declared_names: Set[str] = set()
        self.telemetry: CodegenTelemetry = CodegenTelemetry()

    def new_temp(self) -> str:
        name = f"_t{self.temp_counter}"
        self.temp_counter += 1
        return name

    def new_aux(self, prefix: str = "_aux") -> str:
        name = f"{prefix}{self.aux_counter}"
        self.aux_counter += 1
        return name

    # -------------------------------------------------------------
    # Lifetime & Scope Management
    # -------------------------------------------------------------

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

    def _bind_call(self, c_call: str, out: List[str]) -> str:
        tmp = self.new_temp()
        self._declare_owned_var(tmp, c_call, out)
        return tmp

    def _source_call(self, name: str, args: str, node: HirNode) -> str:
        span = node.span
        file = span.file_path or self.file_path
        return f"{name}({args}, {self.escape_c_str(file)}, {span.line}, {span.col})"

    def _is_local_var(self, c_name: str) -> bool:
        for scope in reversed(self.scope_stack):
            if c_name in scope.vars:
                return True
        return False

    def c_var_decl(self, name: str, symbol_id: Optional[SymbolId] = None) -> str:
        if symbol_id is not None:
            if symbol_id.id in self.symbol_names:
                return self.symbol_names[symbol_id.id]
            base_name = f"v_{name}"
            if base_name in self.declared_names:
                c_name = f"v_{name}_{symbol_id.id}"
            else:
                c_name = base_name
            self.declared_names.add(c_name)
            self.symbol_names[symbol_id.id] = c_name
            return c_name
        return f"v_{name}"

    def c_var(self, name: str, symbol_id: Optional[SymbolId] = None) -> str:
        if symbol_id is not None and symbol_id.id in self.symbol_names:
            return self.symbol_names[symbol_id.id]
        local_name = f"v_{name}"
        if self._is_local_var(local_name):
            return local_name
        if local_name in self.global_vars:
            return local_name
        return local_name

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
                out.append("\\000")
            else:
                out.append(ch)
        out.append('"')
        return "".join(out)

    # -------------------------------------------------------------
    # Primary Lowering Driver
    # -------------------------------------------------------------

    def generate(self, module: HirModule) -> str:
        from hir.HirVerifier import HirVerifier
        if self.interner is None:
            raise WError("HIR emission requires a type interner", file=self.file_path,
                         code="W9999", stage="hir-verification")
        HirVerifier(self.interner, self.file_path).verify(module)
        # 1. Collect declarations
        for en in module.enums:
            self.enum_names.add(en.name)

        for cl in module.classes:
            if cl.name not in self.classes:
                self.classes[cl.name] = cl
                self.class_order.append(cl.name)
            for m in cl.methods:
                if m.name != "init":
                    key = (m.name, len(m.params))
                    if key not in self.dispatch_methods:
                        self.dispatch_methods.append(key)

        for fn in module.functions:
            c_name = f"w_fn_{fn.name}"
            self.fallible_fns[c_name] = fn.is_fallible
            self.fn_err_types[c_name] = fn.err_type_name
            params_sig = ", ".join([f"WVal v_{p.name}" for p in fn.params]) if fn.params else "void"
            self.fn_prototypes.append(f"static WVal {c_name}({params_sig});")

        for stmt in module.top_level_stmts:
            if isinstance(stmt, HirLet):
                gv_name = f"v_{stmt.name}"
                if gv_name not in self.global_vars:
                    self.global_vars.append(gv_name)
                if stmt.symbol_id is not None:
                    self.symbol_names[stmt.symbol_id.id] = gv_name

        # 2. OOP Prototypes
        for cls_name in self.class_order:
            cdecl = self.classes[cls_name]
            self.fn_prototypes.append(f"static const WClassVTable w_vtable_{cls_name};")
            for m in cdecl.methods:
                params = ["WVal v_self"] + [f"WVal v_{p.name}" for p in m.params]
                self.fn_prototypes.append(f"static WVal w_method_{cls_name}__{m.name}({', '.join(params)});")
            init_res = self._find_class_method(cls_name, "init")
            if init_res is not None:
                _, init_m = init_res
                init_sig = ", ".join([f"WVal v_{p.name}" for p in init_m.params]) if init_m.params else "void"
            else:
                init_sig = "void"
            self.fn_prototypes.append(f"static WVal w_new_{cls_name}({init_sig});")

        for mname, arity in self.dispatch_methods:
            params = ["WVal v_self"] + [f"WVal _a{i}" for i in range(arity)]
            self.fn_prototypes.append(f"static WVal w_dispatch__{mname}__{arity}({', '.join(params)});")

        # 3. Emit functions and class methods
        for cl in module.classes:
            self._emit_class(cl)

        for fn in module.functions:
            self._emit_function(fn)

        # 4. Emit Top-Level executable statements into main
        main_stmts: List[str] = []
        self._push_scope("fn")
        self.is_top_level = True
        self.symbol_names.clear()
        self.declared_names.clear()
        self.declared_names.update(self.global_vars)
        top_stmts = list(module.top_level_stmts)
        entry_call = top_stmts[-1] if top_stmts and self._is_entrypoint_call(top_stmts[-1]) else None
        for stmt in top_stmts:
            if isinstance(stmt, HirLet) and stmt.symbol_id is not None:
                self.symbol_names[stmt.symbol_id.id] = f"v_{stmt.name}"
            if stmt is entry_call:
                # The module calls main() explicitly at top level. Its Result must
                # not be discarded, or a failed program would exit 0 silently.
                main_stmts.append("WVal _t_main = " + self.emit_expr(stmt.expr, main_stmts) + ";")
                self._emit_entrypoint_guard(main_stmts)
            else:
                self.emit_stmt(stmt, main_stmts)
        self.is_top_level = False

        if getattr(module, "call_entrypoint", not module.top_level_stmts) and "w_fn_main" in self.fallible_fns:
            main_stmts.append("WVal _t_main = w_fn_main();")
            self._emit_entrypoint_guard(main_stmts)

        self._pop_scope(main_stmts)
        self._emit_oop_dispatchers()

        # 5. Assemble final C99 file
        lines: List[str] = [
            '#include "runtime/w_runtime.h"',
            ""
        ]

        if self.global_vars:
            for gv in self.global_vars:
                lines.append(f"static WVal {gv};")
            lines.append("")

        if self.fn_prototypes:
            lines.extend(self.fn_prototypes)
            lines.append("")

        if self.fn_definitions:
            for fd in self.fn_definitions:
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
        self.telemetry = CodegenTelemetry(
            generated_functions=len(self.fn_definitions),
            generated_structs=len(module.structs),
            generated_enums=len(self.enum_names),
            generated_classes=len(self.classes),
            generated_c_lines=len(c_code_str.splitlines()),
            generated_c_bytes=len(c_code_str.encode("utf-8")),
        )
        return c_code_str

    # -------------------------------------------------------------
    # Class & OOP Emission
    # -------------------------------------------------------------

    def _find_class_method(self, class_name: str, method_name: str) -> Optional[Tuple[str, HirFnDecl]]:
        curr: Optional[str] = class_name
        while curr is not None and curr in self.classes:
            cdecl = self.classes[curr]
            for m in cdecl.methods:
                if m.name == method_name:
                    return (curr, m)
            curr = cdecl.superclass
        return None

    def _collect_class_fields(self, class_name: str) -> List[HirFieldDef]:
        lineage: List[HirClassDecl] = []
        curr: Optional[str] = class_name
        while curr is not None and curr in self.classes:
            lineage.append(self.classes[curr])
            curr = self.classes[curr].superclass
        lineage.reverse()
        fields: List[HirFieldDef] = []
        seen: Set[str] = set()
        for cdecl in lineage:
            for f in cdecl.fields:
                if f.name not in seen:
                    seen.add(f.name)
                    fields.append(f)
        return fields

    def _default_c_expr_for_type_id(self, type_id: int) -> str:
        if self.interner.get_entry(type_id).tag == "weak":
            return "w_empty_weak()"
        if type_id == TYPE_INT:
            return "w_int(0LL)"
        if type_id == TYPE_FLOAT:
            return "w_float(0.0)"
        if type_id == TYPE_BOOL:
            return "w_bool(false)"
        if type_id == TYPE_STR:
            return 'w_str("")'
        if type_id == TYPE_NONE:
            return "w_none()"
        if type_id == TYPE_UNIT:
            return "w_unit()"
        return "w_none()"

    def _emit_class(self, cl: HirClassDecl) -> None:
        prev_cls = self.current_class
        self.current_class = cl
        try:
            for m in cl.methods:
                c_name = f"w_method_{cl.name}__{m.name}"
                self.symbol_names.clear()
                self.declared_names.clear()
                self.declared_names.add("v_self")
                params = ["WVal v_self"] + [f"WVal {self.c_var_decl(p.name, p.symbol_id)}" for p in m.params]
                prev_fallible = self.current_fn_fallible
                prev_err_type = self.current_fn_err_type
                self.current_fn_fallible = m.is_fallible
                self.current_fn_err_type = m.err_type_name

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
                self.fn_definitions.append("\n".join(fn_lines))
                self.current_fn_fallible = prev_fallible
                self.current_fn_err_type = prev_err_type

            # w_new_<ClassName>
            all_fields = self._collect_class_fields(cl.name)
            init_res = self._find_class_method(cl.name, "init")
            if init_res is not None:
                init_cls, init_m = init_res
                init_sig = ", ".join([f"WVal v_{p.name}" for p in init_m.params]) if init_m.params else "void"
                init_args = ["v_self"] + [f"v_{p.name}" for p in init_m.params]
            else:
                init_cls = ""
                init_m = None
                init_sig = "void"
                init_args = []

            new_lines = [f"static WVal w_new_{cl.name}({init_sig}) {{"]
            if all_fields:
                f_names = ", ".join([f'"{f.name}"' for f in all_fields])
                f_defaults = ", ".join([self._default_c_expr_for_type_id(f.type_id) for f in all_fields])
                new_lines.append(f"    const char* _k[{len(all_fields)}] = {{ {f_names} }};")
                new_lines.append(f"    WVal _v[{len(all_fields)}] = {{ {f_defaults} }};")
                new_lines.append(f'    WVal v_self = w_make_object("{cl.name}", {len(all_fields)}, _k, _v);')
                new_lines.append(f"    w_release_array({len(all_fields)}, _v);")
            else:
                new_lines.append(f'    WVal v_self = w_make_object("{cl.name}", 0, NULL, NULL);')
            new_lines.append(f"    v_self.as.st->vtable = &w_vtable_{cl.name};")
            if init_m is not None:
                new_lines.append(f"    w_release(w_method_{init_cls}__init({', '.join(init_args)}));")
            new_lines.append("    return v_self;")
            new_lines.append("}")
            self.fn_definitions.append("\n".join(new_lines))
        finally:
            self.current_class = prev_cls

    def _emit_oop_dispatchers(self) -> None:
        from codegen.VirtualDispatch import emit_vtables
        self.fn_definitions.extend(emit_vtables(self.class_order, self.dispatch_methods, self._find_class_method))

    def _emit_function(self, fn: HirFnDecl) -> None:
        if hasattr(fn, "extern_types"):
            from codegen.ForeignAbi import foreign_wrapper
            prototype, wrapper = foreign_wrapper("w_fn_" + fn.name, fn.extern_name, fn.extern_types)
            self.fn_prototypes.append(prototype)
            self.fn_definitions.append(wrapper)
            return
        c_name = f"w_fn_{fn.name}"
        self.symbol_names.clear()
        self.declared_names.clear()
        params_sig = ", ".join([f"WVal {self.c_var_decl(p.name, p.symbol_id)}" for p in fn.params]) if fn.params else "void"
        prev_fallible = self.current_fn_fallible
        prev_err_type = self.current_fn_err_type
        self.current_fn_fallible = fn.is_fallible
        self.current_fn_err_type = fn.err_type_name

        body_stmts: List[str] = []
        self._push_scope("fn")
        ret_expr = self.emit_block_value(fn.body, body_stmts)
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
        self.fn_definitions.append("\n".join(fn_lines))
        self.current_fn_fallible = prev_fallible
        self.current_fn_err_type = prev_err_type

    # -------------------------------------------------------------
    # Statement Emission
    # -------------------------------------------------------------

    def emit_block_value(self, block: HirBlock, out: List[str]) -> str:
        res_var = self.new_temp()
        self._declare_owned_var(res_var, "w_unit()", out)
        inner: List[str] = []
        self._push_scope("block")
        for s in block.statements:
            self.emit_stmt(s, inner)
        if getattr(block, "tail_expr", None) is not None:
            tail_val = self.emit_expr(block.tail_expr, inner)
            inner.append(f"w_assign(&{res_var}, {self._own_expr(tail_val)});")
        self._pop_scope(inner)
        out.append("{")
        for line in inner:
            out.append(f"    {line}")
        out.append("}")
        return res_var

    def emit_stmt(self, stmt: HirStmt, out: List[str]) -> None:
        if isinstance(stmt, HirExprStmt):
            val = self.emit_expr(stmt.expr, out)
            out.append(f"(void){val};")
            return

        if isinstance(stmt, HirLet):
            val = self.emit_expr(stmt.init_expr, out)
            c_name = self.c_var_decl(stmt.name, stmt.symbol_id)
            if self.is_top_level:
                out.append(f"w_assign(&{c_name}, {self._own_expr(val)});")
            else:
                self._declare_owned_var(c_name, self._own_expr(val), out)
            return

        if isinstance(stmt, HirBindTemp):
            val = self.emit_expr(stmt.init_expr, out)
            # Must go through c_var_decl, which is what registers the symbol-to-C-name
            # mapping. Declaring the raw temp_name here made the emitted variable
            # `v_<temp>` while every later HirLocalRef resolved to `v_v_<temp>`, and the
            # C compiler rejected the result with "use of undeclared identifier".
            self._declare_owned_var(self.c_var_decl(stmt.temp_name, stmt.symbol_id),
                                    self._own_expr(val), out)
            return

        if isinstance(stmt, HirAssign):
            lref = self.prepare_assignment_ref(stmt.target, out)
            val = self.emit_expr(stmt.value, out)
            rhs_hold = self.new_aux("_rhs")
            self._declare_owned_var(rhs_hold, self._own_expr(val), out)
            out.append(f"w_assign({lref}, w_move(&{rhs_hold}));")
            return

        if isinstance(stmt, HirReturn):
            val = self.emit_expr(stmt.value_expr, out)
            ret_hold = self.new_aux("_ret")
            out.append(f"WVal {ret_hold} = {self._own_expr(val)};")
            self._emit_cleanup_until_fn(out)
            if self.current_fn_fallible:
                out.append(f'return w_wrap_result({ret_hold}, "{self.current_fn_err_type}");')
            else:
                out.append(f"return {ret_hold};")
            return

        if isinstance(stmt, HirBreak):
            self._emit_cleanup_until_loop(out)
            out.append("break;")
            return

        if isinstance(stmt, HirContinue):
            self._emit_cleanup_until_loop(out)
            out.append("continue;")
            return

        if isinstance(stmt, HirWhile):
            out.append("while (1) {")
            self._push_scope("loop")
            loop_inner: List[str] = []
            cond_val = self.emit_expr(stmt.cond_expr, loop_inner)
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

        if isinstance(stmt, HirForList):
            out.append("{")
            self._push_scope("block")
            for_outer: List[str] = []
            iter_val = self.emit_expr(stmt.list_expr, for_outer)
            iter_tmp = self.new_temp()
            idx_tmp = self.new_aux("_idx")
            item_tmp = self.new_aux("_item")
            self._declare_owned_var(iter_tmp, self._own_expr(iter_val), for_outer)
            for_outer.append(f"for (int32_t {idx_tmp} = 0; {idx_tmp} < {iter_tmp}.as.list->len; {idx_tmp}++) {{")
            self._push_scope("loop")
            loop_inner = [f"WVal {item_tmp} = {iter_tmp}.as.list->data[{idx_tmp}];"]
            if getattr(stmt, "pattern", None) is not None and isinstance(stmt.pattern, HirPattern):
                self._emit_pattern_bindings(stmt.pattern, item_tmp, loop_inner)
            else:
                c_name = self.c_var_decl(stmt.elem_name, getattr(stmt, "symbol_id", None))
                self._declare_owned_var(c_name, f"w_clone({item_tmp})", loop_inner)
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

        raise WError(f"Unsupported HIR statement: {type(stmt).__name__}",
                     line=stmt.span.line, col=stmt.span.col, file=self.file_path,
                     code="W9999", stage="codegen")

    # -------------------------------------------------------------
    # Expression Emission
    # -------------------------------------------------------------

    def prepare_assignment_ref(self, target, out):
        if isinstance(target, HirIndexRead):
            parent = self.prepare_assignment_ref(target.object, out)
            index = self.emit_value(target.index, out)
            return self._source_call("w_index_ref_at", f"{parent}, {index}", target)
        if isinstance(target, HirFieldRead):
            if self.interner.get_entry(target.object.type_id).tag == 'class':
                parent = '&' + self.emit_value(target.object, out)
            else:
                parent = self.prepare_assignment_ref(target.object, out)
            return f'w_member_ref({parent}, "{target.field_name}")'
        return self.emit_lvalue_ref(target, out)

    def emit_lvalue_ref(self, target: HirExpr, out: List[str]) -> str:
        if isinstance(target, HirThisRef):
            return "&v_self"
        if isinstance(target, HirLocalRef):
            return f"&{self.c_var(target.name, target.symbol_id)}"
        if isinstance(target, HirIndexRead):
            obj_ref = self.emit_lvalue_ref(target.object, out)
            idx_val = self.emit_value(target.index, out)
            return self._source_call("w_index_ref_at", f"{obj_ref}, {idx_val}", target)
        if isinstance(target, HirFieldRead):
            obj_ref = self.emit_lvalue_ref(target.object, out)
            return f'w_member_ref({obj_ref}, "{target.field_name}")'
        val = self.emit_expr(target, out)
        if val.startswith("_t"):
            return f"&{val}"
        tmp = self.new_temp()
        self._declare_owned_var(tmp, self._own_expr(val), out)
        return f"&{tmp}"

    def function_value(self, name, arity, out, environment="w_unit()", captured=False):
        adapter = "w_adapter_" + name
        if adapter not in self.function_adapters:
            self.function_adapters.add(adapter)
            self.fn_prototypes.append(f"static WVal {adapter}(WVal environment, int32_t argc, const WVal* argv);")
            args = ", ".join((["environment"] if captured else []) + [f"argv[{i}]" for i in range(arity)])
            body = f"static WVal {adapter}(WVal environment, int32_t argc, const WVal* argv) {{\n"
            body += "    (void)environment; (void)argv;\n"
            body += f'    if (argc != {arity}) {{ fprintf(stderr, "[W4003] RuntimeError: Call arity mismatch\\n"); exit(1); }}\n'
            body += f"    return w_fn_{name}({args});\n}}"
            self.fn_definitions.append(body)
        return self._bind_call(f"w_function_new({adapter}, {environment})", out)

    def indirect_call(self, callee, args, out):
        function = self.emit_value(callee, out)
        values = [self.emit_value(argument, out) for argument in args]
        array = "(WVal[]){ " + ", ".join(values) + " }" if values else "NULL"
        return self._bind_call(f"w_call({function}, {len(values)}, {array})", out)

    def _is_entrypoint_call(self, stmt) -> bool:
        """True when `stmt` is a direct top-level call whose Result is consumed.

        Such calls return the value of `main` (the `main()` line that closes a W
        program) and their Result must be inspected rather than discarded.
        """
        if not isinstance(stmt, HirExprStmt):
            return False
        expr = stmt.expr
        return isinstance(expr, HirDirectCall) and expr.fn_name == "main"

    def _emit_entrypoint_guard(self, main_stmts: List[str]) -> None:
        """Emits the entrypoint Result check and the mandatory release of `_t_main`.

        W has no stack unwinding: a fallible entrypoint returns its error as a
        value. Discarding it would make a failing program exit 0 with no output,
        which is indistinguishable from success for make/CI/shell.
        """
        main_stmts.append(
            "if (_t_main.tag == W_ERR) { w_report_entrypoint_error(_t_main.as.box->val); "
            "w_release(_t_main); w_runtime_cleanup(); return 1; }"
        )
        main_stmts.append("w_release(_t_main);")

    def emit_expr(self, expr: HirExpr, out: List[str]) -> str:
        if isinstance(expr, HirClosure):
            environment = self.emit_expr(expr.environment, out)
            signature = self.interner.get_entry(expr.type_id)
            return self.function_value(expr.name, len(signature.data[0]), out, self._own_expr(environment), True)
        if isinstance(expr, HirFunctionRef):
            entry = self.interner.get_entry(expr.type_id)
            return self.function_value(expr.name, len(entry.data[0]), out)
        if isinstance(expr, HirIndirectCall):
            return self.indirect_call(expr.callee, expr.args, out)
        if isinstance(expr, HirCoerce):
            val = self.emit_expr(expr.expr, out)
            if expr.kind == "wrap_ok":
                return self._bind_call(f"w_ok({self._own_expr(val)})", out)
            elif expr.kind == "wrap_some":
                return val
            elif expr.kind == "int_to_float":
                return f"w_float((double)({val}).as.i)"
            elif expr.kind == "upcast":
                return val
            return val

        if isinstance(expr, HirConstInt):
            if expr.value == -9223372036854775808:
                return "w_int((-9223372036854775807LL - 1LL))"
            return f"w_int({expr.value}LL)"

        if isinstance(expr, HirConstFloat):
            return f"w_float({repr(expr.value)})"

        if isinstance(expr, HirConstStr):
            return f"w_str_n({self.escape_c_str(expr.value)}, {len(expr.value.encode('utf-8'))})"

        if isinstance(expr, HirConstBool):
            return "w_bool(true)" if expr.value else "w_bool(false)"

        if isinstance(expr, HirConstNone):
            return "w_none()"

        if isinstance(expr, HirConstUnit):
            return "w_unit()"

        if isinstance(expr, HirLocalRef):
            return self.c_var(expr.name, expr.symbol_id)

        if isinstance(expr, HirThisRef):
            return "v_self"

        if isinstance(expr, HirUnaryOp):
            op_val = self.emit_expr(expr.operand, out)
            if expr.op == "-":
                return f"w_neg({op_val})"
            if expr.op == "not":
                return f"w_bool(!({op_val}).as.b)"

        if isinstance(expr, HirBinaryOp):
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
                rhs_stmts: List[str] = []
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
                "+": "w_add", "-": "w_sub", "*": "w_mul", "/": "w_div", "%": "w_mod",
                "<": "w_lt", "<=": "w_le", ">": "w_gt", ">=": "w_ge",
            }
            if expr.op in op_map:
                call = f"{op_map[expr.op]}({lhs}, {rhs})"
                if expr.op == "/":
                    return self._source_call("w_div_at", f"{lhs}, {rhs}", expr)
                if expr.op == "%":
                    return self._source_call("w_mod_at", f"{lhs}, {rhs}", expr)
                return self._bind_call(call, out) if expr.op == "+" else call
            if expr.op == "==":
                return f"w_bool(w_eq({lhs}, {rhs}))"
            if expr.op == "!=":
                return f"w_bool(!w_eq({lhs}, {rhs}))"

        if isinstance(expr, HirConstructStruct):
            if not expr.fields:
                return self._bind_call(f'w_make_struct("{expr.struct_name}", 0, NULL, NULL)', out)
            f_names = [f'"{fname}"' for fname, _ in expr.fields]
            f_vals = [self.emit_value(fval, out) for _, fval in expr.fields]
            k_tmp = self.new_aux("_k")
            v_tmp = self.new_aux("_v")
            out.append(f"const char* {k_tmp}[{len(f_names)}] = {{ {', '.join(f_names)} }};")
            out.append(f"WVal {v_tmp}[{len(f_vals)}] = {{ {', '.join(f_vals)} }};")
            return self._bind_call(f'w_make_struct("{expr.struct_name}", {len(f_names)}, {k_tmp}, {v_tmp})', out)

        if isinstance(expr, HirConstructEnum):
            if (expr.enum_name == "Result" or expr.enum_name.startswith("Result__")) and expr.variant_name == "Ok":
                p_val = self.emit_expr(expr.payload, out) if getattr(expr, "payload", None) is not None else "w_unit()"
                return self._bind_call(f"w_ok({self._own_expr(p_val)})", out)
            if (expr.enum_name == "Result" or expr.enum_name.startswith("Result__")) and expr.variant_name == "Err":
                p_val = self.emit_expr(expr.payload, out) if getattr(expr, "payload", None) is not None else "w_unit()"
                return self._bind_call(f"w_err({self._own_expr(p_val)})", out)
            if (expr.enum_name == "Option" or expr.enum_name.startswith("Option__")) and expr.variant_name in ("None", "none"):
                return "w_none()"
            if getattr(expr, "payload", None) is not None:
                p_val = self.emit_expr(expr.payload, out)
                return self._bind_call(f'w_enum_payload("{expr.enum_name}", "{expr.variant_name}", {self._own_expr(p_val)})', out)
            return f'w_enum("{expr.enum_name}", "{expr.variant_name}")'

        if isinstance(expr, HirConstructObject):
            arg_vals = [self.emit_value(a, out) for a in expr.args]
            return self._bind_call(f"w_new_{expr.class_name}({', '.join(arg_vals)})", out)

        if isinstance(expr, HirConstructList):
            if not expr.elems:
                return self._bind_call("w_make_list(0, NULL)", out)
            elem_vals = [self.emit_value(e, out) for e in expr.elems]
            arr_tmp = self.new_aux("_arr")
            out.append(f"WVal {arr_tmp}[{len(elem_vals)}] = {{ {', '.join(elem_vals)} }};")
            return self._bind_call(f"w_make_list({len(elem_vals)}, {arr_tmp})", out)

        if isinstance(expr, HirConstructTuple):
            if not expr.elems:
                return self._bind_call("w_make_tuple(0, NULL)", out)
            elem_vals = [self.emit_value(e, out) for e in expr.elems]
            arr_tmp = self.new_aux("_arr")
            out.append(f"WVal {arr_tmp}[{len(elem_vals)}] = {{ {', '.join(elem_vals)} }};")
            return self._bind_call(f"w_make_tuple({len(elem_vals)}, {arr_tmp})", out)

        if isinstance(expr, HirConstructDict):
            if not expr.entries:
                return self._bind_call("w_make_dict(0, NULL, NULL)", out)
            pairs = [(self.emit_value(k, out), self.emit_value(v, out)) for k, v in expr.entries]
            k_vals = [key for key, _ in pairs]
            v_vals = [value for _, value in pairs]
            k_tmp = self.new_aux("_k")
            v_tmp = self.new_aux("_v")
            out.append(f"WVal {k_tmp}[{len(k_vals)}] = {{ {', '.join(k_vals)} }};")
            out.append(f"WVal {v_tmp}[{len(v_vals)}] = {{ {', '.join(v_vals)} }};")
            return self._bind_call(f"w_make_dict({len(k_vals)}, {k_tmp}, {v_tmp})", out)

        if isinstance(expr, HirRange):
            s_val = self.emit_value(expr.start, out)
            e_val = self.emit_expr(expr.end, out)
            inc = "true" if expr.inclusive else "false"
            return self._bind_call(f"w_make_range({s_val}, {e_val}, {inc})", out)

        if isinstance(expr, HirFieldRead):
            if isinstance(expr.object, HirLocalRef) and expr.object.name in self.enum_names:
                return f'w_enum("{expr.object.name}", "{expr.field_name}")'
            obj_val = self.emit_expr(expr.object, out)
            return self._bind_call(f'w_clone(w_member_get({obj_val}, "{expr.field_name}"))', out)

        if isinstance(expr, HirIndexRead):
            obj_val = self.emit_value(expr.object, out)
            idx_val = self.emit_expr(expr.index, out)
            call = self._source_call("w_index_get_owned_at", f"{obj_val}, {idx_val}", expr)
            return self._bind_call(call, out)

        if isinstance(expr, HirDirectCall):
            arg_vals = [self.emit_value(a, out) for a in expr.args]
            return self._bind_call(f"w_fn_{expr.fn_name}({', '.join(arg_vals)})", out)

        if isinstance(expr, HirBuiltinCall):
            name = expr.builtin_name
            arg_vals = [self.emit_value(a, out) for a in expr.args]

            if name == "print":
                if not arg_vals:
                    return self._bind_call("w_builtin_print(0, NULL)", out)
                arr_tmp = self.new_aux("_arr")
                out.append(f"WVal {arr_tmp}[{len(arg_vals)}] = {{ {', '.join(arg_vals)} }};")
                return self._bind_call(f"w_builtin_print({len(arg_vals)}, {arr_tmp})", out)

            if name == "eprint":
                if not arg_vals:
                    return self._bind_call("w_builtin_eprint(0, NULL)", out)
                arr_tmp = self.new_aux("_arr")
                out.append(f"WVal {arr_tmp}[{len(arg_vals)}] = {{ {', '.join(arg_vals)} }};")
                return self._bind_call(f"w_builtin_eprint({len(arg_vals)}, {arr_tmp})", out)

            if name == "weak" and len(arg_vals) == 1:
                return self._bind_call(f"w_builtin_weak_owned({self._own_expr(arg_vals[0])})", out)
            builtin_1 = {
                    "weak": "w_builtin_weak", "upgrade": "w_builtin_upgrade",
                "len": "w_builtin_len", "str": "w_builtin_str", "int": "w_builtin_int",
                "float": "w_builtin_float", "ord": "w_builtin_ord", "chr": "w_builtin_chr",
                "bytes": "w_builtin_bytes", "enumerate": "w_builtin_enumerate",
                "dict_items": "w_builtin_dict_items", "read_file": "w_builtin_read_file",
                "exit": "w_builtin_exit"
            }
            if name in builtin_1 and len(arg_vals) == 1:
                return self._bind_call(f"{builtin_1[name]}({arg_vals[0]})", out)

            if name == "args" and len(arg_vals) == 0:
                return self._bind_call("w_builtin_args()", out)

            if name == "write_file" and len(arg_vals) == 2:
                return self._bind_call(f"w_builtin_write_file({arg_vals[0]}, {arg_vals[1]})", out)

            if name == "slice" and len(arg_vals) == 3:
                return self._bind_call(f"w_builtin_slice({arg_vals[0]}, {arg_vals[1]}, {arg_vals[2]})", out)

            return self._bind_call(f"w_builtin_{name}({', '.join(arg_vals)})", out)

        if isinstance(expr, HirMethodCall):
            method = expr.method_name
            # super.init(...) or super.method(...)
            if isinstance(expr.receiver, HirSuperRef):
                arg_vals = [self.emit_value(a, out) for a in expr.args]
                call_args = ["v_self"] + arg_vals
                if self.current_class is not None and self.current_class.superclass is not None:
                    resolved = self._find_class_method(self.current_class.superclass, method)
                    if resolved is not None:
                        def_cls, _ = resolved
                        return self._bind_call(f"w_method_{def_cls}__{method}({', '.join(call_args)})", out)
                return "w_unit()"

            # List/Dict built-in methods
            if method == "append" and len(expr.args) == 1:
                lref = self.emit_lvalue_ref(expr.receiver, out)
                arg_v = self.emit_value(expr.args[0], out)
                return self._bind_call(f"w_list_append({lref}, {arg_v})", out)
            if method == "pop" and len(expr.args) == 0:
                lref = self.emit_lvalue_ref(expr.receiver, out)
                call = self._source_call("w_list_pop_at", lref, expr)
                return self._bind_call(call, out)
            if method == "clear" and len(expr.args) == 0:
                lref = self.emit_lvalue_ref(expr.receiver, out)
                return self._bind_call(f"w_list_clear({lref})", out)
            if method == "get" and len(expr.args) == 1:
                obj_v = self.emit_value(expr.receiver, out)
                arg_v = self.emit_value(expr.args[0], out)
                return self._bind_call(f"w_dict_get({obj_v}, {arg_v})", out)
            if method == "keys" and len(expr.args) == 0:
                obj_v = self.emit_value(expr.receiver, out)
                return self._bind_call(f"w_dict_keys({obj_v})", out)
            if method == "values" and len(expr.args) == 0:
                obj_v = self.emit_value(expr.receiver, out)
                return self._bind_call(f"w_dict_values({obj_v})", out)

            # Dynamic dispatch
            obj_v = self.emit_value(expr.receiver, out)
            arg_vals = [self.emit_value(a, out) for a in expr.args]
            call_args = [obj_v] + arg_vals
            return self._bind_call(f"w_dispatch__{method}__{len(arg_vals)}({', '.join(call_args)})", out)

        if isinstance(expr, HirTryPropagate):
            op_val = self.emit_expr(expr.operand, out)
            tmp = self.new_temp()
            self._declare_owned_var(tmp, self._own_expr(op_val), out)

            none_cleanup: List[str] = []
            self._emit_cleanup_until_fn(none_cleanup)
            channel_enabled = expr.kind == "optional"
            out.append(f"if ({str(channel_enabled).lower()} && ({tmp}.tag == W_NONE || ({tmp}.tag == W_ENUM && strcmp({tmp}.as.en.enum_name, \"Option\") == 0 && strcmp({tmp}.as.en.variant, \"None\") == 0))) {{")
            for cl in none_cleanup:
                out.append(f"    {cl}")
            out.append("    return w_none();")
            out.append("}")

            err_hold = self.new_aux("_err")
            err_cleanup: List[str] = []
            self._emit_cleanup_until_fn(err_cleanup)
            channel_enabled = expr.kind == "result"
            out.append(f"if ({str(channel_enabled).lower()} && ({tmp}.tag == W_ERR || ({tmp}.tag == W_ENUM && strcmp({tmp}.as.en.enum_name, \"Result\") == 0 && strcmp({tmp}.as.en.variant, \"Err\") == 0))) {{")
            out.append(f"    WVal {err_hold} = w_clone({tmp});")
            for cl in err_cleanup:
                out.append(f"    {cl}")
            out.append(f"    return {err_hold};")
            out.append("}")

            unwrapped = self.new_temp()
            helper = "w_unwrap_optional" if expr.kind == "optional" else "w_unwrap_ok"
            self._declare_owned_var(unwrapped, f"{helper}({tmp})", out)
            return unwrapped
        if isinstance(expr, HirCoalesce):
            lhs = self.emit_expr(expr.opt_expr, out)
            res = self.new_temp()
            self._declare_owned_var(res, self._own_expr(lhs), out)
            out.append(f"if ({res}.tag == W_NONE || ({res}.tag == W_ENUM && strcmp({res}.as.en.enum_name, \"Option\") == 0 && strcmp({res}.as.en.variant, \"None\") == 0)) {{")
            self._push_scope("block")
            rhs_stmts: List[str] = []
            rhs = self.emit_expr(expr.fallback_expr, rhs_stmts)
            rhs_stmts.append(f"w_assign(&{res}, {self._own_expr(rhs)});")
            self._pop_scope(rhs_stmts)
            for s in rhs_stmts:
                out.append(f"    {s}")
            out.append("} else {")
            out.append(f"    w_assign(&{res}, w_unwrap_optional({res}));")
            out.append("}")
            return res

        if isinstance(expr, HirElseHandle):
            op_val = self.emit_expr(expr.operand, out)
            tmp = self.new_temp()
            self._declare_owned_var(tmp, self._own_expr(op_val), out)
            res = self.new_temp()
            self._declare_owned_var(res, "w_unit()", out)
            out.append(f"if ({tmp}.tag == W_ERR || {tmp}.tag == W_NONE || ({tmp}.tag == W_ENUM && (strcmp({tmp}.as.en.variant, \"Err\") == 0 || strcmp({tmp}.as.en.variant, \"None\") == 0))) {{")
            self._push_scope("block")
            handler_stmts: List[str] = []
            if expr.err_var is not None:
                c_err = self.c_var_decl(expr.err_var, getattr(expr, "symbol_id", None))
                self._declare_owned_var(c_err, f"w_unwrap_err({tmp})", handler_stmts)
            h_val = self.emit_block_value(expr.handler, handler_stmts)
            handler_stmts.append(f"w_assign(&{res}, {self._own_expr(h_val)});")
            self._pop_scope(handler_stmts)
            for s in handler_stmts:
                out.append(f"    {s}")
            out.append("} else {")
            out.append(f"    w_assign(&{res}, w_unwrap_success({tmp}));")
            out.append("}")
            return res

        if isinstance(expr, HirIf):
            res = self.new_temp()
            self._declare_owned_var(res, "w_unit()", out)
            cond_v = self.emit_expr(expr.cond, out)
            out.append(f"if (({cond_v}).as.b) {{")
            self._push_scope("block")
            then_stmts: List[str] = []
            then_v = self.emit_block_value(expr.then_block, then_stmts)
            then_stmts.append(f"w_assign(&{res}, {self._own_expr(then_v)});")
            self._pop_scope(then_stmts)
            for s in then_stmts:
                out.append(f"    {s}")
            out.append("}")
            self._emit_elifs(expr.elifs, 0, expr.else_block, res, out)
            return res

        if isinstance(expr, HirMatch):
            subj_v = self.emit_expr(expr.subject, out)
            subj_tmp = self.new_temp()
            self._declare_owned_var(subj_tmp, self._own_expr(subj_v), out)
            res = self.new_temp()
            self._declare_owned_var(res, "w_unit()", out)
            self._emit_match_arms(expr.arms, 0, subj_tmp, res, out)
            return res

        raise WError(f"Unsupported HIR expression: {type(expr).__name__}",
                     line=expr.span.line, col=expr.span.col, file=self.file_path,
                     code="W9999", stage="codegen")

    def _emit_elifs(
        self,
        elifs: List[Tuple[HirExpr, HirBlock]],
        idx: int,
        else_block: Optional[HirBlock],
        res_var: str,
        out: List[str]
    ) -> None:
        if idx < len(elifs):
            cond_expr, body_block = elifs[idx]
            out.append("else {")
            self._push_scope("block")
            inner: List[str] = []
            eb_cond = self.emit_expr(cond_expr, inner)
            inner.append(f"if (({eb_cond}).as.b) {{")
            self._push_scope("block")
            eb_stmts: List[str] = []
            eb_v = self.emit_block_value(body_block, eb_stmts)
            eb_stmts.append(f"w_assign(&{res_var}, {self._own_expr(eb_v)});")
            self._pop_scope(eb_stmts)
            for s in eb_stmts:
                inner.append(f"    {s}")
            inner.append("}")
            self._emit_elifs(elifs, idx + 1, else_block, res_var, inner)
            self._pop_scope(inner)
            for s in inner:
                out.append(f"    {s}")
            out.append("}")
        elif else_block is not None:
            out.append("else {")
            self._push_scope("block")
            else_stmts: List[str] = []
            else_v = self.emit_block_value(else_block, else_stmts)
            else_stmts.append(f"w_assign(&{res_var}, {self._own_expr(else_v)});")
            self._pop_scope(else_stmts)
            for s in else_stmts:
                out.append(f"    {s}")
            out.append("}")

    def _emit_match_arms(self, arms: List[HirMatchArm], idx: int, subj_tmp: str, res_var: str, out: List[str]) -> None:
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
        if cond_str == "true":
            out.append("{")
            self._push_scope("block")
            inner: List[str] = []
            self._emit_pattern_bindings(arm.pattern, subj_tmp, inner)
            arm_v = self.emit_block_value(arm.body, inner)
            inner.append(f"w_assign(&{res_var}, {self._own_expr(arm_v)});")
            self._pop_scope(inner)
            for s in inner:
                out.append(f"    {s}")
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
        out.append("} else {")
        self._push_scope("block")
        else_stmts: List[str] = []
        self._emit_match_arms(arms, idx + 1, subj_tmp, res_var, else_stmts)
        self._pop_scope(else_stmts)
        for s in else_stmts:
            out.append(f"    {s}")
        out.append("}")

    def _emit_pattern_bindings(self, pattern: HirPattern, val_expr: str, out: List[str]) -> None:
        if isinstance(pattern, HirBindingPattern):
            if pattern.name not in ("None", "none"):
                c_name = self.c_var_decl(pattern.name, pattern.symbol_id)
                self._declare_owned_var(c_name, f"w_clone({val_expr})", out)
        elif isinstance(pattern, HirTuplePattern):
            for idx, elem_pat in enumerate(pattern.elements):
                sub_expr = f"({val_expr}).as.tuple->items[{idx}]"
                self._emit_pattern_bindings(elem_pat, sub_expr, out)
        elif isinstance(pattern, HirEnumPattern):
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

    def _emit_pattern_cond(self, pattern: HirPattern, val_expr: str, out: List[str]) -> str:
        if isinstance(pattern, HirWildcardPattern):
            return "true"
        if isinstance(pattern, HirBindingPattern):
            if pattern.name in ("None", "none"):
                return f"(({val_expr}).tag == W_NONE || (({val_expr}).tag == W_ENUM && strcmp(({val_expr}).as.en.enum_name, \"Option\") == 0 && strcmp(({val_expr}).as.en.variant, \"None\") == 0))"
            return "true"
        if isinstance(pattern, HirLiteralPattern):
            lit_v = self.emit_expr(pattern.expr, out)
            return f"w_eq({val_expr}, {lit_v})"
        if isinstance(pattern, HirEnumPattern):
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
                conds.append(f"(w_builtin_name(({val_expr}).as.en.enum_name, \"{pattern.enum_name}\"))")
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

        if isinstance(pattern, HirTuplePattern):
            conds = [f"(({val_expr}).tag == W_TUPLE && ({val_expr}).as.tuple->len == {len(pattern.elements)})"]
            for idx, elem_pat in enumerate(pattern.elements):
                sub_c = self._emit_pattern_cond(elem_pat, f"({val_expr}).as.tuple->items[{idx}]", out)
                if sub_c != "true":
                    conds.append(sub_c)
            return "(" + " && ".join(conds) + ")"
        return "true"
