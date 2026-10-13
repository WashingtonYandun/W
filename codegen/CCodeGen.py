import os
from typing import Dict, List, Optional, Set, Tuple
from node.NodeType import (
    Program, Stmt, Expr, TypeNode, ResultType,
    Pattern, IdentifierPattern, TuplePattern, EnumPattern, LiteralPattern, WildcardPattern,
    Block, ExprStmt, Param, FnDecl, StructDecl, EnumDecl, ImportDecl,
    LetDecl, WhileStmt, ForStmt, ReturnStmt, BreakStmt, ContinueStmt,
    IntLiteral, FloatLiteral, StringLiteral, BoolLiteral, NoneLiteral, IdentExpr,
    UnaryExpr, BinaryExpr, CoalesceExpr, RangeExpr, PostfixTryExpr, ElseErrExpr,
    CallExpr, MemberExpr, IndexExpr, AssignmentExpr, StructInitExpr,
    ListExpr, DictExpr, TupleExpr, IfExpr, MatchExpr
)
from parser.Parser import Parser


class CCodeGen:
    """
    Canonical W v0.1 to C99 Transpiler Backend.
    Preserves exact value semantics (ARC + Copy-on-Write via runtime/w_runtime.h),
    deterministic control flow, pattern matching, and fallible error handling.
    """
    def __init__(self, file: str = "<stdin>"):
        self.file = file
        self.temp_counter = 0
        self.enum_names: Set[str] = set()
        self.fallible_fns: Dict[str, bool] = {}
        self.current_fn_fallible: bool = False
        self.current_ns: str = ""
        self.imported_modules: Set[str] = set()
        self.global_vars: List[str] = []
        self.fn_Prototypes: List[str] = []
        self.fn_Definitions: List[str] = []

    def new_temp(self) -> str:
        name = f"_t{self.temp_counter}"
        self.temp_counter += 1
        return name

    def c_var(self, name: str) -> str:
        if self.current_ns and f"v_{self.current_ns}_{name}" in self.global_vars:
            return f"v_{self.current_ns}_{name}"
        return f"v_{name}"

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
        self._collect_declarations(program, ns="")

        # Emit all top-level functions (and imported module functions)
        main_stmts: List[str] = []
        self._emit_module_body(program, ns="", out_main_stmts=main_stmts)

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

        # If there are no top-level executable statements and main() exists in W, call it
        non_decls = [s for s in program.body if not isinstance(s, (FnDecl, StructDecl, EnumDecl, ImportDecl))]
        if not non_decls and "w_fn_main" in self.fallible_fns:
            lines.append("    w_fn_main();")

        lines.append("    return 0;")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _collect_declarations(self, program: Program, ns: str) -> None:
        for stmt in program.body:
            if isinstance(stmt, EnumDecl):
                self.enum_names.add(stmt.name)
            elif isinstance(stmt, FnDecl):
                c_name = self.c_fn(stmt.name, ns=ns)
                is_fallible = isinstance(stmt.return_type, ResultType)
                self.fallible_fns[c_name] = is_fallible
                params_sig = ", ".join([f"WVal v_{p.name}" for p in stmt.params]) if stmt.params else "void"
                self.fn_Prototypes.append(f"static WVal {c_name}({params_sig});")
            elif isinstance(stmt, LetDecl):
                gv_name = f"v_{ns}_{stmt.name}" if ns else f"v_{stmt.name}"
                if gv_name not in self.global_vars:
                    self.global_vars.append(gv_name)

    def _emit_module_body(self, program: Program, ns: str, out_main_stmts: List[str]) -> None:
        prev_ns = self.current_ns
        self.current_ns = ns

        for stmt in program.body:
            if isinstance(stmt, ImportDecl):
                self._handle_import(stmt, out_main_stmts)
            elif isinstance(stmt, FnDecl):
                self._emit_fn_decl(stmt, ns=ns)

        for stmt in program.body:
            if not isinstance(stmt, (FnDecl, StructDecl, EnumDecl, ImportDecl)):
                if isinstance(stmt, LetDecl):
                    gv_name = f"v_{ns}_{stmt.name}" if ns else f"v_{stmt.name}"
                    val_expr = self.emit_expr(stmt.initializer, out_main_stmts)
                    out_main_stmts.append(f"{gv_name} = w_clone({val_expr});")
                else:
                    self.emit_stmt(stmt, out_main_stmts)

        self.current_ns = prev_ns

    def _handle_import(self, stmt: ImportDecl, out_main_stmts: List[str]) -> None:
        current_dir = os.path.dirname(os.path.abspath(self.file)) if self.file != "<stdin>" else os.getcwd()
        resolved_path = os.path.join(current_dir, stmt.path)
        if not os.path.exists(resolved_path):
            resolved_path = stmt.path
        abs_path = os.path.abspath(resolved_path)
        if abs_path in self.imported_modules:
            return
        self.imported_modules.add(abs_path)

        with open(abs_path, "r", encoding="utf-8") as f:
            code = f.read()

        sub_ast = Parser(file=abs_path).parse(code)
        prev_file = self.file
        self.file = abs_path
        self._collect_declarations(sub_ast, ns=stmt.namespace)
        self._emit_module_body(sub_ast, ns=stmt.namespace, out_main_stmts=out_main_stmts)
        self.file = prev_file

    def _emit_fn_decl(self, stmt: FnDecl, ns: str) -> None:
        c_name = self.c_fn(stmt.name, ns=ns)
        params_sig = ", ".join([f"WVal v_{p.name}" for p in stmt.params]) if stmt.params else "void"
        prev_fallible = self.current_fn_fallible
        self.current_fn_fallible = isinstance(stmt.return_type, ResultType)

        body_stmts: List[str] = []
        # Clone parameters to preserve local CoW ownership
        for p in stmt.params:
            body_stmts.append(f"v_{p.name} = w_clone(v_{p.name});")

        ret_expr = self.emit_block_value(stmt.body, body_stmts)
        if self.current_fn_fallible:
            body_stmts.append(f"return w_ok({ret_expr});")
        else:
            body_stmts.append(f"return {ret_expr};")

        fn_lines = [f"static WVal {c_name}({params_sig}) {{"]
        for s in body_stmts:
            fn_lines.append(f"    {s}")
        fn_lines.append("}")
        self.fn_Definitions.append("\n".join(fn_lines))
        self.current_fn_fallible = prev_fallible

    # ==========================================
    # Statement Emission
    # ==========================================

    def emit_block_value(self, block: Block, out: List[str]) -> str:
        res_var = self.new_temp()
        out.append(f"WVal {res_var} = w_unit();")
        inner: List[str] = []
        for s in block.statements:
            self.emit_stmt(s, inner)
        if block.tail_expr is not None:
            tail_val = self.emit_expr(block.tail_expr, inner)
            inner.append(f"{res_var} = {tail_val};")
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
            out.append(f"WVal v_{stmt.name} = w_clone({val});")
            return

        if isinstance(stmt, ReturnStmt):
            if stmt.value is not None:
                val = self.emit_expr(stmt.value, out)
                if self.current_fn_fallible:
                    out.append(f"return w_ok({val});")
                else:
                    out.append(f"return {val};")
            else:
                if self.current_fn_fallible:
                    out.append("return w_ok(w_unit());")
                else:
                    out.append("return w_unit();")
            return

        if isinstance(stmt, BreakStmt):
            out.append("break;")
            return

        if isinstance(stmt, ContinueStmt):
            out.append("continue;")
            return

        if isinstance(stmt, WhileStmt):
            out.append("while (1) {")
            loop_inner: List[str] = []
            cond_val = self.emit_expr(stmt.condition, loop_inner)
            loop_inner.append(f"if (!({cond_val}).as.b) break;")
            body_v = self.emit_block_value(stmt.body, loop_inner)
            loop_inner.append(f"(void){body_v};")
            for line in loop_inner:
                out.append(f"    {line}")
            out.append("}")
            return

        if isinstance(stmt, ForStmt):
            iter_val = self.emit_expr(stmt.iterable, out)
            iter_tmp = self.new_temp()
            idx_tmp = self.new_temp()
            item_tmp = self.new_temp()
            out.append(f"WVal {iter_tmp} = w_clone({iter_val});")
            out.append(f"for (int32_t {idx_tmp} = 0; {idx_tmp} < {iter_tmp}.as.list->len; {idx_tmp}++) {{")
            loop_inner = [f"WVal {item_tmp} = {iter_tmp}.as.list->data[{idx_tmp}];"]
            self._emit_pattern_bindings(stmt.pattern, item_tmp, loop_inner)
            body_v = self.emit_block_value(stmt.body, loop_inner)
            loop_inner.append(f"(void){body_v};")
            for line in loop_inner:
                out.append(f"    {line}")
            out.append("}")
            return

    def _emit_pattern_bindings(self, pattern: Pattern, val_expr: str, out: List[str]) -> None:
        if isinstance(pattern, IdentifierPattern):
            out.append(f"WVal v_{pattern.name} = w_clone({val_expr});")
        elif isinstance(pattern, TuplePattern):
            for idx, elem_pat in enumerate(pattern.elements):
                sub_expr = f"({val_expr}).as.tuple->items[{idx}]"
                self._emit_pattern_bindings(elem_pat, sub_expr, out)

    def _emit_pattern_cond(self, pattern: Pattern, val_expr: str, out: List[str]) -> str:
        if isinstance(pattern, (WildcardPattern, IdentifierPattern)):
            return "true"
        if isinstance(pattern, LiteralPattern):
            lit_v = self.emit_expr(pattern.literal, out)
            return f"w_eq({val_expr}, {lit_v})"
        if isinstance(pattern, EnumPattern):
            en_v = f'w_enum("{pattern.enum_name}", "{pattern.variant}")'
            return f"w_eq({val_expr}, {en_v})"
        if isinstance(pattern, TuplePattern):
            conds: List[str] = [f"(({val_expr}).tag == W_TUPLE && ({val_expr}).as.tuple->len == {len(pattern.elements)})"]
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
        if isinstance(target, IdentExpr):
            return f"&{self.c_var(target.name)}"
        if isinstance(target, IndexExpr):
            obj_ref = self.emit_lvalue_ref(target.object, out)
            idx_val = self.emit_expr(target.index, out)
            return f"w_index_ref({obj_ref}, {idx_val})"
        if isinstance(target, MemberExpr):
            obj_ref = self.emit_lvalue_ref(target.object, out)
            return f'w_member_ref({obj_ref}, "{target.property}")'
        # Fallback for temporary receiver
        val = self.emit_expr(target, out)
        tmp = self.new_temp()
        out.append(f"WVal {tmp} = {val};")
        return f"&{tmp}"

    def emit_expr(self, expr: Expr, out: List[str]) -> str:
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

        if isinstance(expr, IdentExpr):
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
                out.append(f"WVal {res} = w_bool(false);")
                out.append(f"if (({lhs}).as.b) {{")
                rhs_stmts: List[str] = []
                rhs = self.emit_expr(expr.right, rhs_stmts)
                for s in rhs_stmts:
                    out.append(f"    {s}")
                out.append(f"    {res} = w_bool(({rhs}).as.b);")
                out.append("}")
                return res

            if expr.op == "or":
                lhs = self.emit_expr(expr.left, out)
                res = self.new_temp()
                out.append(f"WVal {res} = w_bool(true);")
                out.append(f"if (!({lhs}).as.b) {{")
                rhs_stmts = []
                rhs = self.emit_expr(expr.right, rhs_stmts)
                for s in rhs_stmts:
                    out.append(f"    {s}")
                out.append(f"    {res} = w_bool(({rhs}).as.b);")
                out.append("}")
                return res

            lhs = self.emit_expr(expr.left, out)
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
                return f"{op_map[expr.op]}({lhs}, {rhs})"
            if expr.op == "==":
                return f"w_bool(w_eq({lhs}, {rhs}))"
            if expr.op == "!=":
                return f"w_bool(!w_eq({lhs}, {rhs}))"

        if isinstance(expr, CoalesceExpr):
            res = self.new_temp()
            lhs = self.emit_expr(expr.left, out)
            out.append(f"WVal {res} = {lhs};")
            out.append(f"if ({res}.tag == W_NONE) {{")
            rhs_stmts = []
            rhs = self.emit_expr(expr.right, rhs_stmts)
            for s in rhs_stmts:
                out.append(f"    {s}")
            out.append(f"    {res} = {rhs};")
            out.append("}")
            return res

        if isinstance(expr, RangeExpr):
            s_val = self.emit_expr(expr.start, out)
            e_val = self.emit_expr(expr.end, out)
            inc = "true" if expr.inclusive else "false"
            return f"w_make_range({s_val}, {e_val}, {inc})"

        if isinstance(expr, PostfixTryExpr):
            op_val = self.emit_expr(expr.operand, out)
            tmp = self.new_temp()
            unwrapped = self.new_temp()
            out.append(f"WVal {tmp} = {op_val};")
            out.append(f"if ({tmp}.tag == W_NONE) return w_none();")
            out.append(f"if ({tmp}.tag == W_ERR) return {tmp};")
            out.append(f"WVal {unwrapped} = ({tmp}.tag == W_OK) ? *({tmp}.as.box) : {tmp};")
            return unwrapped

        if isinstance(expr, ElseErrExpr):
            op_val = self.emit_expr(expr.operand, out)
            tmp = self.new_temp()
            res = self.new_temp()
            out.append(f"WVal {tmp} = {op_val};")
            out.append(f"WVal {res} = w_unit();")
            out.append(f"if ({tmp}.tag == W_ERR || {tmp}.tag == W_NONE) {{")
            handler_stmts: List[str] = []
            if expr.err_name is not None:
                handler_stmts.append(f"WVal v_{expr.err_name} = ({tmp}.tag == W_ERR) ? *({tmp}.as.box) : w_none();")
            h_val = self.emit_block_value(expr.handler, handler_stmts)
            handler_stmts.append(f"{res} = {h_val};")
            for s in handler_stmts:
                out.append(f"    {s}")
            out.append("} else {")
            out.append(f"    {res} = ({tmp}.tag == W_OK) ? *({tmp}.as.box) : {tmp};")
            out.append("}")
            return res

        if isinstance(expr, AssignmentExpr):
            val = self.emit_expr(expr.value, out)
            if isinstance(expr.target, IdentExpr):
                c_target = self.c_var(expr.target.name)
                out.append(f"{c_target} = w_clone({val});")
                return c_target
            lref = self.emit_lvalue_ref(expr.target, out)
            tmp = self.new_temp()
            out.append(f"WVal {tmp} = w_clone({val});")
            out.append(f"*({lref}) = {tmp};")
            return tmp

        if isinstance(expr, MemberExpr):
            if isinstance(expr.object, IdentExpr):
                if expr.object.name in self.enum_names:
                    return f'w_enum("{expr.object.name}", "{expr.property}")'
                if f"v_{expr.object.name}_{expr.property}" in self.global_vars:
                    return f"v_{expr.object.name}_{expr.property}"
            obj_val = self.emit_expr(expr.object, out)
            return f'w_member_get({obj_val}, "{expr.property}")'

        if isinstance(expr, IndexExpr):
            obj_val = self.emit_expr(expr.object, out)
            idx_val = self.emit_expr(expr.index, out)
            return f"w_index_get({obj_val}, {idx_val})"

        if isinstance(expr, CallExpr):
            # 1. Built-in or top-level function call
            if isinstance(expr.callee, IdentExpr):
                fn_name = expr.callee.name
                arg_vals = [self.emit_expr(a, out) for a in expr.args]

                if fn_name == "print":
                    if not arg_vals:
                        return "w_builtin_print(0, NULL)"
                    arr_tmp = self.new_temp()
                    elems_c = ", ".join(arg_vals)
                    out.append(f"WVal {arr_tmp}[{len(arg_vals)}] = {{ {elems_c} }};")
                    return f"w_builtin_print({len(arg_vals)}, {arr_tmp})"

                builtin_1 = {
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
                    return f"{builtin_1[fn_name]}({arg_vals[0]})"

                if fn_name == "args" and len(arg_vals) == 0:
                    return "w_builtin_args()"

                if fn_name == "write_file" and len(arg_vals) == 2:
                    return f"w_builtin_write_file({arg_vals[0]}, {arg_vals[1]})"

                if fn_name == "slice" and len(arg_vals) == 3:
                    return f"w_builtin_slice({arg_vals[0]}, {arg_vals[1]}, {arg_vals[2]})"

                c_callee = self.c_fn(fn_name)
                return f"{c_callee}({', '.join(arg_vals)})"

            # 2. Method call or module function call: obj.method(...)
            if isinstance(expr.callee, MemberExpr):
                obj_expr = expr.callee.object
                method = expr.callee.property

                # Check if module call: mod.fn(...)
                if isinstance(obj_expr, IdentExpr):
                    mod_fn = self.c_fn(method, ns=obj_expr.name)
                    if mod_fn in self.fallible_fns:
                        arg_vals = [self.emit_expr(a, out) for a in expr.args]
                        return f"{mod_fn}({', '.join(arg_vals)})"

                # Collection methods
                if method == "append":
                    lref = self.emit_lvalue_ref(obj_expr, out)
                    arg_v = self.emit_expr(expr.args[0], out)
                    return f"w_list_append({lref}, {arg_v})"
                if method == "pop":
                    lref = self.emit_lvalue_ref(obj_expr, out)
                    return f"w_list_pop({lref})"
                if method == "clear":
                    lref = self.emit_lvalue_ref(obj_expr, out)
                    return f"w_list_clear({lref})"
                if method == "get":
                    obj_v = self.emit_expr(obj_expr, out)
                    arg_v = self.emit_expr(expr.args[0], out)
                    return f"w_dict_get({obj_v}, {arg_v})"
                if method == "keys":
                    obj_v = self.emit_expr(obj_expr, out)
                    return f"w_dict_keys({obj_v})"
                if method == "values":
                    obj_v = self.emit_expr(obj_expr, out)
                    return f"w_dict_values({obj_v})"

        if isinstance(expr, ListExpr):
            if not expr.elements:
                return "w_make_list(0, NULL)"
            elem_vals = [self.emit_expr(e, out) for e in expr.elements]
            arr_tmp = self.new_temp()
            out.append(f"WVal {arr_tmp}[{len(elem_vals)}] = {{ {', '.join(elem_vals)} }};")
            return f"w_make_list({len(elem_vals)}, {arr_tmp})"

        if isinstance(expr, TupleExpr):
            elem_vals = [self.emit_expr(e, out) for e in expr.elements]
            arr_tmp = self.new_temp()
            out.append(f"WVal {arr_tmp}[{len(elem_vals)}] = {{ {', '.join(elem_vals)} }};")
            return f"w_make_tuple({len(elem_vals)}, {arr_tmp})"

        if isinstance(expr, DictExpr):
            if not expr.entries:
                return "w_make_dict(0, NULL, NULL)"
            k_vals = [self.emit_expr(e.key, out) for e in expr.entries]
            v_vals = [self.emit_expr(e.value, out) for e in expr.entries]
            k_tmp = self.new_temp()
            v_tmp = self.new_temp()
            out.append(f"WVal {k_tmp}[{len(k_vals)}] = {{ {', '.join(k_vals)} }};")
            out.append(f"WVal {v_tmp}[{len(v_vals)}] = {{ {', '.join(v_vals)} }};")
            return f"w_make_dict({len(k_vals)}, {k_tmp}, {v_tmp})"

        if isinstance(expr, StructInitExpr):
            if not expr.fields:
                return f'w_make_struct("{expr.struct_name}", 0, NULL, NULL)'
            f_names = [f'"{f.name}"' for f in expr.fields]
            f_vals = [self.emit_expr(f.value, out) for f in expr.fields]
            k_tmp = self.new_temp()
            v_tmp = self.new_temp()
            out.append(f"const char* {k_tmp}[{len(f_names)}] = {{ {', '.join(f_names)} }};")
            out.append(f"WVal {v_tmp}[{len(f_vals)}] = {{ {', '.join(f_vals)} }};")
            return f'w_make_struct("{expr.struct_name}", {len(f_names)}, {k_tmp}, {v_tmp})'

        if isinstance(expr, IfExpr):
            res = self.new_temp()
            out.append(f"WVal {res} = w_unit();")
            cond_v = self.emit_expr(expr.condition, out)
            out.append(f"if (({cond_v}).as.b) {{")
            then_stmts: List[str] = []
            then_v = self.emit_block_value(expr.then_branch, then_stmts)
            then_stmts.append(f"{res} = {then_v};")
            for s in then_stmts:
                out.append(f"    {s}")
            out.append("}")

            # Handle elif and else branches with nested else blocks so elif conditions evaluate lazily
            self._emit_elif_chain(expr.elif_branches, 0, expr.else_branch, res, out)
            return res

        if isinstance(expr, MatchExpr):
            subj_v = self.emit_expr(expr.subject, out)
            subj_tmp = self.new_temp()
            res = self.new_temp()
            out.append(f"WVal {subj_tmp} = {subj_v};")
            out.append(f"WVal {res} = w_unit();")
            self._emit_match_arms(expr.arms, 0, subj_tmp, res, out)
            return res

        return "w_unit()"

    def _emit_elif_chain(self, elifs: List, idx: int, else_branch: Optional[Block], res_var: str, out: List[str]) -> None:
        if idx < len(elifs):
            eb = elifs[idx]
            out.append("else {")
            inner: List[str] = []
            eb_cond = self.emit_expr(eb.condition, inner)
            inner.append(f"if (({eb_cond}).as.b) {{")
            eb_stmts: List[str] = []
            eb_v = self.emit_block_value(eb.body, eb_stmts)
            eb_stmts.append(f"{res_var} = {eb_v};")
            for s in eb_stmts:
                inner.append(f"    {s}")
            inner.append("}")
            self._emit_elif_chain(elifs, idx + 1, else_branch, res_var, inner)
            for s in inner:
                out.append(f"    {s}")
            out.append("}")
        elif else_branch is not None:
            out.append("else {")
            else_stmts: List[str] = []
            else_v = self.emit_block_value(else_branch, else_stmts)
            else_stmts.append(f"{res_var} = {else_v};")
            for s in else_stmts:
                out.append(f"    {s}")
            out.append("}")

    def _emit_match_arms(self, arms: List, idx: int, subj_tmp: str, res_var: str, out: List[str]) -> None:
        if idx >= len(arms):
            return
        arm = arms[idx]
        cond_str = self._emit_pattern_cond(arm.pattern, subj_tmp, out)
        out.append(f"if ({cond_str}) {{")
        arm_stmts: List[str] = []
        self._emit_pattern_bindings(arm.pattern, subj_tmp, arm_stmts)
        arm_v = self.emit_block_value(arm.body, arm_stmts)
        arm_stmts.append(f"{res_var} = {arm_v};")
        for s in arm_stmts:
            out.append(f"    {s}")
        out.append("}")
        if idx + 1 < len(arms):
            out.append("else {")
            else_inner: List[str] = []
            self._emit_match_arms(arms, idx + 1, subj_tmp, res_var, else_inner)
            for s in else_inner:
                out.append(f"    {s}")
            out.append("}")


def compile_to_c(source: str, file: str = "<stdin>") -> str:
    ast = Parser(file=file).parse(source)
    return CCodeGen(file=file).generate(ast)
