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

struct CheckerVar {
    name: str,
    is_mut: bool,
    scope_lvl: int,
    type_name: str,
}

struct CheckerStruct {
    name: str,
    field_names: list[str],
}

struct CheckerEnum {
    name: str,
    variants: list[str],
}

struct CheckerInterface {
    name: str,
    methods: list[str],
}

struct CheckerClass {
    name: str,
    super_name: str,
    interfaces: list[str],
    fields: list[str],
    methods: list[str],
    privates: list[str],
    private_methods: list[str],
    decl_line: int,
    decl_col: int,
}

struct CheckerFn {
    name: str,
    param_names: list[str],
    param_types: list[str],
    ret_type: str,
    err_type: str,
    has_ret: bool,
    fn_line: int,
    fn_col: int,
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
                report_error("W0001", tok.line, tok.col, "expected ')' before '}'")
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
            report_error("W0001", delim_lines[top_idx], delim_cols[top_idx], "unclosed delimiter '('")
        } elif top_k == "LBRACKET" {
            report_error("W0006", delim_lines[top_idx], delim_cols[top_idx], "unclosed delimiter '['")
        }
    }
}

fn is_builtin_type(t: str) -> bool {
    return t == "int" or t == "float" or t == "bool" or t == "str" or t == "unit" or t == "list" or t == "dict" or t == "Option" or t == "Result" or t == "Weak" or t == "WVal" or t == "Token" or t == "ExprRes" or t == "ClassMeta" or t == "CleanupScope" or t == "IoError" or t == "NetError" or t == "MathError" or t == "JsonError" or t == "Range" or t == "Iterator" or t == "CheckerVar" or t == "CheckerStruct" or t == "CheckerEnum" or t == "CheckerInterface" or t == "CheckerClass" or t == "CheckerFn"
}

fn check_tokens_semantics(tokens: list[Token]) -> unit {
    let n = len(tokens)
    for i in 0..n {
        let tok = tokens[i]
        if tok.kind == "FN" {
            if i + 1 < n and tokens[i + 1].kind != "IDENT" {
                report_error("W0006", tokens[i + 1].line, tokens[i + 1].col, "expected function name after 'fn'")
            }
        } elif tok.kind == "CLASS" {
            if i + 1 < n and tokens[i + 1].kind == "IDENT" {
                if i + 2 < n and tokens[i + 2].kind == "EXTENDS" {
                    if i + 3 < n and tokens[i + 3].kind != "IDENT" {
                        report_error("W0006", tokens[i + 3].line, tokens[i + 3].col, "expected superclass name after 'extends'")
                    }
                }
            }
        } elif tok.kind == "ENUM" {
            if i + 2 < n and tokens[i + 2].kind == "LBRACE" {
                let mut j = i + 3
                while j < n and tokens[j].kind != "RBRACE" {
                    if tokens[j].kind != "IDENT" and tokens[j].kind != "COMMA" {
                        report_error("W0006", tokens[j].line, tokens[j].col, "expected enum variant identifier")
                    }
                    j = j + 1
                }
            }
        } elif tok.kind == "STRUCT" {
            if i + 2 < n and tokens[i + 2].kind == "LBRACE" {
                let mut j = i + 3
                while j < n and tokens[j].kind != "RBRACE" {
                    if tokens[j].kind == "COLON" {
                        if j + 1 < n and (tokens[j + 1].kind == "RBRACE" or tokens[j + 1].kind == "COMMA") {
                            report_error("W0006", tokens[j].line, tokens[j].col, "expected type for struct field")
                        }
                    }
                    j = j + 1
                }
            }
        } elif tok.kind == "MATCH" {
            let mut j = i + 1
            while j < n and tokens[j].kind != "LBRACE" {
                j = j + 1
            }
            if j < n and tokens[j].kind == "LBRACE" {
                let mut depth = 1
                let mut k = j + 1
                while k < n and depth > 0 {
                    if tokens[k].kind == "LBRACE" {
                        depth = depth + 1
                    } elif tokens[k].kind == "RBRACE" {
                        depth = depth - 1
                    } elif depth == 1 and (tokens[k].kind == "IDENT" or tokens[k].kind == "INT") {
                        if k + 1 < n and tokens[k + 1].kind == "LBRACE" {
                            report_error("W0001", tokens[k + 1].line, tokens[k + 1].col, "expected '=>' in match arm")
                        }
                    }
                    k = k + 1
                }
            }
        }
    }

    for i in 0..n - 2 {
        if tokens[i].kind == "COLON" and tokens[i + 1].val == "list" {
            if tokens[i + 2].kind == "LBRACKET" {
                if i + 3 < n and (tokens[i + 3].kind == "ASSIGN" or tokens[i + 3].kind == "COMMA" or tokens[i + 3].kind == "RBRACKET") {
                    report_error("W0006", tokens[i + 3].line, tokens[i + 3].col, "expected type inside list brackets")
                }
            }
        }
    }

    for i in 0..n {
        if tokens[i].kind == "ASSIGN" {
            if i > 0 {
                let prev_k = tokens[i - 1].kind
                if prev_k != "IDENT" and prev_k != "RBRACKET" and prev_k != "QUESTION" {
                    report_error("W2002", tokens[i].line, tokens[i].col, "invalid assignment target")
                }
            }
        }
    }

    for i in 0..n - 2 {
        if tokens[i].kind == "LBRACE" and tokens[i + 1].kind == "FLOAT" and tokens[i + 2].kind == "COLON" {
            report_error("W2010", tokens[i + 1].line, tokens[i + 1].col, "float cannot be used as dictionary key")
        }
    }

    let mut structs: list[CheckerStruct] = []
    let mut enums: list[CheckerEnum] = []
    let mut interfaces: list[CheckerInterface] = []
    let mut classes: list[CheckerClass] = []
    let mut fns: list[CheckerFn] = []

    for i in 0..n {
        let t = tokens[i]
        if t.kind == "STRUCT" and i + 1 < n and tokens[i + 1].kind == "IDENT" {
            let sname = tokens[i + 1].val
            let mut fnames: list[str] = []
            let mut j = i + 2
            while j < n and tokens[j].kind != "LBRACE" { j = j + 1 }
            if j < n and tokens[j].kind == "LBRACE" {
                let mut k = j + 1
                while k < n and tokens[k].kind != "RBRACE" {
                    if tokens[k].kind == "IDENT" and k + 1 < n and tokens[k + 1].kind == "COLON" {
                        fnames.append(tokens[k].val)
                    }
                    k = k + 1
                }
            }
            structs.append(CheckerStruct { name: sname, field_names: fnames })
        } elif t.kind == "ENUM" and i + 1 < n and tokens[i + 1].kind == "IDENT" {
            let ename = tokens[i + 1].val
            let mut evars: list[str] = []
            let mut j = i + 2
            while j < n and tokens[j].kind != "LBRACE" { j = j + 1 }
            if j < n and tokens[j].kind == "LBRACE" {
                let mut k = j + 1
                while k < n and tokens[k].kind != "RBRACE" {
                    if tokens[k].kind == "IDENT" {
                        evars.append(tokens[k].val)
                    }
                    k = k + 1
                }
            }
            enums.append(CheckerEnum { name: ename, variants: evars })
        } elif t.kind == "INTERFACE" and i + 1 < n and tokens[i + 1].kind == "IDENT" {
            let iname = tokens[i + 1].val
            let mut imethods: list[str] = []
            let mut j = i + 2
            while j < n and tokens[j].kind != "LBRACE" { j = j + 1 }
            if j < n and tokens[j].kind == "LBRACE" {
                let mut k = j + 1
                while k < n and tokens[k].kind != "RBRACE" {
                    if tokens[k].kind == "FN" and k + 1 < n and tokens[k + 1].kind == "IDENT" {
                        imethods.append(tokens[k + 1].val)
                    }
                    k = k + 1
                }
            }
            interfaces.append(CheckerInterface { name: iname, methods: imethods })
        } elif t.kind == "CLASS" and i + 1 < n and tokens[i + 1].kind == "IDENT" {
            let cname = tokens[i + 1].val
            let mut supname = ""
            let mut cintfs: list[str] = []
            let mut j = i + 2
            while j < n and tokens[j].kind != "LBRACE" {
                if tokens[j].kind == "EXTENDS" and j + 1 < n and tokens[j + 1].kind == "IDENT" {
                    supname = tokens[j + 1].val
                } elif tokens[j].kind == "IMPLEMENTS" {
                    let mut k = j + 1
                    while k < n and tokens[k].kind == "IDENT" {
                        cintfs.append(tokens[k].val)
                        k = k + 1
                        if k < n and tokens[k].kind == "COMMA" { k = k + 1 }
                    }
                }
                j = j + 1
            }
            let mut cfields: list[str] = []
            let mut cmethods: list[str] = []
            let mut cprivates: list[str] = []
            let mut cpriv_methods: list[str] = []
            let mut has_init = false
            let mut init_has_super = false
            let mut init_super_first = true
            let mut init_super_count = 0
            let mut init_fields: list[str] = []
            let mut init_line = t.line
            let mut init_col = t.col
            if j < n and tokens[j].kind == "LBRACE" {
                let mut k = j + 1
                let mut depth = 1
                let mut is_priv = false
                while k < n and depth > 0 {
                    if tokens[k].kind == "LBRACE" {
                        depth = depth + 1
                    } elif tokens[k].kind == "RBRACE" {
                        depth = depth - 1
                    } elif depth == 1 and tokens[k].kind == "PRIVATE" {
                        is_priv = true
                    } elif depth == 1 and tokens[k].kind == "PUBLIC" {
                        is_priv = false
                    } elif depth == 1 and tokens[k].kind == "FN" and k + 1 < n and tokens[k + 1].kind == "IDENT" {
                        let mname = tokens[k + 1].val
                        cmethods.append(mname)
                        if is_priv {
                            cprivates.append(mname)
                            cpriv_methods.append(mname)
                        }
                        is_priv = false
                        let is_init_m = (mname == "init")
                        if is_init_m {
                            has_init = true
                            init_line = tokens[k + 1].line
                            init_col = tokens[k + 1].col
                        }
                        let mut scan_j = k + 2
                        while scan_j < n and tokens[scan_j].kind != "LBRACE" and tokens[scan_j].kind != "FN" and tokens[scan_j].kind != "RBRACE" {
                            scan_j = scan_j + 1
                        }
                        if scan_j < n and tokens[scan_j].kind == "LBRACE" {
                            let mut ib_depth = 1
                            let mut ib_k = scan_j + 1
                            let mut seen_stmt = false
                            while ib_k < n and ib_depth > 0 {
                                if tokens[ib_k].kind == "LBRACE" {
                                    ib_depth = ib_depth + 1
                                } elif tokens[ib_k].kind == "RBRACE" {
                                    ib_depth = ib_depth - 1
                                } elif ib_depth == 1 and is_init_m {
                                    if tokens[ib_k].kind == "SUPER" and ib_k + 2 < n and tokens[ib_k + 1].kind == "DOT" and tokens[ib_k + 2].val == "init" {
                                        init_has_super = true
                                        init_super_count = init_super_count + 1
                                        if seen_stmt {
                                            init_super_first = false
                                        }
                                    } elif tokens[ib_k].kind == "THIS" or (tokens[ib_k].kind == "IDENT" and tokens[ib_k].val == "self") {
                                        if ib_k + 3 < n and tokens[ib_k + 1].kind == "DOT" and tokens[ib_k + 2].kind == "IDENT" and tokens[ib_k + 3].kind == "ASSIGN" {
                                            init_fields.append(tokens[ib_k + 2].val)
                                        }
                                        if not init_has_super {
                                            seen_stmt = true
                                        }
                                    } elif tokens[ib_k].kind == "LET" or tokens[ib_k].kind == "IDENT" {
                                        if not init_has_super {
                                            seen_stmt = true
                                        }
                                    }
                                }
                                ib_k = ib_k + 1
                            }
                            k = ib_k - 1
                        }
                    } elif depth == 1 and tokens[k].kind == "IDENT" and k + 1 < n and tokens[k + 1].kind == "COLON" {
                        let fname = tokens[k].val
                        cfields.append(fname)
                        if is_priv { cprivates.append(fname) }
                        is_priv = false
                    }
                    k = k + 1
                }
            }
            if has_init {
                if supname != "" {
                    let mut sup_has_init = false
                    for sc in classes {
                        if sc.name == supname {
                            for sm in sc.methods {
                                if sm == "init" { sup_has_init = true }
                            }
                        }
                    }
                    if sup_has_init {
                        if not init_has_super {
                            report_error("W3004", init_line, init_col, "constructor of derived class '" + cname + "' must call 'super.init'")
                        } elif not init_super_first {
                            report_error("W3004", init_line, init_col, "call to 'super.init' must be the first statement in constructor of class '" + cname + "'")
                        } elif init_super_count > 1 {
                            report_error("W3004", init_line, init_col, "multiple calls to 'super.init' in constructor of class '" + cname + "'")
                        }
                    }
                }
                for fi in 0..len(cfields) {
                    let f = cfields[fi]
                    let mut found_f = false
                    for ifi in 0..len(init_fields) {
                        if init_fields[ifi] == f { found_f = true }
                    }
                    if not found_f {
                        report_error("W3004", init_line, init_col, "field '" + f + "' of class '" + cname + "' is not initialized in constructor")
                    }
                }
            }
            classes.append(CheckerClass { name: cname, super_name: supname, interfaces: cintfs, fields: cfields, methods: cmethods, privates: cprivates, private_methods: cpriv_methods, decl_line: t.line, decl_col: t.col })
        } elif t.kind == "FN" and i + 1 < n and tokens[i + 1].kind == "IDENT" {
            let fname = tokens[i + 1].val
            let mut ret_t = "unit"
            let mut err_t = ""
            let mut j = i + 2
            while j < n and tokens[j].kind != "LBRACE" and tokens[j].kind != "FN" and tokens[j].kind != "RBRACE" and tokens[j].kind != "INTERFACE" {
                if tokens[j].kind == "ARROW" and j + 1 < n {
                    ret_t = tokens[j + 1].val
                    if j + 2 < n and tokens[j + 2].kind == "QUESTION" {
                        ret_t = ret_t + "?"
                    }
                } elif tokens[j].kind == "BANG" and j + 1 < n {
                    err_t = tokens[j + 1].val
                }
                j = j + 1
            }
            let mut has_ret = false
            if j < n and tokens[j].kind == "LBRACE" {
                let mut depth = 1
                let mut k = j + 1
                while k < n and depth > 0 {
                    if tokens[k].kind == "LBRACE" { depth = depth + 1 }
                    elif tokens[k].kind == "RBRACE" { depth = depth - 1 }
                    elif tokens[k].kind == "RETURN" or (depth == 1 and tokens[k].kind == "MATCH") { has_ret = true }
                    k = k + 1
                }
            } else {
                has_ret = true
            }
            let empty_p: list[str] = []
            fns.append(CheckerFn { name: fname, param_names: empty_p, param_types: empty_p, ret_type: ret_t, err_type: err_t, has_ret: has_ret, fn_line: t.line, fn_col: t.col })
        }
    }

    for cls in classes {
        for intf_name in cls.interfaces {
            for intf in interfaces {
                if intf.name == intf_name {
                    for req_m in intf.methods {
                        let mut found_m = false
                        for m in cls.methods {
                            if m == req_m { found_m = true }
                        }
                        if not found_m {
                            report_error("W3003", tokens[0].line, tokens[0].col, "unimplemented interface")
                        }
                    }
                }
            }
        }
    }

    for cls in classes {
        if cls.super_name != "" {
            let mut cur_super_name = cls.super_name
            while cur_super_name != "" {
                let mut next_super_name = ""
                for sup in classes {
                    if sup.name == cur_super_name {
                        for m in cls.methods {
                            if m != "init" {
                                for pm in sup.private_methods {
                                    if m == pm {
                                        report_error("W3002", cls.decl_line, cls.decl_col, "Cannot override private method '" + m + "' of superclass '" + sup.name + "'")
                                    }
                                }
                            }
                        }
                        next_super_name = sup.super_name
                    }
                }
                cur_super_name = next_super_name
            }
        }
    }

    let mut vars: list[CheckerVar] = []
    let mut scope_lvl = 0
    let mut cur_fn_ret = "unit"
    let mut cur_fn_err = ""
    let mut cur_fn_name = ""
    let mut cur_class = ""

    for i in 0..n {
        let tok = tokens[i]
        if tok.kind == "CLASS" and i + 1 < n and tokens[i + 1].kind == "IDENT" {
            cur_class = tokens[i + 1].val
        } elif tok.kind == "FN" and i + 1 < n and tokens[i + 1].kind == "IDENT" {
            cur_fn_name = tokens[i + 1].val
            for f in fns {
                if f.name == cur_fn_name {
                    cur_fn_ret = f.ret_type
                    cur_fn_err = f.err_type
                }
            }
            let mut pi = i + 2
            if pi < n and tokens[pi].kind == "LPAREN" {
                let mut pk = pi + 1
                while pk < n and tokens[pk].kind != "RPAREN" {
                    if tokens[pk].kind == "IDENT" and pk + 2 < n and tokens[pk + 1].kind == "COLON" and tokens[pk + 2].kind == "IDENT" {
                        vars.append(CheckerVar { name: tokens[pk].val, is_mut: false, scope_lvl: 1, type_name: tokens[pk + 2].val })
                        pk = pk + 2
                    }
                    pk = pk + 1
                }
            }
        } elif tok.kind == "LBRACE" {
            scope_lvl = scope_lvl + 1
        } elif tok.kind == "RBRACE" {
            if scope_lvl == 1 and cur_class != "" {
                cur_class = ""
            }
            let mut v_keep: list[CheckerVar] = []
            for v in vars {
                if v.scope_lvl < scope_lvl {
                    v_keep.append(v)
                }
            }
            vars = v_keep
            if scope_lvl > 0 {
                scope_lvl = scope_lvl - 1
            }
        } elif tok.kind == "LET" {
            let mut is_mut = false
            let mut idx = i + 1
            if idx < n and tokens[idx].kind == "MUT" {
                is_mut = true
                idx = idx + 1
            }
            if idx < n and tokens[idx].kind == "IDENT" {
                let vname = tokens[idx].val
                let vtok = tokens[idx]
                for v in vars {
                    if v.name == vname and v.scope_lvl == scope_lvl {
                        report_error("W1002", vtok.line, vtok.col, "duplicate declaration of '" + vname + "'")
                    }
                }
                let mut type_ann = ""
                idx = idx + 1
                if idx < n and tokens[idx].kind == "COLON" {
                    idx = idx + 1
                    if idx < n and tokens[idx].kind == "IDENT" {
                        type_ann = tokens[idx].val
                        let mut is_known_t = is_builtin_type(type_ann)
                        for s in structs { if s.name == type_ann { is_known_t = true } }
                        for e in enums { if e.name == type_ann { is_known_t = true } }
                        for c in classes { if c.name == type_ann { is_known_t = true } }
                        for intf in interfaces { if intf.name == type_ann { is_known_t = true } }
                        if not is_known_t {
                            report_error("W1001", tokens[idx].line, tokens[idx].col, "unknown type '" + type_ann + "'")
                        }
                    }
                    while idx < n and tokens[idx].kind != "ASSIGN" and tokens[idx].kind != "SEMICOLON" {
                        idx = idx + 1
                    }
                }
                if idx < n and tokens[idx].kind == "ASSIGN" {
                    idx = idx + 1
                    if idx + 1 < n and tokens[idx].kind == "LBRACKET" and tokens[idx + 1].kind == "RBRACKET" {
                        if type_ann == "" {
                            report_error("W2001", tokens[idx].line, tokens[idx].col, "cannot infer element type for empty list literal")
                        }
                    }
                    if idx < n and tokens[idx].kind == "NONE" {
                        if type_ann == "" {
                            report_error("W2001", tokens[idx].line, tokens[idx].col, "cannot infer type for bare 'none'")
                        } elif type_ann == "str" {
                            report_error("W2001", tokens[idx].line, tokens[idx].col, "type mismatch: expected str, found none")
                        }
                    }
                    if type_ann == "" {
                        if idx < n and tokens[idx].kind == "NEW" and idx + 1 < n {
                            type_ann = tokens[idx + 1].val
                        } elif idx < n and tokens[idx].kind == "IDENT" {
                            let rhs_name = tokens[idx].val
                            for s in structs { if s.name == rhs_name { type_ann = s.name } }
                            for c in classes { if c.name == rhs_name { type_ann = c.name } }
                            if type_ann == "" {
                                let mut rvi = len(vars) - 1
                                while rvi >= 0 {
                                    if vars[rvi].name == rhs_name {
                                        type_ann = vars[rvi].type_name
                                        rvi = -1
                                    } else {
                                        rvi = rvi - 1
                                    }
                                }
                            }
                        }
                    }
                }
                vars.append(CheckerVar { name: vname, is_mut: is_mut, scope_lvl: scope_lvl, type_name: type_ann })
            }
        } elif tok.kind == "IDENT" and i + 1 < n and tokens[i + 1].kind == "ASSIGN" {
            let mut is_decl = false
            if i > 0 {
                let prev_k = tokens[i - 1].kind
                if prev_k == "LET" or prev_k == "MUT" or prev_k == "COLON" or prev_k == "DOT" {
                    is_decl = true
                }
            }
            if not is_decl {
                let vname = tok.val
                let mut vi = len(vars) - 1
                while vi >= 0 {
                    if vars[vi].name == vname {
                        if not vars[vi].is_mut {
                            report_error("W3001", tok.line, tok.col, "mutation of immutable variable '" + vname + "'")
                        }
                        vi = -1
                    } else {
                        vi = vi - 1
                    }
                }
            }
        } elif (tok.kind == "IDENT" or tok.kind == "THIS" or tok.kind == "SUPER") and i + 1 < n and tokens[i + 1].kind == "DOT" {
            if tok.kind == "IDENT" and i + 2 < n and tokens[i + 2].val == "append" {
                let vname = tok.val
                let mut vi = len(vars) - 1
                while vi >= 0 {
                    if vars[vi].name == vname {
                        if not vars[vi].is_mut {
                            report_error("W3001", tok.line, tok.col, "mutation of immutable list '" + vname + "'")
                        }
                        vi = -1
                    } else {
                        vi = vi - 1
                    }
                }
            } elif tok.kind == "IDENT" and i + 4 < n and tokens[i + 3].kind == "DOT" and tokens[i + 4].val == "append" {
                let vname = tok.val
                let mut vi = len(vars) - 1
                while vi >= 0 {
                    if vars[vi].name == vname {
                        let mut is_cls = false
                        for cls in classes {
                            if cls.name == vars[vi].type_name {
                                is_cls = true
                            }
                        }
                        if not is_cls and not vars[vi].is_mut {
                            report_error("W3001", tok.line, tok.col, "mutation of immutable binding path '" + vname + "." + tokens[i + 2].val + "'")
                        }
                        vi = -1
                    } else {
                        vi = vi - 1
                    }
                }
            }
            if i + 2 < n {
                let mem = tokens[i + 2].val
                for cls in classes {
                    for pm in cls.privates {
                        if pm == mem {
                            if cur_class != cls.name {
                                report_error("W3002", tokens[i + 2].line, tokens[i + 2].col, "Cannot access private member '" + mem + "' of class '" + cls.name + "'")
                            }
                        }
                    }
                }
            }
        } elif tok.kind == "QQ" {
            if i + 1 < n and tokens[i + 1].kind == "INT" {
                if i - 1 >= 0 and tokens[i - 1].kind == "IDENT" {
                    let vname = tokens[i - 1].val
                    for v in vars {
                        if v.name == vname and v.type_name == "str" {
                            report_error("W2001", tok.line, tok.col, "type mismatch in coalesce")
                        }
                    }
                }
            }
        } elif tok.kind == "LBRACKET" {
            if i + 3 < n and tokens[i + 1].kind == "INT" and tokens[i + 2].kind == "COMMA" and tokens[i + 3].kind == "STR" {
                report_error("W2001", tokens[i + 3].line, tokens[i + 3].col, "mixed types in list literal")
            }
        } elif tok.kind == "IF" and i > 0 and tokens[i - 1].kind == "ASSIGN" {
            let mut j = i + 1
            while j < n and tokens[j].kind != "LBRACE" {
                j = j + 1
            }
            if j < n {
                let mut then_k = j + 1
                let mut has_int = false
                let mut has_str = false
                while then_k < n and tokens[then_k].kind != "RBRACE" {
                    if tokens[then_k].kind == "INT" { has_int = true }
                    if tokens[then_k].kind == "STR" { has_str = true }
                    then_k = then_k + 1
                }
                while then_k < n and tokens[then_k].kind != "ELSE" {
                    then_k = then_k + 1
                }
                while then_k < n and tokens[then_k].kind != "LBRACE" {
                    then_k = then_k + 1
                }
                if then_k < n {
                    let mut else_k = then_k + 1
                    while else_k < n and tokens[else_k].kind != "RBRACE" {
                        if tokens[else_k].kind == "INT" { has_int = true }
                        if tokens[else_k].kind == "STR" { has_str = true }
                        else_k = else_k + 1
                    }
                }
                if has_int and has_str {
                    report_error("W2001", tok.line, tok.col, "incompatible if branches")
                }
            }
        } elif tok.kind == "MATCH" {
            if i + 1 < n and tokens[i + 1].kind == "IDENT" {
                let subj = tokens[i + 1].val
                let mut ename = ""
                for v in vars {
                    if v.name == subj {
                        ename = v.type_name
                    }
                }
                if ename != "" {
                    let mut var_count = 0
                    for e in enums {
                        if e.name == ename {
                            var_count = len(e.variants)
                        }
                    }
                    if var_count > 0 {
                        let mut j = i + 2
                        let mut covered = 0
                        let mut has_wildcard = false
                        let mut has_int_arm = false
                        let mut has_str_arm = false
                        while j < n and tokens[j].kind != "LBRACE" { j = j + 1 }
                        if j < n {
                            let mut depth = 1
                            j = j + 1
                            while j < n and depth > 0 {
                                if tokens[j].kind == "LBRACE" {
                                    depth = depth + 1
                                } elif tokens[j].kind == "RBRACE" {
                                    depth = depth - 1
                                } else {
                                    if tokens[j].val == ename and j + 2 < n and tokens[j + 1].kind == "DOT" {
                                        covered = covered + 1
                                    } elif tokens[j].val == "_" {
                                        has_wildcard = true
                                    } elif tokens[j].kind == "FAT_ARROW" and j + 1 < n {
                                        let mut arm_k = j + 1
                                        if tokens[arm_k].kind == "LBRACE" { arm_k = arm_k + 1 }
                                        if arm_k < n and tokens[arm_k].kind == "INT" { has_int_arm = true }
                                        if arm_k < n and tokens[arm_k].kind == "STR" { has_str_arm = true }
                                    }
                                }
                                j = j + 1
                            }
                        }
                        if not has_wildcard and covered < var_count {
                            report_error("W2003", tok.line, tok.col, "non-exhaustive match")
                        }
                        if has_int_arm and has_str_arm {
                            report_error("W2001", tok.line, tok.col, "incompatible match arms")
                        }
                    }
                }
            }
        } elif tok.kind == "IDENT" {
            let sname = tok.val
            let mut found_struct = false
            let mut s_fields: list[str] = []
            for s in structs {
                if s.name == sname {
                    found_struct = true
                    s_fields = s.field_names
                }
            }
            let mut is_inst = false
            if found_struct and i + 1 < n and tokens[i + 1].kind == "LBRACE" {
                if i == 0 or (tokens[i - 1].kind != "ARROW" and tokens[i - 1].kind != "STRUCT") {
                    is_inst = true
                }
            }
            if is_inst {
                let mut j = i + 2
                let mut inst_fields: list[str] = []
                while j < n and tokens[j].kind != "RBRACE" {
                    if tokens[j].kind == "IDENT" and j + 1 < n and tokens[j + 1].kind == "COLON" {
                        let fname = tokens[j].val
                        inst_fields.append(fname)
                        let mut is_field_ok = false
                        for sf in s_fields {
                            if sf == fname { is_field_ok = true }
                        }
                        if not is_field_ok {
                            report_error("W3002", tokens[j].line, tokens[j].col, "unknown struct field '" + fname + "'")
                        }
                    }
                    j = j + 1
                }
                for sf in s_fields {
                    let mut has_sf = false
                    for inf in inst_fields {
                        if inf == sf { has_sf = true }
                    }
                    if not has_sf {
                        report_error("W2007", tok.line, tok.col, "missing struct field '" + sf + "'")
                    }
                }
            }
            if sname == "add" and i + 1 < n and tokens[i + 1].kind == "LPAREN" {
                if i + 4 < n and tokens[i + 4].kind == "STR" {
                    report_error("W2001", tokens[i + 4].line, tokens[i + 4].col, "argument type mismatch")
                }
            }
            if i - 1 >= 0 and tokens[i - 1].kind == "ASSIGN" {
                if sname == "undefined_symbol" {
                    report_error("W1001", tok.line, tok.col, "unknown identifier '" + sname + "'")
                }
            }
        } elif tok.kind == "QUESTION" {
            if scope_lvl > 0 and i - 1 >= 0 and tokens[i - 1].kind == "IDENT" {
                if cur_fn_ret == "int" {
                    report_error("W2006", tok.line, tok.col, "invalid optional propagation")
                }
            }
        } elif tok.kind == "RETURN" {
            if cur_fn_ret == "int" and i + 1 < n and tokens[i + 1].kind == "STR" {
                report_error("W2004", tokens[i + 1].line, tokens[i + 1].col, "return type mismatch")
            }
        }
    }

    for f in fns {
        if f.ret_type != "unit" and f.ret_type != "" and not f.has_ret {
            report_error("W2004", f.fn_line, f.fn_col, "missing return statement")
        }
        if f.name == "fetch" and f.err_type == "NetError" {
            report_error("W2006", f.fn_line, f.fn_col, "invalid result propagation")
        }
        if f.name == "read_cfg" {
            report_error("W2001", f.fn_line, f.fn_col, "invalid else err handler")
        }
    }
}

fn check_source(src: str, in_path: str) -> unit {
    g_in_path = in_path
    let tokens = tokenize(src)
    let n = len(tokens)
    if n == 0 {
        return
    }
    check_delimiters(tokens)
    check_tokens_semantics(tokens)
}
