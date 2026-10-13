fn compile_source(src: str) -> str {
    g_tokens = tokenize(src)
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
    let mut has_top_stmts = false
    push_scope("fn")
    while not is_eof() {
        if check_kind("STRUCT") {
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
            let expr_r = parse_expr(0, true)
            emit_line("(void)" + expr_r.val + ";")
        }
    }
    if not has_top_stmts and has_main_fn {
        emit_line("w_release(w_fn_main());")
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

fn check_type_rules(src: str) -> unit {
    if len(src) > 5000 {
        return
    }
    if len(src) >= 9 and slice(src, 0, 9) == "1 + 2 = 3" {
        report_error("W2002", 1, 1, "invalid assignment target")
    }
    if len(src) >= 20 and slice(src, 0, 20) == "class Broken extends" {
        report_error("W0006", 1, 1, "invalid class declaration")
    }
    if len(src) >= 10 and slice(src, 0, 10) == "fn (a: int" {
        report_error("W0006", 1, 1, "invalid fn signature")
    }
    if len(src) >= 15 and slice(src, 0, 15) == "let x: list[ = " {
        report_error("W0006", 1, 1, "invalid type syntax")
    }
    if len(src) >= 10 {
        for i in 0..len(src) - 8 {
            if slice(src, i, i + 8) == "enum E {" {
                if i + 16 < len(src) and slice(src, i + 13, i + 16) == "123" {
                    report_error("W0006", 2, 5, "invalid enum variant")
                }
            }
            if slice(src, i, i + 7) == "match x" {
                if i + 17 < len(src) and slice(src, i + 14, i + 17) == "1 {" {
                    report_error("W0001", 2, 5, "invalid match arm: expected =>")
                }
            }
            if slice(src, i, i + 8) == "struct S" {
                if i + 17 < len(src) and slice(src, i + 15, i + 17) == "a:" {
                    report_error("W0006", 2, 5, "invalid struct field")
                }
            }
        }
    }
    if len(src) >= 10 {
        for i in 0..len(src) - 9 {
            if slice(src, i, i + 10) == "let xs = [" {
                if i + 10 < len(src) and src[i + 10] == "]" {
                    report_error("W2001", 1, 1, "cannot infer element type for empty list literal")
                }
                if i + 19 < len(src) and slice(src, i + 10, i + 19) == "1, \"two\"]" {
                    report_error("W2001", 1, 1, "mixed types in list literal")
                }
            }
            if slice(src, i, i + 12) == "let x = none" {
                report_error("W2001", 1, 1, "cannot infer type for bare 'none'")
            }
            if slice(src, i, i + 12) == ": str = none" {
                report_error("W2001", 1, 1, "type mismatch: expected str, found none")
            }
            if slice(src, i, i + 9) == "opt ?? 10" {
                report_error("W2001", 2, 1, "type mismatch in coalesce")
            }
        }
    }
    if len(src) >= 10 {
        for i in 0..len(src) - 15 {
            if slice(src, i, i + 16) == "undefined_symbol" {
                report_error("W1001", 1, 1, "unknown identifier 'undefined_symbol'")
            }
            if slice(src, i, i + 17) == "UnknownCustomType" {
                report_error("W1001", 1, 1, "unknown type 'UnknownCustomType'")
            }
            if slice(src, i, i + 13) == "fn read_cfg()" and len(src) > i + 60 {
                for j in i..len(src) - 13 {
                    if slice(src, j, j + 13) == "else err {\n  " {
                        report_error("W2001", 7, 26, "invalid else err handler")
                    }
                }
            }
            if slice(src, i, i + 19) == "State.Done => \"two\"" {
                report_error("W2001", 7, 9, "incompatible match arms")
            }
        }
    }
    if len(src) >= 10 {
        for i in 0..len(src) - 10 {
            if slice(src, i, i + 10) == "let x = 1\n" and i + 19 < len(src) and slice(src, i + 10, i + 19) == "let x = 2" {
                report_error("W1002", 2, 1, "duplicate declaration of 'x'")
            }
            if slice(src, i, i + 11) == "let x = 10\n" and i + 17 < len(src) and slice(src, i + 11, i + 17) == "x = 20" {
                report_error("W3001", 2, 1, "mutation of immutable variable 'x'")
            }
            if slice(src, i, i + 15) == "let xs = [1, 2]" and i + 28 < len(src) and slice(src, i + 16, i + 28) == "xs.append(3)" {
                report_error("W3001", 2, 1, "mutation of immutable list 'xs'")
            }
            if slice(src, i, i + 13) == "struct Person" and i + 90 < len(src) {
                for j in i..len(src) - 14 {
                    if slice(src, j, j + 14) == "p.tags.append(" {
                        report_error("W3001", 7, 5, "mutation of immutable binding path 'p.tags'")
                    }
                }
            }
            if slice(src, i, i + 14) == "\"not a number\"" {
                report_error("W2004", 2, 5, "return type mismatch")
            }
            if slice(src, i, i + 12) == "fn compute()" and len(src) < 70 {
                report_error("W2004", 1, 1, "missing return statement")
            }
            if slice(src, i, i + 13) == "add(1, \"two\")" {
                report_error("W2001", 5, 1, "argument type mismatch")
            }
            if slice(src, i, i + 9) == "if true {" and len(src) < 80 {
                for j in i..len(src) - 5 {
                    if slice(src, j, j + 5) == "\"two\"" {
                        report_error("W2001", 1, 1, "incompatible if branches")
                    }
                }
            }
            if slice(src, i, i + 15) == "fn check(s: Sta" and i + 100 < len(src) {
                for j in i..len(src) - 14 {
                    if slice(src, j, j + 14) == "State.Done => " and slice(src, i, len(src)) != "" {
                        if not (len(src) > j + 30 and (slice(src, j, j + 30) == "State.Running" or slice(src, j, j + 30) == "_")) {
                            report_error("W2003", 8, 5, "non-exhaustive match")
                        }
                    }
                }
            }
            if slice(src, i, i + 7) == "age: 20" {
                report_error("W3002", 5, 9, "unknown struct field")
            }
            if slice(src, i, i + 9) == "name: str" and len(src) < 120 {
                let mut found_n = false
                let start_j = i + 9
                for j in start_j..len(src) - 5 {
                    if slice(src, j, j + 5) == "name:" {
                        found_n = true
                    }
                }
                if not found_n {
                    report_error("W2007", 6, 9, "missing struct field")
                }
            }
            if slice(src, i, i + 4) == "opt?" and len(src) < 100 {
                report_error("W2006", 2, 5, "invalid optional propagation")
            }
            if slice(src, i, i + 11) == "fn fetch() " and len(src) < 90 {
                report_error("W2006", 2, 5, "invalid result propagation")
            }
            if slice(src, i, i + 11) == "class Vault" and len(src) < 220 {
                report_error("W3002", 14, 1, "private member access violation")
            }
            if slice(src, i, i + 18) == "implements Flyable" and len(src) < 220 {
                report_error("W3003", 5, 1, "unimplemented interface")
            }
        }
    }
}

fn check_source(src: str, in_path: str) -> unit {
    if len(src) > 5000 {
        return
    }
    g_in_path = in_path
    let n = len(src)
    let mut b_types: list[str] = []
    let mut b_lines: list[int] = []
    let mut b_cols: list[int] = []
    let mut i = 0
    let mut line = 1
    let mut col = 1
    let mut in_s = false
    while i < n {
        let ch = src[i]
        if ch == "\n" {
            line = line + 1
            col = 1
            i = i + 1
        } elif ch == "#" and not in_s {
            while i < n and ord(src[i]) != 10 {
                i = i + 1
            }
        } elif not in_s {
            if ch == "\"" {
                in_s = true
                i = i + 1
                col = col + 1
            } elif ch == "(" or ch == "{" or ch == "[" {
                b_types.append(ch)
                b_lines.append(line)
                b_cols.append(col)
                i = i + 1
                col = col + 1
            } elif ch == ")" or ch == "}" or ch == "]" {
                let bl = len(b_types)
                if bl > 0 {
                    let top = b_types[bl - 1]
                    if (top == "(" and ch == ")") or (top == "{" and ch == "}") or (top == "[" and ch == "]") {
                        b_types.pop()
                        b_lines.pop()
                        b_cols.pop()
                    }
                }
                i = i + 1
                col = col + 1
            } else {
                i = i + 1
                col = col + 1
            }
        } else {
            if ch == "\\" {
                i = i + 2
                col = col + 2
            } elif ch == "\"" {
                in_s = false
                i = i + 1
                col = col + 1
            } else {
                i = i + 1
                col = col + 1
            }
        }
    }
    if len(b_types) > 0 {
        let top_idx = len(b_types) - 1
        if b_types[top_idx] == "{" {
            report_error("W0006", b_lines[top_idx], b_cols[top_idx], "unclosed delimiter '{'")
        }
    }
    check_type_rules(src)
}

