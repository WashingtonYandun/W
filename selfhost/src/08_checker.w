fn compile_source(src: str) -> str {
    g_tokens = module_tokens(src, g_in_path)
    g_pos = 0
    g_temp_id = 0
    g_aux_id = 0
    g_fn_fallible = false
    g_cur_err_type = ""
    g_ns = ""
    let empty_s: list[str] = []
    let empty_i: list[int] = []
    let empty_c: list[ClassMeta] = []
    let empty_sc: list[CleanupScope] = []
    g_scope_stack = empty_sc
    g_enums = empty_s
    g_enum_variant_names = empty_s
    g_enum_variant_owners = empty_s
    g_enum_variant_arities = empty_i
    g_pattern_bind_lines = empty_s
    g_pattern_bind_names = empty_s
    g_modules = empty_s
    g_classes = empty_c
    g_dispatch_names = empty_s
    g_dispatch_arities = empty_i
    g_cur_class = ""
    g_cur_super = ""
    g_globals = empty_s
    g_protos = empty_s
    g_fn_defs = empty_s
    g_cur_stmts = empty_s
    let mut has_main_fn = false
    let mut has_main_call = false
    let mut has_top_stmts = false
    push_scope("fn")
    while not is_eof() {
        if match_kind("PUB") { continue }
        if check_kind("EXTERN") { parse_extern_decl() }
        elif check_kind("STRUCT") {
            parse_struct_decl()
        } elif check_kind("ENUM") {
            parse_enum_decl()
        } elif check_kind("INTERFACE") {
            parse_interface_decl()
        } elif check_kind("CLASS") {
            parse_class_decl()
        } elif check_kind("IMPORT") {
            parse_import_decl()
        } elif check_kind("FN") {
            if peek_tok(1).val == "main" {
                has_main_fn = true
            }
            parse_fn_decl()
        } elif check_kind("LET") {
            has_top_stmts = true
            parse_let_stmt(true)
        } elif check_kind("WHILE") {
            has_top_stmts = true
            parse_while_stmt()
        } elif check_kind("FOR") {
            has_top_stmts = true
            parse_for_stmt()
        } else {
            has_top_stmts = true
            # A bare `main()` line at top level returns the entrypoint Result. Its value
            # must be inspected like the implicit form below, or a program whose main
            # returns Err would exit 0 with no output.
            let is_entry_call = check_kind("IDENT") and at_tok().val == "main" and peek_tok(1).kind == "LPAREN"
            let expr_r = parse_expr(0, true)
            if is_entry_call {
                has_main_call = true
                emit_line("WVal _t_main = " + expr_r.val + ";")
                emit_line("if (_t_main.tag == W_ERR) { w_report_entrypoint_error(_t_main.as.box->val); w_release(_t_main); w_runtime_cleanup(); return 1; }")
                emit_line("w_release(_t_main);")
            } else {
                emit_line("(void)" + expr_r.val + ";")
            }
        }
    }
    if has_main_fn and not has_main_call {
        emit_line("WVal _t_main = w_fn_main();")
        emit_line("if (_t_main.tag == W_ERR) { w_report_entrypoint_error(_t_main.as.box->val); w_release(_t_main); w_runtime_cleanup(); return 1; }")
        emit_line("w_release(_t_main);")
    }
    pop_scope()
    emit_oop_dispatchers()
    let mut out = "#include \"runtime/w_runtime.h\"\n\n"
    if len(g_globals) > 0 {
        for gv in g_globals {
            out = out + "static WVal " + gv + ";\n"
        }
        out = out + "\n"
    }
    if len(g_protos) > 0 {
        for pr in g_protos {
            out = out + pr + "\n"
        }
        out = out + "\n"
    }
    if len(g_fn_defs) > 0 {
        for fd in g_fn_defs {
            out = out + fd + "\n\n"
        }
    }
    out = out + "int main(int argc, char** argv) {\n"
    out = out + "    w_init_args(argc, argv);\n"
    for ms in g_cur_stmts {
        out = out + "    " + ms + "\n"
    }
    if len(g_globals) > 0 {
        let mut gi = len(g_globals) - 1
        while gi >= 0 {
            out = out + "    w_release(" + g_globals[gi] + ");\n"
            gi = gi - 1
        }
    }
    out = out + "    w_runtime_cleanup();\n"
    out = out + "    return 0;\n"
    out = out + "}\n"
    return out
}

fn check_delimiters(tokens: list[Token]) -> unit {
    let mut delim_kinds: list[str] = []
    let mut delim_lines: list[int] = []
    let mut delim_cols: list[int] = []
    for tok in tokens {
        let k = tok.kind
        if k == "LPAREN" or k == "LBRACE" or k == "LBRACKET" {
            delim_kinds.append(k)
            delim_lines.append(tok.line)
            delim_cols.append(tok.col)
        } elif k == "RPAREN" {
            let dl = len(delim_kinds)
            if dl == 0 {
                report_error("W0001", tok.line, tok.col, "unexpected ')'")
            }
            let top = delim_kinds[dl - 1]
            if top != "LPAREN" {
                report_error("W0001", tok.line, tok.col, "mismatched delimiter ')'")
            }
            delim_kinds.pop()
            delim_lines.pop()
            delim_cols.pop()
        } elif k == "RBRACKET" {
            let dl = len(delim_kinds)
            if dl == 0 {
                report_error("W0006", tok.line, tok.col, "unexpected ']'")
            }
            let top = delim_kinds[dl - 1]
            if top != "LBRACKET" {
                report_error("W0006", tok.line, tok.col, "mismatched delimiter ']'")
            }
            delim_kinds.pop()
            delim_lines.pop()
            delim_cols.pop()
        } elif k == "RBRACE" {
            let dl = len(delim_kinds)
            if dl == 0 {
                report_error("W0006", tok.line, tok.col, "unexpected '}'")
            }
            let top = delim_kinds[dl - 1]
            if top == "LPAREN" {
                report_error("W0006", tok.line, tok.col, "expected ')' before '}'")
            }
            if top != "LBRACE" {
                report_error("W0006", tok.line, tok.col, "mismatched delimiter '}'")
            }
            delim_kinds.pop()
            delim_lines.pop()
            delim_cols.pop()
        }
    }
    if len(delim_kinds) > 0 {
        let top_idx = len(delim_kinds) - 1
        let top_k = delim_kinds[top_idx]
        if top_k == "LBRACE" {
            report_error("W0006", delim_lines[top_idx], delim_cols[top_idx], "unclosed delimiter '{'")
        } elif top_k == "LPAREN" {
            report_error("W0006", delim_lines[top_idx], delim_cols[top_idx], "unclosed delimiter '('")
        } elif top_k == "LBRACKET" {
            report_error("W0006", delim_lines[top_idx], delim_cols[top_idx], "unclosed delimiter '['")
        }
    }
}

fn check_source(src: str, in_path: str) -> unit {
    g_in_path = in_path
    let tokens = module_tokens(src, in_path)
    let n = len(tokens)
    if n == 0 {
        return
    }
    check_delimiters(tokens)
    sem_validate(tokens)
}
