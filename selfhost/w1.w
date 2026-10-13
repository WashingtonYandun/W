struct Token {
    kind: str,
    val: str,
    line: int,
    col: int,
}

struct ExprRes {
    val: str,
    lref: str,
}

struct ClassMeta {
    name: str,
    super_name: str,
    field_names: list[str],
    field_defaults: list[str],
    method_names: list[str],
    method_arities: list[int],
    init_params: list[str],
}

let mut g_tokens: list[Token] = []
let mut g_pos: int = 0
let mut g_temp_id: int = 0
let mut g_fn_fallible: bool = false
let mut g_ns: str = ""
let mut g_enums: list[str] = []
let mut g_modules: list[str] = []
let mut g_classes: list[ClassMeta] = []
let mut g_dispatch_names: list[str] = []
let mut g_dispatch_arities: list[int] = []
let mut g_cur_class: str = ""
let mut g_cur_super: str = ""
let mut g_globals: list[str] = []
let mut g_protos: list[str] = []
let mut g_fn_defs: list[str] = []
let mut g_cur_stmts: list[str] = []

# ==========================================
# 1. Lexer Implementation
# ==========================================

fn is_alpha(c: int) -> bool {
    return (c >= 65 and c <= 90) or (c >= 97 and c <= 122) or c == 95
}

fn is_digit(c: int) -> bool {
    return c >= 48 and c <= 57
}

fn is_alnum(c: int) -> bool {
    return is_alpha(c) or is_digit(c)
}

fn is_space(c: int) -> bool {
    return c == 32 or c == 9 or c == 10 or c == 13
}

fn hex_val(c: int) -> int {
    if c >= 48 and c <= 57 { return c - 48 }
    if c >= 65 and c <= 70 { return c - 55 }
    if c >= 97 and c <= 102 { return c - 87 }
    return 0
}

fn keyword_kind(word: str) -> str {
    if word == "fn" { return "FN" }
    if word == "let" { return "LET" }
    if word == "mut" { return "MUT" }
    if word == "struct" { return "STRUCT" }
    if word == "enum" { return "ENUM" }
    if word == "class" { return "CLASS" }
    if word == "interface" { return "INTERFACE" }
    if word == "extends" { return "EXTENDS" }
    if word == "implements" { return "IMPLEMENTS" }
    if word == "new" { return "NEW" }
    if word == "this" { return "THIS" }
    if word == "super" { return "SUPER" }
    if word == "public" { return "PUBLIC" }
    if word == "private" { return "PRIVATE" }
    if word == "if" { return "IF" }
    if word == "elif" { return "ELIF" }
    if word == "else" { return "ELSE" }
    if word == "for" { return "FOR" }
    if word == "while" { return "WHILE" }
    if word == "in" { return "IN" }
    if word == "match" { return "MATCH" }
    if word == "return" { return "RETURN" }
    if word == "break" { return "BREAK" }
    if word == "continue" { return "CONTINUE" }
    if word == "import" { return "IMPORT" }
    if word == "true" { return "TRUE" }
    if word == "false" { return "FALSE" }
    if word == "none" { return "NONE" }
    if word == "and" { return "AND" }
    if word == "or" { return "OR" }
    if word == "not" { return "NOT" }
    return "IDENT"
}

fn tokenize(src: str) -> list[Token] {
    let mut tokens: list[Token] = []
    let n = len(src)
    let mut i = 0
    let mut line = 1
    let mut col = 1

    while i < n {
        let ch = src[i]
        let code = ord(ch)

        if is_space(code) {
            if code == 10 {
                line = line + 1
                col = 1
            } else {
                col = col + 1
            }
            i = i + 1
        } elif ch == "#" {
            while i < n and ord(src[i]) != 10 {
                i = i + 1
            }
        } elif is_alpha(code) {
            let start = i
            let start_col = col
            while i < n and is_alnum(ord(src[i])) {
                i = i + 1
                col = col + 1
            }
            let word = slice(src, start, i)
            let k = keyword_kind(word)
            tokens.append(Token { kind: k, val: word, line: line, col: start_col })
        } elif is_digit(code) {
            let start_col = col
            let mut is_flt = false
            let mut clean_num = ""
            while i < n and (is_digit(ord(src[i])) or src[i] == "_") {
                if src[i] != "_" {
                    clean_num = clean_num + src[i]
                }
                i = i + 1
                col = col + 1
            }
            if i + 1 < n and src[i] == "." and is_digit(ord(src[i + 1])) {
                is_flt = true
                clean_num = clean_num + "."
                i = i + 1
                col = col + 1
                while i < n and (is_digit(ord(src[i])) or src[i] == "_") {
                    if src[i] != "_" {
                        clean_num = clean_num + src[i]
                    }
                    i = i + 1
                    col = col + 1
                }
            }
            if is_flt {
                tokens.append(Token { kind: "FLOAT", val: clean_num, line: line, col: start_col })
            } else {
                tokens.append(Token { kind: "INT", val: clean_num, line: line, col: start_col })
            }
        } elif ch == "\"" {
            let start_col = col
            i = i + 1
            col = col + 1
            let mut s_val = ""
            while i < n and src[i] != "\"" {
                if src[i] == "\\" {
                    i = i + 1
                    col = col + 1
                    let esc = src[i]
                    if esc == "n" {
                        s_val = s_val + "\n"
                        i = i + 1
                        col = col + 1
                    } elif esc == "r" {
                        s_val = s_val + "\r"
                        i = i + 1
                        col = col + 1
                    } elif esc == "t" {
                        s_val = s_val + "\t"
                        i = i + 1
                        col = col + 1
                    } elif esc == "\\" {
                        s_val = s_val + "\\"
                        i = i + 1
                        col = col + 1
                    } elif esc == "\"" {
                        s_val = s_val + "\""
                        i = i + 1
                        col = col + 1
                    } elif esc == "0" {
                        s_val = s_val + chr(0)
                        i = i + 1
                        col = col + 1
                    } elif esc == "u" {
                        i = i + 2
                        col = col + 2
                        let mut u_cp = 0
                        while i < n and src[i] != "}" {
                            u_cp = u_cp * 16 + hex_val(ord(src[i]))
                            i = i + 1
                            col = col + 1
                        }
                        i = i + 1
                        col = col + 1
                        s_val = s_val + chr(u_cp)
                    } else {
                        s_val = s_val + esc
                        i = i + 1
                        col = col + 1
                    }
                } else {
                    s_val = s_val + src[i]
                    i = i + 1
                    col = col + 1
                }
            }
            i = i + 1
            col = col + 1
            tokens.append(Token { kind: "STR", val: s_val, line: line, col: start_col })
        } else {
            let start_col = col
            let mut two = ""
            let mut three = ""
            if i + 1 < n {
                two = slice(src, i, i + 2)
            }
            if i + 2 < n {
                three = slice(src, i, i + 3)
            }

            if three == "..=" {
                tokens.append(Token { kind: "DOT_DOT_EQ", val: "..=", line: line, col: start_col })
                i = i + 3
                col = col + 3
            } elif two == "==" {
                tokens.append(Token { kind: "EQ", val: "==", line: line, col: start_col })
                i = i + 2
                col = col + 2
            } elif two == "!=" {
                tokens.append(Token { kind: "NEQ", val: "!=", line: line, col: start_col })
                i = i + 2
                col = col + 2
            } elif two == "<=" {
                tokens.append(Token { kind: "LTE", val: "<=", line: line, col: start_col })
                i = i + 2
                col = col + 2
            } elif two == ">=" {
                tokens.append(Token { kind: "GTE", val: ">=", line: line, col: start_col })
                i = i + 2
                col = col + 2
            } elif two == "->" {
                tokens.append(Token { kind: "ARROW", val: "->", line: line, col: start_col })
                i = i + 2
                col = col + 2
            } elif two == "=>" {
                tokens.append(Token { kind: "FAT_ARROW", val: "=>", line: line, col: start_col })
                i = i + 2
                col = col + 2
            } elif two == ".." {
                tokens.append(Token { kind: "DOT_DOT", val: "..", line: line, col: start_col })
                i = i + 2
                col = col + 2
            } elif two == "??" {
                tokens.append(Token { kind: "QQ", val: "??", line: line, col: start_col })
                i = i + 2
                col = col + 2
            } else {
                let mut kind = "OP"
                if ch == "(" { kind = "LPAREN" }
                elif ch == ")" { kind = "RPAREN" }
                elif ch == "{" { kind = "LBRACE" }
                elif ch == "}" { kind = "RBRACE" }
                elif ch == "[" { kind = "LBRACKET" }
                elif ch == "]" { kind = "RBRACKET" }
                elif ch == "," { kind = "COMMA" }
                elif ch == ":" { kind = "COLON" }
                elif ch == "." { kind = "DOT" }
                elif ch == "+" { kind = "PLUS" }
                elif ch == "-" { kind = "MINUS" }
                elif ch == "*" { kind = "STAR" }
                elif ch == "/" { kind = "SLASH" }
                elif ch == "%" { kind = "PERCENT" }
                elif ch == "=" { kind = "ASSIGN" }
                elif ch == "<" { kind = "LT" }
                elif ch == ">" { kind = "GT" }
                elif ch == "!" { kind = "BANG" }
                elif ch == "?" { kind = "QUESTION" }
                tokens.append(Token { kind: kind, val: ch, line: line, col: start_col })
                i = i + 1
                col = col + 1
            }
        }
    }

    tokens.append(Token { kind: "EOF", val: "", line: line, col: col })
    return tokens
}

# ==========================================
# 2. Parser & C99 Codegen Helpers
# ==========================================

fn at_tok() -> Token {
    return g_tokens[g_pos]
}

fn peek_tok(offset: int) -> Token {
    let idx = g_pos + offset
    if idx >= len(g_tokens) {
        return g_tokens[len(g_tokens) - 1]
    }
    return g_tokens[idx]
}

fn is_eof() -> bool {
    return at_tok().kind == "EOF"
}

fn check_kind(k: str) -> bool {
    return at_tok().kind == k
}

fn advance_tok() -> Token {
    let tok = g_tokens[g_pos]
    if g_pos + 1 < len(g_tokens) {
        g_pos = g_pos + 1
    }
    return tok
}

fn match_kind(k: str) -> bool {
    if check_kind(k) {
        advance_tok()
        return true
    }
    return false
}

fn expect_kind(k: str) -> Token {
    let tok = at_tok()
    advance_tok()
    return tok
}

fn new_temp() -> str {
    let name = "_t" + str(g_temp_id)
    g_temp_id = g_temp_id + 1
    return name
}

fn emit_line(line: str) -> unit {
    g_cur_stmts.append(line)
}

fn is_enum_name(name: str) -> bool {
    for e in g_enums {
        if e == name {
            return true
        }
    }
    return false
}

fn is_module_name(name: str) -> bool {
    for m in g_modules {
        if m == name {
            return true
        }
    }
    return false
}

fn c_fn_name(name: str) -> str {
    if g_ns != "" {
        return "w_fn_" + g_ns + "__" + name
    }
    return "w_fn_" + name
}

fn escape_c_str(s: str) -> str {
    let mut out = "\""
    let n = len(s)
    for i in 0..n {
        let ch = s[i]
        let code = ord(ch)
        if code == 34 {
            out = out + "\\\""
        } elif code == 92 {
            out = out + "\\\\"
        } elif code == 10 {
            out = out + "\\n"
        } elif code == 13 {
            out = out + "\\r"
        } elif code == 9 {
            out = out + "\\t"
        } elif code == 0 {
            out = out + "\\0"
        } else {
            out = out + ch
        }
    }
    out = out + "\""
    return out
}

fn parse_type_ann() -> bool {
    let mut is_fallible = false
    advance_tok()
    if match_kind("LBRACKET") {
        while not check_kind("RBRACKET") and not is_eof() {
            parse_type_ann()
            match_kind("COMMA")
        }
        expect_kind("RBRACKET")
    }

    if match_kind("QUESTION") {
        is_fallible = false
    }
    if match_kind("BANG") {
        parse_type_ann()
        is_fallible = true
    }
    return is_fallible
}

fn parse_field_default() -> str {
    let tname = at_tok().val
    let mut def_c = "w_none()"
    if tname == "int" { def_c = "w_int(0LL)" }
    elif tname == "float" { def_c = "w_float(0.0)" }
    elif tname == "bool" { def_c = "w_bool(false)" }
    elif tname == "str" { def_c = "w_str(\"\")" }
    elif tname == "list" { def_c = "w_make_list(0, NULL)" }
    elif tname == "dict" { def_c = "w_make_dict(0, NULL, NULL)" }
    advance_tok()
    if match_kind("LBRACKET") {
        while not check_kind("RBRACKET") and not is_eof() {
            parse_type_ann()
            match_kind("COMMA")
        }
        expect_kind("RBRACKET")
    }
    if match_kind("QUESTION") {
        def_c = "w_none()"
    }
    return def_c
}

fn find_class_meta_idx(cls_name: str) -> int {
    for i in 0..len(g_classes) {
        if g_classes[i].name == cls_name {
            return i
        }
    }
    return -1
}

fn find_class_method_owner(start_cls: str, m_name: str) -> str {
    let mut cur = start_cls
    while cur != "" {
        let idx = find_class_meta_idx(cur)
        if idx == -1 {
            return ""
        }
        let cm = g_classes[idx]
        for mi in 0..len(cm.method_names) {
            if cm.method_names[mi] == m_name {
                return cm.name
            }
        }
        cur = cm.super_name
    }
    return ""
}

fn find_class_method_arity(start_cls: str, m_name: str) -> int {
    let mut cur = start_cls
    while cur != "" {
        let idx = find_class_meta_idx(cur)
        if idx == -1 {
            return -1
        }
        let cm = g_classes[idx]
        for mi in 0..len(cm.method_names) {
            if cm.method_names[mi] == m_name {
                return cm.method_arities[mi]
            }
        }
        cur = cm.super_name
    }
    return -1
}

fn register_dispatch(m_name: str, arity: int) -> unit {
    for i in 0..len(g_dispatch_names) {
        if g_dispatch_names[i] == m_name and g_dispatch_arities[i] == arity {
            return
        }
    }
    g_dispatch_names.append(m_name)
    g_dispatch_arities.append(arity)
    let mut sig = "WVal v_self"
    for ai in 0..arity {
        sig = sig + ", WVal _a" + str(ai)
    }
    g_protos.append("static WVal w_dispatch__" + m_name + "__" + str(arity) + "(" + sig + ");")
}

fn op_precedence(k: str) -> int {
    if k == "ASSIGN" { return 1 }
    if k == "QQ" { return 2 }
    if k == "OR" { return 3 }
    if k == "AND" { return 4 }
    if k == "EQ" or k == "NEQ" or k == "LT" or k == "LTE" or k == "GT" or k == "GTE" { return 6 }
    if k == "DOT_DOT" or k == "DOT_DOT_EQ" { return 7 }
    if k == "PLUS" or k == "MINUS" { return 8 }
    if k == "STAR" or k == "SLASH" or k == "PERCENT" { return 9 }
    return 0
}

fn clean_lref(raw: str) -> str {
    let n = len(raw)
    if n < 2 {
        return raw
    }
    for i in 0..(n - 1) {
        if slice(raw, i, i + 2) == "::" {
            return slice(raw, 0, i)
        }
    }
    return raw
}

fn extract_module_ns(path: str) -> str {
    let n = len(path)
    let mut slash = -1
    let mut dot = n
    for i in 0..n {
        if path[i] == "/" {
            slash = i
        } elif path[i] == "." {
            dot = i
        }
    }
    return slice(path, slash + 1, dot)
}

# ==========================================
# 3. Recursive-Descent + Pratt Expression Emitter
# ==========================================

fn emit_call(callee: ExprRes, args_c: list[str]) -> ExprRes {
    let raw = callee.lref
    let n = len(raw)
    let mut s1 = -1
    let mut s2 = -1
    let mut s3 = -1
    if n >= 2 {
        for i in 0..(n - 1) {
            if slice(raw, i, i + 2) == "::" {
                if s1 == -1 {
                    s1 = i
                } elif s2 == -1 {
                    s2 = i
                } else {
                    s3 = i
                    break
                }
            }
        }
    }

    if s1 != -1 and s2 != -1 and s3 != -1 {
        let method = slice(raw, s1 + 2, s2)
        let recv_lref = clean_lref(slice(raw, s2 + 2, s3))
        let recv_val = slice(raw, s3 + 2, n)

        if recv_val == "v_super" {
            let def_cls = find_class_method_owner(g_cur_super, method)
            if def_cls != "" {
                let mut joined = "v_self"
                for idx in 0..len(args_c) {
                    joined = joined + ", " + args_c[idx]
                }
                return ExprRes { val: "w_method_" + def_cls + "__" + method + "(" + joined + ")", lref: "" }
            }
            return ExprRes { val: "w_unit()", lref: "" }
        }

        if len(recv_val) >= 2 and slice(recv_val, 0, 2) == "v_" {
            let obj_name = slice(recv_val, 2, len(recv_val))
            if is_module_name(obj_name) {
                let mut joined = ""
                for idx in 0..len(args_c) {
                    if idx > 0 { joined = joined + ", " }
                    joined = joined + args_c[idx]
                }
                return ExprRes { val: "w_fn_" + obj_name + "__" + method + "(" + joined + ")", lref: "" }
            }
        }

        if method == "append" {
            return ExprRes { val: "w_list_append(" + recv_lref + ", " + args_c[0] + ")", lref: "" }
        }
        if method == "pop" {
            return ExprRes { val: "w_list_pop(" + recv_lref + ")", lref: "" }
        }
        if method == "clear" {
            return ExprRes { val: "w_list_clear(" + recv_lref + ")", lref: "" }
        }
        if method == "get" {
            return ExprRes { val: "w_dict_get(" + recv_val + ", " + args_c[0] + ")", lref: "" }
        }
        if method == "keys" {
            return ExprRes { val: "w_dict_keys(" + recv_val + ")", lref: "" }
        }
        if method == "values" {
            return ExprRes { val: "w_dict_values(" + recv_val + ")", lref: "" }
        }

        let mut d_args = recv_val
        for idx in 0..len(args_c) {
            d_args = d_args + ", " + args_c[idx]
        }
        return ExprRes { val: "w_dispatch__" + method + "__" + str(len(args_c)) + "(" + d_args + ")", lref: "" }
    }

    if len(callee.val) >= 2 and slice(callee.val, 0, 2) == "v_" {
        let fn_name = slice(callee.val, 2, len(callee.val))
        if fn_name == "print" {
            if len(args_c) == 0 {
                return ExprRes { val: "w_builtin_print(0, NULL)", lref: "" }
            }
            let arr_tmp = new_temp()
            let mut joined = ""
            for idx in 0..len(args_c) {
                if idx > 0 { joined = joined + ", " }
                joined = joined + args_c[idx]
            }
            let cnt = str(len(args_c))
            emit_line("WVal " + arr_tmp + "[" + cnt + "] = { " + joined + " };")
            return ExprRes { val: "w_builtin_print(" + cnt + ", " + arr_tmp + ")", lref: "" }
        }
        if fn_name == "len" { return ExprRes { val: "w_builtin_len(" + args_c[0] + ")", lref: "" } }
        if fn_name == "str" { return ExprRes { val: "w_builtin_str(" + args_c[0] + ")", lref: "" } }
        if fn_name == "int" { return ExprRes { val: "w_builtin_int(" + args_c[0] + ")", lref: "" } }
        if fn_name == "float" { return ExprRes { val: "w_builtin_float(" + args_c[0] + ")", lref: "" } }
        if fn_name == "ord" { return ExprRes { val: "w_builtin_ord(" + args_c[0] + ")", lref: "" } }
        if fn_name == "chr" { return ExprRes { val: "w_builtin_chr(" + args_c[0] + ")", lref: "" } }
        if fn_name == "bytes" { return ExprRes { val: "w_builtin_bytes(" + args_c[0] + ")", lref: "" } }
        if fn_name == "enumerate" { return ExprRes { val: "w_builtin_enumerate(" + args_c[0] + ")", lref: "" } }
        if fn_name == "dict_items" { return ExprRes { val: "w_builtin_dict_items(" + args_c[0] + ")", lref: "" } }
        if fn_name == "read_file" { return ExprRes { val: "w_builtin_read_file(" + args_c[0] + ")", lref: "" } }
        if fn_name == "write_file" { return ExprRes { val: "w_builtin_write_file(" + args_c[0] + ", " + args_c[1] + ")", lref: "" } }
        if fn_name == "slice" { return ExprRes { val: "w_builtin_slice(" + args_c[0] + ", " + args_c[1] + ", " + args_c[2] + ")", lref: "" } }
        if fn_name == "args" { return ExprRes { val: "w_builtin_args()", lref: "" } }

        let mut joined = ""
        for idx in 0..len(args_c) {
            if idx > 0 { joined = joined + ", " }
            joined = joined + args_c[idx]
        }
        return ExprRes { val: c_fn_name(fn_name) + "(" + joined + ")", lref: "" }
    }

    return ExprRes { val: "w_unit()", lref: "" }
}

fn parse_block_expr() -> str {
    expect_kind("LBRACE")
    let res = new_temp()
    emit_line("WVal " + res + " = w_unit();")
    emit_line("{")

    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty

    let mut tail_val = "w_unit()"
    while not check_kind("RBRACE") and not is_eof() {
        if check_kind("LET") {
            parse_let_stmt(false)
            tail_val = "w_unit()"
        } elif check_kind("WHILE") {
            parse_while_stmt()
            tail_val = "w_unit()"
        } elif check_kind("FOR") {
            parse_for_stmt()
            tail_val = "w_unit()"
        } elif check_kind("RETURN") {
            parse_return_stmt()
            tail_val = "w_unit()"
        } elif check_kind("BREAK") {
            advance_tok()
            emit_line("break;")
            tail_val = "w_unit()"
        } elif check_kind("CONTINUE") {
            advance_tok()
            emit_line("continue;")
            tail_val = "w_unit()"
        } else {
            let expr_r = parse_expr(0, true)
            if check_kind("RBRACE") {
                tail_val = expr_r.val
            } else {
                emit_line("(void)" + expr_r.val + ";")
                tail_val = "w_unit()"
            }
        }
    }
    expect_kind("RBRACE")
    if tail_val != "w_unit()" {
        emit_line(res + " = " + tail_val + ";")
    }
    let inner = g_cur_stmts
    g_cur_stmts = saved
    for l in inner {
        emit_line("    " + l)
    }
    emit_line("}")
    return res
}

fn parse_if_expr() -> ExprRes {
    expect_kind("IF")
    let res = new_temp()
    emit_line("WVal " + res + " = w_unit();")
    let cond_r = parse_expr(0, false)
    emit_line("if ((" + cond_r.val + ").as.b) {")

    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    let then_v = parse_block_expr()
    emit_line(res + " = " + then_v + ";")
    let then_lines = g_cur_stmts
    g_cur_stmts = saved
    for l in then_lines {
        emit_line("    " + l)
    }
    emit_line("}")

    parse_elif_chain(res)
    return ExprRes { val: res, lref: "" }
}

fn parse_elif_chain(res: str) -> unit {
    if match_kind("ELIF") {
        emit_line("else {")
        let saved = g_cur_stmts
        let empty: list[str] = []
        g_cur_stmts = empty

        let eb_cond = parse_expr(0, false)
        emit_line("if ((" + eb_cond.val + ").as.b) {")

        let saved_inner = g_cur_stmts
        let empty2: list[str] = []
        g_cur_stmts = empty2
        let eb_v = parse_block_expr()
        emit_line(res + " = " + eb_v + ";")
        let eb_lines = g_cur_stmts
        g_cur_stmts = saved_inner
        for l in eb_lines {
            emit_line("    " + l)
        }
        emit_line("}")

        parse_elif_chain(res)

        let outer_lines = g_cur_stmts
        g_cur_stmts = saved
        for l in outer_lines {
            emit_line("    " + l)
        }
        emit_line("}")
    } elif match_kind("ELSE") {
        emit_line("else {")
        let saved = g_cur_stmts
        let empty: list[str] = []
        g_cur_stmts = empty
        let else_v = parse_block_expr()
        emit_line(res + " = " + else_v + ";")
        let else_lines = g_cur_stmts
        g_cur_stmts = saved
        for l in else_lines {
            emit_line("    " + l)
        }
        emit_line("}")
    }
}

fn parse_match_expr() -> ExprRes {
    expect_kind("MATCH")
    let subj_r = parse_expr(0, false)
    let subj_tmp = new_temp()
    let res = new_temp()
    emit_line("WVal " + subj_tmp + " = " + subj_r.val + ";")
    emit_line("WVal " + res + " = w_unit();")
    expect_kind("LBRACE")
    if not check_kind("RBRACE") {
        parse_match_arms(subj_tmp, res)
    }
    expect_kind("RBRACE")
    return ExprRes { val: res, lref: "" }
}

fn parse_match_arms(subj_tmp: str, res: str) -> unit {
    let mut cond_c = "true"
    let mut bind_lines: list[str] = []

    if match_kind("ELSE") {
        cond_c = "true"
    } elif check_kind("IDENT") {
        let id_tok = advance_tok()
        if match_kind("DOT") {
            let var_tok = expect_kind("IDENT")
            cond_c = "w_eq(" + subj_tmp + ", w_enum(\"" + id_tok.val + "\", \"" + var_tok.val + "\"))"
        } elif check_kind("COMMA") {
            let mut t_names: list[str] = [id_tok.val]
            while match_kind("COMMA") {
                let nt = expect_kind("IDENT")
                t_names.append(nt.val)
            }
            cond_c = "((" + subj_tmp + ").tag == W_TUPLE && (" + subj_tmp + ").as.tuple->len == " + str(len(t_names)) + ")"
            for ti in 0..len(t_names) {
                bind_lines.append("WVal v_" + t_names[ti] + " = w_clone((" + subj_tmp + ").as.tuple->items[" + str(ti) + "]);")
            }
        } else {
            cond_c = "true"
            bind_lines.append("WVal v_" + id_tok.val + " = w_clone(" + subj_tmp + ");")
        }
    } else {
        let lit_r = parse_prefix_expr(false)
        cond_c = "w_eq(" + subj_tmp + ", " + lit_r.val + ")"
    }

    expect_kind("FAT_ARROW")
    emit_line("if (" + cond_c + ") {")

    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    for bl in bind_lines {
        emit_line(bl)
    }

    if check_kind("LBRACE") {
        let arm_v = parse_block_expr()
        emit_line(res + " = " + arm_v + ";")
    } else {
        let arm_tmp = new_temp()
        emit_line("WVal " + arm_tmp + " = w_unit();")
        emit_line("{")
        let saved2 = g_cur_stmts
        let empty2: list[str] = []
        g_cur_stmts = empty2
        let e_r = parse_expr(0, true)
        emit_line(arm_tmp + " = " + e_r.val + ";")
        let e_lines = g_cur_stmts
        g_cur_stmts = saved2
        for el in e_lines {
            emit_line("    " + el)
        }
        emit_line("}")
        emit_line(res + " = " + arm_tmp + ";")
    }

    let arm_lines = g_cur_stmts
    g_cur_stmts = saved
    for al in arm_lines {
        emit_line("    " + al)
    }
    emit_line("}")

    match_kind("COMMA")

    if not check_kind("RBRACE") and not is_eof() {
        emit_line("else {")
        let saved_else = g_cur_stmts
        let empty_else: list[str] = []
        g_cur_stmts = empty_else
        parse_match_arms(subj_tmp, res)
        let else_lines = g_cur_stmts
        g_cur_stmts = saved_else
        for el in else_lines {
            emit_line("    " + el)
        }
        emit_line("}")
    }
}

fn parse_prefix_expr(allow_struct: bool) -> ExprRes {
    let tok = at_tok()

    if match_kind("INT") {
        return ExprRes { val: "w_int(" + tok.val + "LL)", lref: "" }
    }
    if match_kind("FLOAT") {
        return ExprRes { val: "w_float(" + tok.val + ")", lref: "" }
    }
    if match_kind("STR") {
        return ExprRes { val: "w_str(" + escape_c_str(tok.val) + ")", lref: "" }
    }
    if match_kind("TRUE") {
        return ExprRes { val: "w_bool(true)", lref: "" }
    }
    if match_kind("FALSE") {
        return ExprRes { val: "w_bool(false)", lref: "" }
    }
    if match_kind("NONE") {
        return ExprRes { val: "w_none()", lref: "" }
    }
    if match_kind("THIS") {
        return ExprRes { val: "v_self", lref: "&v_self" }
    }
    if match_kind("SUPER") {
        return ExprRes { val: "v_super", lref: "&v_super" }
    }
    if match_kind("NEW") {
        let cname_tok = expect_kind("IDENT")
        expect_kind("LPAREN")
        let mut args_c: list[str] = []
        if not check_kind("RPAREN") {
            let a0 = parse_expr(0, true)
            args_c.append(a0.val)
            while match_kind("COMMA") {
                if check_kind("RPAREN") {
                    break
                }
                let an = parse_expr(0, true)
                args_c.append(an.val)
            }
        }
        expect_kind("RPAREN")
        let mut joined = ""
        for idx in 0..len(args_c) {
            if idx > 0 { joined = joined + ", " }
            joined = joined + args_c[idx]
        }
        return ExprRes { val: "w_new_" + cname_tok.val + "(" + joined + ")", lref: "" }
    }

    if match_kind("IDENT") {
        let name = tok.val
        if allow_struct and check_kind("LBRACE") {
            let p1 = peek_tok(1)
            let p2 = peek_tok(2)
            if p1.kind == "RBRACE" or (p1.kind == "IDENT" and p2.kind == "COLON") {
                advance_tok()
                let mut f_names: list[str] = []
                let mut f_vals: list[str] = []
                while not check_kind("RBRACE") and not is_eof() {
                    let f_tok = expect_kind("IDENT")
                    expect_kind("COLON")
                    let f_v = parse_expr(0, true)
                    f_names.append("\"" + f_tok.val + "\"")
                    f_vals.append(f_v.val)
                    match_kind("COMMA")
                }
                expect_kind("RBRACE")
                if len(f_names) == 0 {
                    return ExprRes { val: "w_make_struct(\"" + name + "\", 0, NULL, NULL)", lref: "" }
                }
                let k_tmp = new_temp()
                let v_tmp = new_temp()
                let mut k_joined = ""
                let mut v_joined = ""
                for idx in 0..len(f_names) {
                    if idx > 0 {
                        k_joined = k_joined + ", "
                        v_joined = v_joined + ", "
                    }
                    k_joined = k_joined + f_names[idx]
                    v_joined = v_joined + f_vals[idx]
                }
                let cnt = str(len(f_names))
                emit_line("const char* " + k_tmp + "[" + cnt + "] = { " + k_joined + " };")
                emit_line("WVal " + v_tmp + "[" + cnt + "] = { " + v_joined + " };")
                return ExprRes { val: "w_make_struct(\"" + name + "\", " + cnt + ", " + k_tmp + ", " + v_tmp + ")", lref: "" }
            }
        }
        return ExprRes { val: "v_" + name, lref: "&v_" + name }
    }

    if match_kind("MINUS") {
        let op_r = parse_expr(8, allow_struct)
        return ExprRes { val: "w_neg(" + op_r.val + ")", lref: "" }
    }
    if match_kind("NOT") {
        let op_r = parse_expr(8, allow_struct)
        return ExprRes { val: "w_bool(!(" + op_r.val + ").as.b)", lref: "" }
    }

    if match_kind("LPAREN") {
        if match_kind("RPAREN") {
            return ExprRes { val: "w_make_tuple(0, NULL)", lref: "" }
        }
        let first = parse_expr(0, true)
        if match_kind("COMMA") {
            let mut t_elems: list[str] = [first.val]
            if not check_kind("RPAREN") {
                let second = parse_expr(0, true)
                t_elems.append(second.val)
                while match_kind("COMMA") {
                    if check_kind("RPAREN") {
                        break
                    }
                    let nxt = parse_expr(0, true)
                    t_elems.append(nxt.val)
                }
            }
            expect_kind("RPAREN")
            let arr_tmp = new_temp()
            let mut joined = ""
            for idx in 0..len(t_elems) {
                if idx > 0 { joined = joined + ", " }
                joined = joined + t_elems[idx]
            }
            let cnt = str(len(t_elems))
            emit_line("WVal " + arr_tmp + "[" + cnt + "] = { " + joined + " };")
            return ExprRes { val: "w_make_tuple(" + cnt + ", " + arr_tmp + ")", lref: "" }
        }
        expect_kind("RPAREN")
        return first
    }

    if match_kind("LBRACKET") {
        let mut elems: list[str] = []
        if not check_kind("RBRACKET") {
            let first = parse_expr(0, true)
            elems.append(first.val)
            while match_kind("COMMA") {
                if check_kind("RBRACKET") {
                    break
                }
                let nxt = parse_expr(0, true)
                elems.append(nxt.val)
            }
        }
        expect_kind("RBRACKET")
        if len(elems) == 0 {
            return ExprRes { val: "w_make_list(0, NULL)", lref: "" }
        }
        let arr_tmp = new_temp()
        let mut joined = ""
        for idx in 0..len(elems) {
            if idx > 0 {
                joined = joined + ", "
            }
            joined = joined + elems[idx]
        }
        let cnt = str(len(elems))
        emit_line("WVal " + arr_tmp + "[" + cnt + "] = { " + joined + " };")
        return ExprRes { val: "w_make_list(" + cnt + ", " + arr_tmp + ")", lref: "" }
    }

    if match_kind("LBRACE") {
        let mut d_keys: list[str] = []
        let mut d_vals: list[str] = []
        if not check_kind("RBRACE") {
            let k0 = parse_expr(0, true)
            expect_kind("COLON")
            let v0 = parse_expr(0, true)
            d_keys.append(k0.val)
            d_vals.append(v0.val)
            while match_kind("COMMA") {
                if check_kind("RBRACE") {
                    break
                }
                let kn = parse_expr(0, true)
                expect_kind("COLON")
                let vn = parse_expr(0, true)
                d_keys.append(kn.val)
                d_vals.append(vn.val)
            }
        }
        expect_kind("RBRACE")
        if len(d_keys) == 0 {
            return ExprRes { val: "w_make_dict(0, NULL, NULL)", lref: "" }
        }
        let k_tmp = new_temp()
        let v_tmp = new_temp()
        let mut kj = ""
        let mut vj = ""
        for idx in 0..len(d_keys) {
            if idx > 0 {
                kj = kj + ", "
                vj = vj + ", "
            }
            kj = kj + d_keys[idx]
            vj = vj + d_vals[idx]
        }
        let cnt = str(len(d_keys))
        emit_line("WVal " + k_tmp + "[" + cnt + "] = { " + kj + " };")
        emit_line("WVal " + v_tmp + "[" + cnt + "] = { " + vj + " };")
        return ExprRes { val: "w_make_dict(" + cnt + ", " + k_tmp + ", " + v_tmp + ")", lref: "" }
    }

    if check_kind("IF") {
        return parse_if_expr()
    }

    if check_kind("MATCH") {
        return parse_match_expr()
    }

    advance_tok()
    return ExprRes { val: "w_unit()", lref: "" }
}

fn parse_expr(min_prec: int, allow_struct: bool) -> ExprRes {
    let mut left = parse_prefix_expr(allow_struct)

    while true {
        while true {
            if check_kind("LPAREN") {
                advance_tok()
                let mut args_c: list[str] = []
                if not check_kind("RPAREN") {
                    let a0 = parse_expr(0, true)
                    args_c.append(a0.val)
                    while match_kind("COMMA") {
                        if check_kind("RPAREN") {
                            break
                        }
                        let an = parse_expr(0, true)
                        args_c.append(an.val)
                    }
                }
                expect_kind("RPAREN")
                left = emit_call(left, args_c)
            } elif check_kind("DOT") {
                advance_tok()
                let prop_tok = expect_kind("IDENT")
                let prop = prop_tok.val
                if len(left.val) >= 2 and slice(left.val, 0, 2) == "v_" {
                    let raw_obj = slice(left.val, 2, len(left.val))
                    if is_enum_name(raw_obj) {
                        left = ExprRes { val: "w_enum(\"" + raw_obj + "\", \"" + prop + "\")", lref: "" }
                    } else {
                        left = ExprRes {
                            val: "w_member_get(" + left.val + ", \"" + prop + "\")",
                            lref: "w_member_ref(" + clean_lref(left.lref) + ", \"" + prop + "\")::" + prop + "::" + clean_lref(left.lref) + "::" + left.val,
                        }
                    }
                } else {
                    left = ExprRes {
                        val: "w_member_get(" + left.val + ", \"" + prop + "\")",
                        lref: "w_member_ref(" + clean_lref(left.lref) + ", \"" + prop + "\")::" + prop + "::" + clean_lref(left.lref) + "::" + left.val,
                    }
                }
            } elif check_kind("LBRACKET") {
                advance_tok()
                let idx_r = parse_expr(0, true)
                expect_kind("RBRACKET")
                left = ExprRes {
                    val: "w_index_get(" + left.val + ", " + idx_r.val + ")",
                    lref: "w_index_ref(" + clean_lref(left.lref) + ", " + idx_r.val + ")",
                }
            } elif check_kind("QUESTION") {
                advance_tok()
                let tmp = new_temp()
                let unw = new_temp()
                emit_line("WVal " + tmp + " = " + left.val + ";")
                emit_line("if (" + tmp + ".tag == W_NONE) return w_none();")
                emit_line("if (" + tmp + ".tag == W_ERR) return " + tmp + ";")
                emit_line("WVal " + unw + " = (" + tmp + ".tag == W_OK) ? *(" + tmp + ".as.box) : " + tmp + ";")
                left = ExprRes { val: unw, lref: "" }
            } elif check_kind("ELSE") {
                advance_tok()
                let mut err_name = ""
                if check_kind("IDENT") {
                    let et = advance_tok()
                    err_name = et.val
                }
                let tmp = new_temp()
                let res = new_temp()
                emit_line("WVal " + tmp + " = " + left.val + ";")
                emit_line("WVal " + res + " = w_unit();")
                emit_line("if (" + tmp + ".tag == W_ERR || " + tmp + ".tag == W_NONE) {")
                let saved = g_cur_stmts
                let empty: list[str] = []
                g_cur_stmts = empty
                if err_name != "" {
                    emit_line("WVal v_" + err_name + " = (" + tmp + ".tag == W_ERR) ? *(" + tmp + ".as.box) : w_none();")
                }
                let hv = parse_block_expr()
                emit_line(res + " = " + hv + ";")
                let h_lines = g_cur_stmts
                g_cur_stmts = saved
                for l in h_lines {
                    emit_line("    " + l)
                }
                emit_line("} else {")
                emit_line("    " + res + " = (" + tmp + ".tag == W_OK) ? *(" + tmp + ".as.box) : " + tmp + ";")
                emit_line("}")
                left = ExprRes { val: res, lref: "" }
            } else {
                break
            }
        }

        let op_tok = at_tok()
        let prec = op_precedence(op_tok.kind)
        if prec <= min_prec {
            break
        }
        advance_tok()

        let mut next_min = prec
        if op_tok.kind == "ASSIGN" or op_tok.kind == "QQ" {
            next_min = prec - 1
        }

        if op_tok.kind == "AND" {
            let res = new_temp()
            emit_line("WVal " + res + " = w_bool(false);")
            emit_line("if ((" + left.val + ").as.b) {")
            let saved = g_cur_stmts
            let empty: list[str] = []
            g_cur_stmts = empty
            let rhs = parse_expr(next_min, allow_struct)
            emit_line(res + " = w_bool((" + rhs.val + ").as.b);")
            let r_lines = g_cur_stmts
            g_cur_stmts = saved
            for l in r_lines {
                emit_line("    " + l)
            }
            emit_line("}")
            left = ExprRes { val: res, lref: "" }
        } elif op_tok.kind == "OR" {
            let res = new_temp()
            emit_line("WVal " + res + " = w_bool(true);")
            emit_line("if (!(" + left.val + ").as.b) {")
            let saved = g_cur_stmts
            let empty: list[str] = []
            g_cur_stmts = empty
            let rhs = parse_expr(next_min, allow_struct)
            emit_line(res + " = w_bool((" + rhs.val + ").as.b);")
            let r_lines = g_cur_stmts
            g_cur_stmts = saved
            for l in r_lines {
                emit_line("    " + l)
            }
            emit_line("}")
            left = ExprRes { val: res, lref: "" }
        } elif op_tok.kind == "QQ" {
            let res = new_temp()
            emit_line("WVal " + res + " = " + left.val + ";")
            emit_line("if (" + res + ".tag == W_NONE) {")
            let saved = g_cur_stmts
            let empty: list[str] = []
            g_cur_stmts = empty
            let rhs = parse_expr(next_min, allow_struct)
            emit_line(res + " = " + rhs.val + ";")
            let r_lines = g_cur_stmts
            g_cur_stmts = saved
            for l in r_lines {
                emit_line("    " + l)
            }
            emit_line("}")
            left = ExprRes { val: res, lref: "" }
        } else {
            let right = parse_expr(next_min, allow_struct)
            if op_tok.kind == "ASSIGN" {
                if len(left.val) >= 2 and slice(left.val, 0, 2) == "v_" {
                    emit_line(left.val + " = w_clone(" + right.val + ");")
                    left = ExprRes { val: left.val, lref: left.lref }
                } else {
                    let tmp = new_temp()
                    let target_ref = clean_lref(left.lref)
                    emit_line("WVal " + tmp + " = w_clone(" + right.val + ");")
                    emit_line("*(" + target_ref + ") = " + tmp + ";")
                    left = ExprRes { val: tmp, lref: "" }
                }
            } elif op_tok.kind == "DOT_DOT" {
                left = ExprRes { val: "w_make_range(" + left.val + ", " + right.val + ", false)", lref: "" }
            } elif op_tok.kind == "DOT_DOT_EQ" {
                left = ExprRes { val: "w_make_range(" + left.val + ", " + right.val + ", true)", lref: "" }
            } elif op_tok.kind == "PLUS" {
                left = ExprRes { val: "w_add(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "MINUS" {
                left = ExprRes { val: "w_sub(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "STAR" {
                left = ExprRes { val: "w_mul(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "SLASH" {
                left = ExprRes { val: "w_div(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "PERCENT" {
                left = ExprRes { val: "w_mod(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "LT" {
                left = ExprRes { val: "w_lt(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "LTE" {
                left = ExprRes { val: "w_le(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "GT" {
                left = ExprRes { val: "w_gt(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "GTE" {
                left = ExprRes { val: "w_ge(" + left.val + ", " + right.val + ")", lref: "" }
            } elif op_tok.kind == "EQ" {
                left = ExprRes { val: "w_bool(w_eq(" + left.val + ", " + right.val + "))", lref: "" }
            } elif op_tok.kind == "NEQ" {
                left = ExprRes { val: "w_bool(!w_eq(" + left.val + ", " + right.val + "))", lref: "" }
            }
        }
    }

    return left
}

# ==========================================
# 4. Statement & Top-Level Declaration Emitters
# ==========================================

fn parse_let_stmt(is_global: bool) -> unit {
    expect_kind("LET")
    match_kind("MUT")
    let name_tok = expect_kind("IDENT")
    if match_kind("COLON") {
        parse_type_ann()
    }
    expect_kind("ASSIGN")
    let val_r = parse_expr(0, true)
    let mut vname = "v_" + name_tok.val
    if is_global and g_ns != "" {
        vname = "v_" + g_ns + "_" + name_tok.val
    }
    if is_global {
        g_globals.append(vname)
        emit_line(vname + " = w_clone(" + val_r.val + ");")
    } else {
        emit_line("WVal " + vname + " = w_clone(" + val_r.val + ");")
    }
}

fn parse_return_stmt() -> unit {
    expect_kind("RETURN")
    if check_kind("RBRACE") or is_eof() {
        if g_fn_fallible {
            emit_line("return w_ok(w_unit());")
        } else {
            emit_line("return w_unit();")
        }
        return
    }
    let val_r = parse_expr(0, true)
    if g_fn_fallible {
        emit_line("return w_ok(" + val_r.val + ");")
    } else {
        emit_line("return " + val_r.val + ";")
    }
}

fn parse_while_stmt() -> unit {
    expect_kind("WHILE")
    emit_line("while (1) {")
    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty

    let cond_r = parse_expr(0, false)
    emit_line("if (!(" + cond_r.val + ").as.b) break;")
    let body_v = parse_block_expr()
    emit_line("(void)" + body_v + ";")

    let inner = g_cur_stmts
    g_cur_stmts = saved
    for l in inner {
        emit_line("    " + l)
    }
    emit_line("}")
}

fn parse_for_stmt() -> unit {
    expect_kind("FOR")
    let pat0 = expect_kind("IDENT")
    let mut pat_names: list[str] = [pat0.val]
    while match_kind("COMMA") {
        let pn = expect_kind("IDENT")
        pat_names.append(pn.val)
    }
    expect_kind("IN")
    let iter_r = parse_expr(0, false)
    let iter_tmp = new_temp()
    let idx_tmp = new_temp()
    let item_tmp = new_temp()
    emit_line("WVal " + iter_tmp + " = w_clone(" + iter_r.val + ");")
    emit_line("for (int32_t " + idx_tmp + " = 0; " + idx_tmp + " < " + iter_tmp + ".as.list->len; " + idx_tmp + "++) {")

    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    emit_line("WVal " + item_tmp + " = " + iter_tmp + ".as.list->data[" + idx_tmp + "];")
    if len(pat_names) == 1 {
        emit_line("WVal v_" + pat_names[0] + " = w_clone(" + item_tmp + ");")
    } else {
        for pi in 0..len(pat_names) {
            emit_line("WVal v_" + pat_names[pi] + " = w_clone((" + item_tmp + ").as.tuple->items[" + str(pi) + "]);")
        }
    }
    let body_v = parse_block_expr()
    emit_line("(void)" + body_v + ";")

    let inner = g_cur_stmts
    g_cur_stmts = saved
    for l in inner {
        emit_line("    " + l)
    }
    emit_line("}")
}

fn parse_struct_decl() -> unit {
    expect_kind("STRUCT")
    expect_kind("IDENT")
    expect_kind("LBRACE")
    while not check_kind("RBRACE") and not is_eof() {
        expect_kind("IDENT")
        expect_kind("COLON")
        parse_type_ann()
        match_kind("COMMA")
    }
    expect_kind("RBRACE")
}

fn parse_enum_decl() -> unit {
    expect_kind("ENUM")
    let name_tok = expect_kind("IDENT")
    g_enums.append(name_tok.val)
    expect_kind("LBRACE")
    while not check_kind("RBRACE") and not is_eof() {
        expect_kind("IDENT")
        match_kind("COMMA")
    }
    expect_kind("RBRACE")
}

fn parse_interface_decl() -> unit {
    expect_kind("INTERFACE")
    expect_kind("IDENT")
    expect_kind("LBRACE")
    while not check_kind("RBRACE") and not is_eof() {
        expect_kind("FN")
        expect_kind("IDENT")
        expect_kind("LPAREN")
        if not check_kind("RPAREN") {
            expect_kind("IDENT")
            expect_kind("COLON")
            parse_type_ann()
            while match_kind("COMMA") {
                if check_kind("RPAREN") {
                    break
                }
                expect_kind("IDENT")
                expect_kind("COLON")
                parse_type_ann()
            }
        }
        expect_kind("RPAREN")
        if match_kind("ARROW") {
            parse_type_ann()
        }
        match_kind("COMMA")
    }
    expect_kind("RBRACE")
}

fn parse_class_decl() -> unit {
    expect_kind("CLASS")
    let cname_tok = expect_kind("IDENT")
    let cls_name = cname_tok.val
    let mut sup_name = ""
    if match_kind("EXTENDS") {
        let s_tok = expect_kind("IDENT")
        sup_name = s_tok.val
    }
    if match_kind("IMPLEMENTS") {
        expect_kind("IDENT")
        while match_kind("COMMA") {
            expect_kind("IDENT")
        }
    }

    let mut f_names: list[str] = []
    let mut f_defaults: list[str] = []
    let mut m_names: list[str] = []
    let mut m_arities: list[int] = []
    let mut init_p: list[str] = []

    let prev_cls = g_cur_class
    let prev_sup = g_cur_super
    g_cur_class = cls_name
    g_cur_super = sup_name

    expect_kind("LBRACE")
    while not check_kind("RBRACE") and not is_eof() {
        if check_kind("PUBLIC") or check_kind("PRIVATE") {
            advance_tok()
        }
        if check_kind("FN") {
            advance_tok()
            let m_tok = expect_kind("IDENT")
            let mname = m_tok.val
            expect_kind("LPAREN")
            let mut p_names: list[str] = []
            if not check_kind("RPAREN") {
                let p0 = expect_kind("IDENT")
                expect_kind("COLON")
                parse_type_ann()
                p_names.append(p0.val)
                while match_kind("COMMA") {
                    if check_kind("RPAREN") {
                        break
                    }
                    let pn = expect_kind("IDENT")
                    expect_kind("COLON")
                    parse_type_ann()
                    p_names.append(pn.val)
                }
            }
            expect_kind("RPAREN")
            let mut fallible = false
            if match_kind("ARROW") {
                fallible = parse_type_ann()
            }

            m_names.append(mname)
            m_arities.append(len(p_names))
            if mname == "init" {
                init_p = p_names
            } else {
                register_dispatch(mname, len(p_names))
            }

            let mut m_sig = "WVal v_self"
            for idx in 0..len(p_names) {
                m_sig = m_sig + ", WVal v_" + p_names[idx]
            }
            let c_mname = "w_method_" + cls_name + "__" + mname
            g_protos.append("static WVal " + c_mname + "(" + m_sig + ");")

            let prev_fall = g_fn_fallible
            g_fn_fallible = fallible
            let saved = g_cur_stmts
            let empty: list[str] = []
            g_cur_stmts = empty

            emit_line("v_self = w_clone(v_self);")
            for p in p_names {
                emit_line("v_" + p + " = w_clone(v_" + p + ");")
            }
            let ret_v = parse_block_expr()
            if g_fn_fallible {
                emit_line("return w_ok(" + ret_v + ");")
            } else {
                emit_line("return " + ret_v + ";")
            }
            let body_lines = g_cur_stmts
            g_cur_stmts = saved
            g_fn_fallible = prev_fall

            let mut m_str = "static WVal " + c_mname + "(" + m_sig + ") {\n"
            for l in body_lines {
                m_str = m_str + "    " + l + "\n"
            }
            m_str = m_str + "}"
            g_fn_defs.append(m_str)
        } else {
            let f_tok = expect_kind("IDENT")
            expect_kind("COLON")
            let f_def = parse_field_default()
            match_kind("COMMA")
            f_names.append(f_tok.val)
            f_defaults.append(f_def)
        }
    }
    expect_kind("RBRACE")

    g_cur_class = prev_cls
    g_cur_super = prev_sup

    g_classes.append(ClassMeta {
        name: cls_name,
        super_name: sup_name,
        field_names: f_names,
        field_defaults: f_defaults,
        method_names: m_names,
        method_arities: m_arities,
        init_params: init_p,
    })

    # Collect all fields from root ancestor down to cls_name
    let mut lineage: list[int] = []
    let mut cur_c = cls_name
    while cur_c != "" {
        let cidx = find_class_meta_idx(cur_c)
        if cidx == -1 {
            break
        }
        lineage.append(cidx)
        cur_c = g_classes[cidx].super_name
    }
    let mut all_fnames: list[str] = []
    let mut all_fdefs: list[str] = []
    let mut li = len(lineage) - 1
    while li >= 0 {
        let cm = g_classes[lineage[li]]
        for fi in 0..len(cm.field_names) {
            all_fnames.append(cm.field_names[fi])
            all_fdefs.append(cm.field_defaults[fi])
        }
        li = li - 1
    }

    let init_owner = find_class_method_owner(cls_name, "init")
    let mut eff_init_p: list[str] = []
    if init_owner != "" {
        let oidx = find_class_meta_idx(init_owner)
        if oidx != -1 {
            eff_init_p = g_classes[oidx].init_params
        }
    }

    let mut new_sig = "void"
    let mut init_call_args = "v_self"
    if len(eff_init_p) > 0 {
        new_sig = ""
        for idx in 0..len(eff_init_p) {
            if idx > 0 { new_sig = new_sig + ", " }
            new_sig = new_sig + "WVal v_" + eff_init_p[idx]
            init_call_args = init_call_args + ", v_" + eff_init_p[idx]
        }
    }
    g_protos.append("static WVal w_new_" + cls_name + "(" + new_sig + ");")

    let mut new_str = "static WVal w_new_" + cls_name + "(" + new_sig + ") {\n"
    if len(all_fnames) > 0 {
        let mut kj = ""
        let mut vj = ""
        for fi in 0..len(all_fnames) {
            if fi > 0 {
                kj = kj + ", "
                vj = vj + ", "
            }
            kj = kj + "\"" + all_fnames[fi] + "\""
            vj = vj + all_fdefs[fi]
        }
        let fcnt = str(len(all_fnames))
        new_str = new_str + "    const char* _k[" + fcnt + "] = { " + kj + " };\n"
        new_str = new_str + "    WVal _v[" + fcnt + "] = { " + vj + " };\n"
        new_str = new_str + "    WVal v_self = w_make_object(\"" + cls_name + "\", " + fcnt + ", _k, _v);\n"
    } else {
        new_str = new_str + "    WVal v_self = w_make_object(\"" + cls_name + "\", 0, NULL, NULL);\n"
    }
    if init_owner != "" {
        new_str = new_str + "    (void)w_method_" + init_owner + "__init(" + init_call_args + ");\n"
    }
    new_str = new_str + "    return v_self;\n}"
    g_fn_defs.append(new_str)
}

fn emit_oop_dispatchers() -> unit {
    for di in 0..len(g_dispatch_names) {
        let mname = g_dispatch_names[di]
        let arity = g_dispatch_arities[di]
        let mut sig = "WVal v_self"
        let mut call_args = "v_self"
        for ai in 0..arity {
            sig = sig + ", WVal _a" + str(ai)
            call_args = call_args + ", _a" + str(ai)
        }
        let mut d_str = "static WVal w_dispatch__" + mname + "__" + str(arity) + "(" + sig + ") {\n"
        for ci in 0..len(g_classes) {
            let cname = g_classes[ci].name
            let owner = find_class_method_owner(cname, mname)
            let m_arity = find_class_method_arity(cname, mname)
            if owner != "" and m_arity == arity {
                d_str = d_str + "    if (v_self.tag == W_OBJECT && strcmp(v_self.as.st->name, \"" + cname + "\") == 0) return w_method_" + owner + "__" + mname + "(" + call_args + ");\n"
            }
        }
        d_str = d_str + "    return w_none();\n}"
        g_fn_defs.append(d_str)
    }
}

fn parse_import_decl() -> unit {
    expect_kind("IMPORT")
    let path_tok = expect_kind("STR")
    let ns = extract_module_ns(path_tok.val)
    if is_module_name(ns) {
        return
    }
    g_modules.append(ns)
    let mod_src = read_file(path_tok.val) else err {
        ""
    }
    if mod_src == "" {
        return
    }
    let saved_tokens = g_tokens
    let saved_pos = g_pos
    let saved_ns = g_ns

    g_tokens = tokenize(mod_src)
    g_pos = 0
    g_ns = ns

    while not is_eof() {
        if check_kind("STRUCT") {
            parse_struct_decl()
        } elif check_kind("ENUM") {
            parse_enum_decl()
        } elif check_kind("INTERFACE") {
            parse_interface_decl()
        } elif check_kind("CLASS") {
            parse_class_decl()
        } elif check_kind("FN") {
            parse_fn_decl()
        } elif check_kind("LET") {
            parse_let_stmt(true)
        } else {
            let expr_r = parse_expr(0, true)
            emit_line("(void)" + expr_r.val + ";")
        }
    }

    g_tokens = saved_tokens
    g_pos = saved_pos
    g_ns = saved_ns
}

fn parse_fn_decl() -> unit {
    expect_kind("FN")
    let name_tok = expect_kind("IDENT")
    expect_kind("LPAREN")
    let mut param_names: list[str] = []
    if not check_kind("RPAREN") {
        let p0 = expect_kind("IDENT")
        expect_kind("COLON")
        parse_type_ann()
        param_names.append(p0.val)
        while match_kind("COMMA") {
            if check_kind("RPAREN") {
                break
            }
            let pn = expect_kind("IDENT")
            expect_kind("COLON")
            parse_type_ann()
            param_names.append(pn.val)
        }
    }
    expect_kind("RPAREN")

    let mut fallible = false
    if match_kind("ARROW") {
        fallible = parse_type_ann()
    }

    let mut sig = "void"
    if len(param_names) > 0 {
        sig = ""
        for idx in 0..len(param_names) {
            if idx > 0 { sig = sig + ", " }
            sig = sig + "WVal v_" + param_names[idx]
        }
    }

    let c_name = c_fn_name(name_tok.val)
    g_protos.append("static WVal " + c_name + "(" + sig + ");")

    let prev_fallible = g_fn_fallible
    g_fn_fallible = fallible

    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty

    for p in param_names {
        emit_line("v_" + p + " = w_clone(v_" + p + ");")
    }
    let ret_v = parse_block_expr()
    if g_fn_fallible {
        emit_line("return w_ok(" + ret_v + ");")
    } else {
        emit_line("return " + ret_v + ";")
    }

    let body_lines = g_cur_stmts
    g_cur_stmts = saved
    g_fn_fallible = prev_fallible

    let mut fn_str = "static WVal " + c_name + "(" + sig + ") {\n"
    for l in body_lines {
        fn_str = fn_str + "    " + l + "\n"
    }
    fn_str = fn_str + "}"
    g_fn_defs.append(fn_str)
}

fn compile_source(src: str) -> str {
    g_tokens = tokenize(src)
    g_pos = 0
    g_temp_id = 0
    g_fn_fallible = false
    g_ns = ""
    let empty_s: list[str] = []
    let empty_i: list[int] = []
    let empty_c: list[ClassMeta] = []
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
    if not has_top_stmts and has_main_fn {
        out = out + "    w_fn_main();\n"
    }
    out = out + "    return 0;\n"
    out = out + "}\n"
    return out
}

fn run_compiler() -> unit ! IoError {
    let cli = args()
    let mut in_path = "selfhost/w1.w"
    let mut out_path = "build/compiler1.c"
    if len(cli) >= 3 {
        in_path = cli[1]
        out_path = cli[2]
    }
    let src = read_file(in_path)?
    let c_code = compile_source(src)
    write_file(out_path, c_code)?
    print("[W1] Compiled", in_path, "->", out_path)
}

let res = run_compiler() else err {
    print("W1 Error:", err.message)
}
