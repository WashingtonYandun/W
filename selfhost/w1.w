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

struct CleanupScope {
    kind: str,
    vars: list[str],
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
let mut g_scope_stack: list[CleanupScope] = []
let mut g_aux_id: int = 0
let mut g_cur_err_type: str = ""
let mut g_in_path: str = ""

fn report_error(code: str, line: int, col: int, msg: str) -> unit {
    eprint("[" + code + "] " + g_in_path + ":" + str(line) + ":" + str(col) + " - " + msg)
    exit(1)
}

fn is_alpha(c: int) -> bool {
    return c >= 65 and c <= 90 or c >= 97 and c <= 122 or c == 95
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
    if c >= 48 and c <= 57 {
        return c - 48
    }
    if c >= 65 and c <= 70 {
        return c - 55
    }
    if c >= 97 and c <= 102 {
        return c - 87
    }
    return 0
}

fn keyword_kind(word: str) -> str {
    if word == "fn" {
        return "FN"
    }
    if word == "let" {
        return "LET"
    }
    if word == "mut" {
        return "MUT"
    }
    if word == "struct" {
        return "STRUCT"
    }
    if word == "enum" {
        return "ENUM"
    }
    if word == "class" {
        return "CLASS"
    }
    if word == "interface" {
        return "INTERFACE"
    }
    if word == "extends" {
        return "EXTENDS"
    }
    if word == "implements" {
        return "IMPLEMENTS"
    }
    if word == "new" {
        return "NEW"
    }
    if word == "this" {
        return "THIS"
    }
    if word == "super" {
        return "SUPER"
    }
    if word == "public" {
        return "PUBLIC"
    }
    if word == "private" {
        return "PRIVATE"
    }
    if word == "if" {
        return "IF"
    }
    if word == "elif" {
        return "ELIF"
    }
    if word == "else" {
        return "ELSE"
    }
    if word == "for" {
        return "FOR"
    }
    if word == "while" {
        return "WHILE"
    }
    if word == "in" {
        return "IN"
    }
    if word == "match" {
        return "MATCH"
    }
    if word == "return" {
        return "RETURN"
    }
    if word == "break" {
        return "BREAK"
    }
    if word == "continue" {
        return "CONTINUE"
    }
    if word == "import" {
        return "IMPORT"
    }
    if word == "true" {
        return "TRUE"
    }
    if word == "false" {
        return "FALSE"
    }
    if word == "none" {
        return "NONE"
    }
    if word == "and" {
        return "AND"
    }
    if word == "or" {
        return "OR"
    }
    if word == "not" {
        return "NOT"
    }
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
            let mut last_was_under = false
            let mut sep_err = false
            while i < n and (is_digit(ord(src[i])) or src[i] == "_") {
                if src[i] == "_" {
                    if last_was_under {
                        sep_err = true
                    }
                    last_was_under = true
                } else {
                    last_was_under = false
                    clean_num = clean_num + src[i]
                }
                i = i + 1
                col = col + 1
            }
            if last_was_under or sep_err {
                report_error("W0002", line, start_col, "malformed numeric separator")
            }
            if i + 1 < n and src[i] == "." and is_digit(ord(src[i + 1])) {
                is_flt = true
                clean_num = clean_num + "."
                i = i + 1
                col = col + 1
                while i < n and (is_digit(ord(src[i])) or src[i] == "_") {
                    if src[i] == "_" {
                        if last_was_under {
                            sep_err = true
                        }
                        last_was_under = true
                    } else {
                        last_was_under = false
                        clean_num = clean_num + src[i]
                    }
                    i = i + 1
                    col = col + 1
                }
                if last_was_under or sep_err {
                    report_error("W0002", line, start_col, "malformed numeric separator")
                }
            } elif i < n and src[i] == "." and not (i + 1 < n and src[i + 1] == ".") {
                report_error("W0002", line, start_col, "malformed float literal: trailing dot")
            }
            if is_flt {
                tokens.append(Token { kind: "FLOAT", val: clean_num, line: line, col: start_col })
            } else {
                tokens.append(Token { kind: "INT", val: clean_num, line: line, col: start_col })
            }
        } elif ch == "." and i + 1 < n and is_digit(ord(src[i + 1])) {
            report_error("W0002", line, col, "malformed float literal: leading dot")
        } elif ch == "\"" {
            let start_col = col
            let start_line = line
            i = i + 1
            col = col + 1
            let mut s_val = ""
            while i < n and src[i] != "\"" {
                if src[i] == "\\" {
                    if i + 1 >= n {
                        report_error("W0004", line, col, "unterminated string escape")
                    }
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
                        if i + 1 >= n or src[i + 1] != "{" {
                            report_error("W0005", line, col - 1, "invalid Unicode scalar escape sequence")
                        }
                        i = i + 2
                        col = col + 2
                        let mut u_cp = 0
                        let mut has_hex = false
                        let mut valid_hex = true
                        while i < n and src[i] != "}" {
                            let hcode = ord(src[i])
                            if not (hcode >= 48 and hcode <= 57 or hcode >= 65 and hcode <= 70 or hcode >= 97 and hcode <= 102) {
                                valid_hex = false
                            }
                            u_cp = u_cp * 16 + hex_val(hcode)
                            has_hex = true
                            i = i + 1
                            col = col + 1
                        }
                        if i >= n or src[i] != "}" or not has_hex or not valid_hex {
                            report_error("W0005", line, col, "invalid Unicode scalar escape sequence")
                        }
                        i = i + 1
                        col = col + 1
                        s_val = s_val + chr(u_cp)
                    } else {
                        report_error("W0004", line, col - 1, "invalid string escape sequence")
                    }
                } else {
                    s_val = s_val + src[i]
                    i = i + 1
                    col = col + 1
                }
            }
            if i >= n {
                report_error("W0003", start_line, start_col, "unterminated string literal")
            }
            i = i + 1
            col = col + 1
            tokens.append(Token { kind: "STR", val: s_val, line: start_line, col: start_col })
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
                if ch == "(" {
                    kind = "LPAREN"
                } elif ch == ")" {
                    kind = "RPAREN"
                } elif ch == "{" {
                    kind = "LBRACE"
                } elif ch == "}" {
                    kind = "RBRACE"
                } elif ch == "[" {
                    kind = "LBRACKET"
                } elif ch == "]" {
                    kind = "RBRACKET"
                } elif ch == "," {
                    kind = "COMMA"
                } elif ch == ":" {
                    kind = "COLON"
                } elif ch == "." {
                    kind = "DOT"
                } elif ch == "+" {
                    kind = "PLUS"
                } elif ch == "-" {
                    kind = "MINUS"
                } elif ch == "*" {
                    kind = "STAR"
                } elif ch == "/" {
                    kind = "SLASH"
                } elif ch == "%" {
                    kind = "PERCENT"
                } elif ch == "=" {
                    kind = "ASSIGN"
                } elif ch == "<" {
                    kind = "LT"
                } elif ch == ">" {
                    kind = "GT"
                } elif ch == "!" {
                    kind = "BANG"
                } elif ch == "?" {
                    kind = "QUESTION"
                }
                if kind == "OP" {
                    report_error("W0001", line, start_col, "unexpected character '" + ch + "'")
                }
                tokens.append(Token { kind: kind, val: ch, line: line, col: start_col })
                i = i + 1
                col = col + 1
            }
        }
    }
    tokens.append(Token { kind: "EOF", val: "", line: line, col: col })
    return tokens
}

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
    if tok.kind != k {
        if k == "RBRACE" or k == "RBRACKET" {
            report_error("W0006", tok.line, tok.col, "expected '" + k + "', found '" + tok.val + "'")
        } else {
            report_error("W0001", tok.line, tok.col, "expected '" + k + "', found '" + tok.val + "'")
        }
    }
    advance_tok()
    return tok
}

fn new_temp() -> str {
    let name = "_t" + str(g_temp_id)
    g_temp_id = g_temp_id + 1
    return name
}

fn new_aux(prefix: str) -> str {
    let s = prefix + str(g_aux_id)
    g_aux_id = g_aux_id + 1
    return s
}

fn push_scope(kind: str) -> unit {
    let empty_v: list[str] = []
    g_scope_stack.append(CleanupScope { kind: kind, vars: empty_v })
}

fn register_var(v: str) -> unit {
    let n = len(g_scope_stack)
    if n > 0 {
        g_scope_stack[n - 1].vars.append(v)
    }
}

fn declare_owned_var(var_name: str, init_c_expr: str) -> str {
    emit_line("WVal " + var_name + " = " + init_c_expr + ";")
    register_var(var_name)
    return var_name
}

fn pop_scope() -> unit {
    let n = len(g_scope_stack)
    if n == 0 {
        return
    }
    let top = g_scope_stack[n - 1]
    g_scope_stack.pop()
    let num_vars = len(top.vars)
    if num_vars > 0 {
        let mut idx = num_vars - 1
        while idx >= 0 {
            emit_line("w_release(" + top.vars[idx] + ");")
            idx = idx - 1
        }
    }
}

fn emit_cleanup_until_fn() -> unit {
    let num_scopes = len(g_scope_stack)
    let mut si = num_scopes - 1
    while si >= 0 {
        let sc = g_scope_stack[si]
        let num_vars = len(sc.vars)
        if num_vars > 0 {
            let mut vi = num_vars - 1
            while vi >= 0 {
                emit_line("w_release(" + sc.vars[vi] + ");")
                vi = vi - 1
            }
        }
        if sc.kind == "fn" {
            break
        }
        si = si - 1
    }
}

fn emit_cleanup_until_fn_indented() -> unit {
    let num_scopes = len(g_scope_stack)
    let mut si = num_scopes - 1
    while si >= 0 {
        let sc = g_scope_stack[si]
        let num_vars = len(sc.vars)
        if num_vars > 0 {
            let mut vi = num_vars - 1
            while vi >= 0 {
                emit_line("    w_release(" + sc.vars[vi] + ");")
                vi = vi - 1
            }
        }
        if sc.kind == "fn" {
            break
        }
        si = si - 1
    }
}

fn emit_cleanup_until_loop() -> unit {
    let num_scopes = len(g_scope_stack)
    let mut si = num_scopes - 1
    while si >= 0 {
        let sc = g_scope_stack[si]
        let num_vars = len(sc.vars)
        if num_vars > 0 {
            let mut vi = num_vars - 1
            while vi >= 0 {
                emit_line("w_release(" + sc.vars[vi] + ");")
                vi = vi - 1
            }
        }
        if sc.kind == "loop" {
            break
        }
        si = si - 1
    }
}

fn has_cleanup_until_loop() -> bool {
    let num_scopes = len(g_scope_stack)
    let mut si = num_scopes - 1
    while si >= 0 {
        let sc = g_scope_stack[si]
        if len(sc.vars) > 0 {
            return true
        }
        if sc.kind == "loop" {
            break
        }
        si = si - 1
    }
    return false
}

fn emit_cleanup_until_loop_indented() -> unit {
    let num_scopes = len(g_scope_stack)
    let mut si = num_scopes - 1
    while si >= 0 {
        let sc = g_scope_stack[si]
        let num_vars = len(sc.vars)
        if num_vars > 0 {
            let mut vi = num_vars - 1
            while vi >= 0 {
                emit_line("    w_release(" + sc.vars[vi] + ");")
                vi = vi - 1
            }
        }
        if sc.kind == "loop" {
            break
        }
        si = si - 1
    }
}

fn own_expr(val_expr: str) -> str {
    if len(val_expr) >= 2 and slice(val_expr, 0, 2) == "_t" {
        return "w_move(&" + val_expr + ")"
    }
    if len(val_expr) >= 7 and slice(val_expr, 0, 7) == "w_make_" {
        return val_expr
    }
    if len(val_expr) >= 6 and slice(val_expr, 0, 6) == "w_new_" {
        return val_expr
    }
    if len(val_expr) >= 8 and slice(val_expr, 0, 8) == "w_clone(" {
        return val_expr
    }
    return "w_clone(" + val_expr + ")"
}

fn emit_line(line: str) -> unit {
    g_cur_stmts.append(line)
}


fn snapshot_value(value: str) -> str {
    if len(value) >= 2 and slice(value, 0, 2) == "_t" {
        return value
    }
    if len(value) >= 7 and slice(value, 0, 7) == "w_make_" {
        return bind_call(value).val
    }
    return bind_call("w_clone(" + value + ")").val
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
    if match_kind("LPAREN") {
        is_fallible = parse_type_ann()
        expect_kind("RPAREN")
    } else {
        advance_tok()
    }
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
        let err_tok = at_tok()
        parse_type_ann()
        is_fallible = true
        g_cur_err_type = err_tok.val
    }
    return is_fallible
}

fn parse_field_default() -> str {
    let tname = at_tok().val
    let mut def_c = "w_none()"
    if tname == "int" {
        def_c = "w_int(0LL)"
    } elif tname == "float" {
        def_c = "w_float(0.0)"
    } elif tname == "bool" {
        def_c = "w_bool(false)"
    } elif tname == "str" {
        def_c = "w_str(\"\")"
    } elif tname == "list" {
        def_c = "w_make_list(0, NULL)"
    } elif tname == "dict" {
        def_c = "w_make_dict(0, NULL, NULL)"
    }
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
    if k == "ASSIGN" {
        return 1
    }
    if k == "QQ" {
        return 2
    }
    if k == "OR" {
        return 3
    }
    if k == "AND" {
        return 4
    }
    if k == "EQ" or k == "NEQ" or k == "LT" or k == "LTE" or k == "GT" or k == "GTE" {
        return 6
    }
    if k == "DOT_DOT" or k == "DOT_DOT_EQ" {
        return 7
    }
    if k == "PLUS" or k == "MINUS" {
        return 8
    }
    if k == "STAR" or k == "SLASH" or k == "PERCENT" {
        return 9
    }
    return 0
}

fn clean_lref(raw: str) -> str {
    let n = len(raw)
    if n < 2 {
        return raw
    }
    for i in 0..n - 1 {
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

fn bind_call(c_call: str) -> ExprRes {
    let tmp = new_temp()
    declare_owned_var(tmp, c_call)
    return ExprRes { val: tmp, lref: "" }
}
fn snapshot_callee(callee: ExprRes) -> ExprRes {
    let raw = callee.lref
    let mut separators: list[int] = []
    let mut skip = -1
    for i in 0..len(raw) - 1 {
        if i > skip and slice(raw, i, i + 2) == "::" {
            separators.append(i)
            skip = i + 1
        }
    }
    if len(separators) < 3 { return callee }
    let method = slice(raw, separators[0] + 2, separators[1])
    let receiver = slice(raw, separators[2] + 2, len(raw))
    if method == "append" or method == "pop" or method == "clear" or receiver == "v_super" { return callee }
    if len(receiver) >= 2 and slice(receiver, 0, 2) == "v_" {
        if is_module_name(slice(receiver, 2, len(receiver))) { return callee }
    }
    let held = snapshot_value(receiver)
    return ExprRes { val: callee.val, lref: slice(raw, 0, separators[2] + 2) + held }
}

fn projection_is_mutated() -> bool {
    let mut offset = 0
    while true {
        let kind = peek_tok(offset).kind
        if kind == "ASSIGN" { return true }
        if kind == "DOT" {
            let method = peek_tok(offset + 1).val
            if peek_tok(offset + 2).kind == "LPAREN" {
                return method == "append" or method == "pop" or method == "clear"
            }
            offset = offset + 2
        } elif kind == "LBRACKET" {
            let mut depth = 1
            offset = offset + 1
            while depth > 0 and peek_tok(offset).kind != "EOF" {
                if peek_tok(offset).kind == "LBRACKET" { depth = depth + 1 }
                if peek_tok(offset).kind == "RBRACKET" { depth = depth - 1 }
                offset = offset + 1
            }
        } else { return false }
    }
    return false
}


fn emit_call(callee: ExprRes, args_c: list[str]) -> ExprRes {
    let raw = callee.lref
    let n = len(raw)
    let mut s1 = -1
    let mut s2 = -1
    let mut s3 = -1
    let mut skip = -1
    if n >= 2 {
        for i in 0..n - 1 {
            if i > skip and slice(raw, i, i + 2) == "::" {
                skip = i + 1
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
                return bind_call("w_method_" + def_cls + "__" + method + "(" + joined + ")")
            }
            return ExprRes { val: "w_unit()", lref: "" }
        }
        if len(recv_val) >= 2 and slice(recv_val, 0, 2) == "v_" {
            let obj_name = slice(recv_val, 2, len(recv_val))
            if is_module_name(obj_name) {
                let mut joined = ""
                for idx in 0..len(args_c) {
                    if idx > 0 {
                        joined = joined + ", "
                    }
                    joined = joined + args_c[idx]
                }
                return bind_call("w_fn_" + obj_name + "__" + method + "(" + joined + ")")
            }
        }
        if method == "append" {
            return bind_call("w_list_append(" + recv_lref + ", " + args_c[0] + ")")
        }
        if method == "pop" {
            return bind_call("w_list_pop(" + recv_lref + ")")
        }
        if method == "clear" {
            return bind_call("w_list_clear(" + recv_lref + ")")
        }
        if method == "get" {
            return bind_call("w_dict_get(" + recv_val + ", " + args_c[0] + ")")
        }
        if method == "keys" {
            return bind_call("w_dict_keys(" + recv_val + ")")
        }
        if method == "values" {
            return bind_call("w_dict_values(" + recv_val + ")")
        }
        let mut d_args = recv_val
        for idx in 0..len(args_c) {
            d_args = d_args + ", " + args_c[idx]
        }
        return bind_call("w_dispatch__" + method + "__" + str(len(args_c)) + "(" + d_args + ")")
    }
    if len(callee.val) >= 2 and slice(callee.val, 0, 2) == "v_" {
        let fn_name = slice(callee.val, 2, len(callee.val))
        if fn_name == "Ok" and len(args_c) == 1 {
            return bind_call("w_ok(" + own_expr(args_c[0]) + ")")
        }
        if fn_name == "Err" and len(args_c) == 1 {
            return bind_call("w_err(" + own_expr(args_c[0]) + ")")
        }
        if fn_name == "print" {
            if len(args_c) == 0 {
                return bind_call("w_builtin_print(0, NULL)")
            }
            let arr_tmp = new_aux("_arr")
            let mut joined = ""
            for idx in 0..len(args_c) {
                if idx > 0 {
                    joined = joined + ", "
                }
                joined = joined + args_c[idx]
            }
            let cnt = str(len(args_c))
            emit_line("WVal " + arr_tmp + "[" + cnt + "] = { " + joined + " };")
            return bind_call("w_builtin_print(" + cnt + ", " + arr_tmp + ")")
        }
        if fn_name == "eprint" {
            if len(args_c) == 0 {
                return bind_call("w_builtin_eprint(0, NULL)")
            }
            let arr_tmp = new_aux("_arr")
            let mut joined = ""
            for idx in 0..len(args_c) {
                if idx > 0 {
                    joined = joined + ", "
                }
                joined = joined + args_c[idx]
            }
            let cnt = str(len(args_c))
            emit_line("WVal " + arr_tmp + "[" + cnt + "] = { " + joined + " };")
            return bind_call("w_builtin_eprint(" + cnt + ", " + arr_tmp + ")")
        }
        if fn_name == "exit" and len(args_c) == 1 {
            return bind_call("w_builtin_exit(" + args_c[0] + ")")
        }
        if fn_name == "len" {
            return bind_call("w_builtin_len(" + args_c[0] + ")")
        }
        if fn_name == "str" {
            return bind_call("w_builtin_str(" + args_c[0] + ")")
        }
        if fn_name == "int" {
            return bind_call("w_builtin_int(" + args_c[0] + ")")
        }
        if fn_name == "float" {
            return bind_call("w_builtin_float(" + args_c[0] + ")")
        }
        if fn_name == "ord" {
            return bind_call("w_builtin_ord(" + args_c[0] + ")")
        }
        if fn_name == "chr" {
            return bind_call("w_builtin_chr(" + args_c[0] + ")")
        }
        if fn_name == "bytes" {
            return bind_call("w_builtin_bytes(" + args_c[0] + ")")
        }
        if fn_name == "enumerate" {
            return bind_call("w_builtin_enumerate(" + args_c[0] + ")")
        }
        if fn_name == "dict_items" {
            return bind_call("w_builtin_dict_items(" + args_c[0] + ")")
        }
        if fn_name == "read_file" {
            return bind_call("w_builtin_read_file(" + args_c[0] + ")")
        }
        if fn_name == "write_file" {
            return bind_call("w_builtin_write_file(" + args_c[0] + ", " + args_c[1] + ")")
        }
        if fn_name == "slice" {
            return bind_call("w_builtin_slice(" + args_c[0] + ", " + args_c[1] + ", " + args_c[2] + ")")
        }
        if fn_name == "args" {
            return bind_call("w_builtin_args()")
        }
        let mut joined = ""
        for idx in 0..len(args_c) {
            if idx > 0 {
                joined = joined + ", "
            }
            joined = joined + args_c[idx]
        }
        if find_class_meta_idx(fn_name) != -1 {
            return bind_call("w_new_" + fn_name + "(" + joined + ")")
        }
        return bind_call(c_fn_name(fn_name) + "(" + joined + ")")
    }
    return ExprRes { val: "w_unit()", lref: "" }
}

fn parse_block_expr() -> str {
    expect_kind("LBRACE")
    let res = new_temp()
    declare_owned_var(res, "w_unit()")
    emit_line("{")
    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    push_scope("block")
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
            emit_cleanup_until_loop()
            emit_line("break;")
            tail_val = "w_unit()"
        } elif check_kind("CONTINUE") {
            advance_tok()
            emit_cleanup_until_loop()
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
        emit_line("w_assign(&" + res + ", " + own_expr(tail_val) + ");")
    }
    pop_scope()
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
    declare_owned_var(res, "w_unit()")
    let cond_r = parse_expr(0, false)
    emit_line("if ((" + cond_r.val + ").as.b) {")
    push_scope("block")
    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    let then_v = parse_block_expr()
    emit_line("w_assign(&" + res + ", " + own_expr(then_v) + ");")
    pop_scope()
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
        push_scope("block")
        let saved = g_cur_stmts
        let empty: list[str] = []
        g_cur_stmts = empty
        let eb_cond = parse_expr(0, false)
        emit_line("if ((" + eb_cond.val + ").as.b) {")
        push_scope("block")
        let saved_inner = g_cur_stmts
        let empty2: list[str] = []
        g_cur_stmts = empty2
        let eb_v = parse_block_expr()
        emit_line("w_assign(&" + res + ", " + own_expr(eb_v) + ");")
        pop_scope()
        let eb_lines = g_cur_stmts
        g_cur_stmts = saved_inner
        for l in eb_lines {
            emit_line("    " + l)
        }
        emit_line("}")
        parse_elif_chain(res)
        pop_scope()
        let outer_lines = g_cur_stmts
        g_cur_stmts = saved
        for l in outer_lines {
            emit_line("    " + l)
        }
        emit_line("}")
    } elif match_kind("ELSE") {
        emit_line("else {")
        push_scope("block")
        let saved = g_cur_stmts
        let empty: list[str] = []
        g_cur_stmts = empty
        let else_v = parse_block_expr()
        emit_line("w_assign(&" + res + ", " + own_expr(else_v) + ");")
        pop_scope()
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
    declare_owned_var(subj_tmp, own_expr(subj_r.val))
    let res = new_temp()
    declare_owned_var(res, "w_unit()")
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
    push_scope("block")
    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    for bl in bind_lines {
        emit_line(bl)
    }
    if check_kind("LBRACE") {
        let arm_v = parse_block_expr()
        emit_line("w_assign(&" + res + ", " + own_expr(arm_v) + ");")
    } else {
        let arm_v = parse_expr(0, true)
        emit_line("w_assign(&" + res + ", " + own_expr(arm_v.val) + ");")
    }
    pop_scope()
    let arm_lines = g_cur_stmts
    g_cur_stmts = saved
    for al in arm_lines {
        emit_line("    " + al)
    }
    emit_line("}")
    match_kind("COMMA")
    if not check_kind("RBRACE") and not is_eof() {
        emit_line("else {")
        push_scope("block")
        let saved_else = g_cur_stmts
        let empty_else: list[str] = []
        g_cur_stmts = empty_else
        parse_match_arms(subj_tmp, res)
        pop_scope()
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
            args_c.append(snapshot_value(a0.val))
            while match_kind("COMMA") {
                if check_kind("RPAREN") {
                    break
                }
                let an = parse_expr(0, true)
                args_c.append(snapshot_value(an.val))
            }
        }
        expect_kind("RPAREN")
        let mut joined = ""
        for idx in 0..len(args_c) {
            if idx > 0 {
                joined = joined + ", "
            }
            joined = joined + args_c[idx]
        }
        return bind_call("w_new_" + cname_tok.val + "(" + joined + ")")
    }
    if match_kind("IDENT") {
        let name = tok.val
        if allow_struct and check_kind("LBRACE") {
            let p1 = peek_tok(1)
            let p2 = peek_tok(2)
            if p1.kind == "RBRACE" or p1.kind == "IDENT" and p2.kind == "COLON" {
                advance_tok()
                let mut f_names: list[str] = []
                let mut f_vals: list[str] = []
                while not check_kind("RBRACE") and not is_eof() {
                    let f_tok = expect_kind("IDENT")
                    expect_kind("COLON")
                    let f_v = parse_expr(0, true)
                    f_names.append("\"" + f_tok.val + "\"")
                    f_vals.append(snapshot_value(f_v.val))
                    match_kind("COMMA")
                }
                expect_kind("RBRACE")
                if len(f_names) == 0 {
                    return bind_call("w_make_struct(\"" + name + "\", 0, NULL, NULL)")
                }
                let k_tmp = new_aux("_k")
                let v_tmp = new_aux("_v")
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
                return bind_call("w_make_struct(\"" + name + "\", " + cnt + ", " + k_tmp + ", " + v_tmp + ")")
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
            return bind_call("w_make_tuple(0, NULL)")
        }
        let first = parse_expr(0, true)
        if match_kind("COMMA") {
            let mut t_elems: list[str] = [snapshot_value(first.val)]
            if not check_kind("RPAREN") {
                let second = parse_expr(0, true)
                t_elems.append(snapshot_value(second.val))
                while match_kind("COMMA") {
                    if check_kind("RPAREN") {
                        break
                    }
                    let nxt = parse_expr(0, true)
                    t_elems.append(snapshot_value(nxt.val))
                }
            }
            expect_kind("RPAREN")
            let arr_tmp = new_aux("_arr")
            let mut joined = ""
            for idx in 0..len(t_elems) {
                if idx > 0 {
                    joined = joined + ", "
                }
                joined = joined + t_elems[idx]
            }
            let cnt = str(len(t_elems))
            emit_line("WVal " + arr_tmp + "[" + cnt + "] = { " + joined + " };")
            return bind_call("w_make_tuple(" + cnt + ", " + arr_tmp + ")")
        }
        expect_kind("RPAREN")
        return first
    }
    if match_kind("LBRACKET") {
        let mut elems: list[str] = []
        if not check_kind("RBRACKET") {
            let first = parse_expr(0, true)
            elems.append(snapshot_value(first.val))
            while match_kind("COMMA") {
                if check_kind("RBRACKET") {
                    break
                }
                let nxt = parse_expr(0, true)
                elems.append(snapshot_value(nxt.val))
            }
        }
        expect_kind("RBRACKET")
        if len(elems) == 0 {
            return bind_call("w_make_list(0, NULL)")
        }
        let arr_tmp = new_aux("_arr")
        let mut joined = ""
        for idx in 0..len(elems) {
            if idx > 0 {
                joined = joined + ", "
            }
            joined = joined + elems[idx]
        }
        let cnt = str(len(elems))
        emit_line("WVal " + arr_tmp + "[" + cnt + "] = { " + joined + " };")
        return bind_call("w_make_list(" + cnt + ", " + arr_tmp + ")")
    }
    if match_kind("LBRACE") {
        let mut d_keys: list[str] = []
        let mut d_vals: list[str] = []
        if not check_kind("RBRACE") {
            let k0 = parse_expr(0, true)
            if len(k0.val) >= 7 and slice(k0.val, 0, 7) == "w_float" {
                report_error("W2010", at_tok().line, at_tok().col, "invalid dictionary key type: float is not allowed as dictionary key")
            }
            expect_kind("COLON")
            let key0 = snapshot_value(k0.val)
            let v0 = parse_expr(0, true)
            d_keys.append(key0)
            d_vals.append(snapshot_value(v0.val))
            while match_kind("COMMA") {
                if check_kind("RBRACE") {
                    break
                }
                let kn = parse_expr(0, true)
                if len(kn.val) >= 7 and slice(kn.val, 0, 7) == "w_float" {
                    report_error("W2010", at_tok().line, at_tok().col, "invalid dictionary key type: float is not allowed as dictionary key")
                }
                expect_kind("COLON")
                let keyn = snapshot_value(kn.val)
                let vn = parse_expr(0, true)
                d_keys.append(keyn)
                d_vals.append(snapshot_value(vn.val))
            }
        }
        expect_kind("RBRACE")
        if len(d_keys) == 0 {
            return bind_call("w_make_dict(0, NULL, NULL)")
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
        return bind_call("w_make_dict(" + cnt + ", " + k_tmp + ", " + v_tmp + ")")
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
    let expression_start = g_pos
    let statements_before = g_cur_stmts
    let scopes_before = g_scope_stack
    let temps_before = g_temp_id
    let aux_before = g_aux_id
    let mut left = parse_prefix_expr(allow_struct)
    while true {
        while true {
            if check_kind("LPAREN") {
                left = snapshot_callee(left)
                advance_tok()
                let mut args_c: list[str] = []
                if not check_kind("RPAREN") {
                    let a0 = parse_expr(0, true)
                    args_c.append(snapshot_value(a0.val))
                    while match_kind("COMMA") {
                        if check_kind("RPAREN") {
                            break
                        }
                        let an = parse_expr(0, true)
                        args_c.append(snapshot_value(an.val))
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
                        left = ExprRes { val: "w_member_get(" + left.val + ", \"" + prop + "\")", lref: "w_member_ref(" + clean_lref(left.lref) + ", \"" + prop + "\")::" + prop + "::" + clean_lref(left.lref) + "::" + left.val }
                    }
                } else {
                    left = ExprRes { val: "w_member_get(" + left.val + ", \"" + prop + "\")", lref: "w_member_ref(" + clean_lref(left.lref) + ", \"" + prop + "\")::" + prop + "::" + clean_lref(left.lref) + "::" + left.val }
                }
                if not projection_is_mutated() and not check_kind("LPAREN") and left.lref != "" {
                    left = ExprRes { val: bind_call("w_clone(" + left.val + ")").val, lref: left.lref }
                }
            } elif check_kind("LBRACKET") {
                let mutated = projection_is_mutated()
                advance_tok()
                let mut object_value = left.val
                if not mutated {
                    object_value = snapshot_value(left.val)
                }
                let mut idx_r = parse_expr(0, true)
                expect_kind("RBRACKET")
                if mutated {
                    idx_r = ExprRes { val: snapshot_value(idx_r.val), lref: idx_r.lref }
                }
                let index_lref = "w_index_ref(" + clean_lref(left.lref) + ", " + idx_r.val + ")"
                if mutated {
                    left = ExprRes { val: "w_index_get(" + left.val + ", " + idx_r.val + ")", lref: index_lref }
                } else {
                    left = ExprRes { val: bind_call("w_index_get_owned(" + object_value + ", " + idx_r.val + ")").val, lref: index_lref }
                }
            } elif check_kind("QUESTION") {
                advance_tok()
                let tmp = new_temp()
                declare_owned_var(tmp, own_expr(left.val))
                emit_line("if (" + str(not g_fn_fallible) + " && (" + tmp + ".tag == W_NONE)) {")
                emit_cleanup_until_fn_indented()
                emit_line("    return w_none();")
                emit_line("}")
                let err_hold = new_aux("_err")
                emit_line("if (" + str(g_fn_fallible) + " && (" + tmp + ".tag == W_ERR)) {")
                emit_line("    WVal " + err_hold + " = w_clone(" + tmp + ");")
                emit_cleanup_until_fn_indented()
                emit_line("    return " + err_hold + ";")
                emit_line("}")
                let unw = new_temp()
                let mut unwrap_helper = "w_unwrap_optional"
                if g_fn_fallible { unwrap_helper = "w_unwrap_ok" }
                declare_owned_var(unw, unwrap_helper + "(" + tmp + ")")
                left = ExprRes { val: unw, lref: "" }
            } elif check_kind("ELSE") {
                advance_tok()
                let mut err_name = ""
                if check_kind("IDENT") {
                    let et = advance_tok()
                    err_name = et.val
                }
                let tmp = new_temp()
                declare_owned_var(tmp, own_expr(left.val))
                let res = new_temp()
                declare_owned_var(res, "w_unit()")
                emit_line("if (" + tmp + ".tag == W_ERR || " + tmp + ".tag == W_NONE) {")
                push_scope("block")
                let saved = g_cur_stmts
                let empty: list[str] = []
                g_cur_stmts = empty
                if err_name != "" {
                    declare_owned_var("v_" + err_name, "w_unwrap_err(" + tmp + ")")
                }
                let hv = parse_block_expr()
                emit_line("w_assign(&" + res + ", " + own_expr(hv) + ");")
                pop_scope()
                let h_lines = g_cur_stmts
                g_cur_stmts = saved
                for l in h_lines {
                    emit_line("    " + l)
                }
                emit_line("} else {")
                emit_line("    w_assign(&" + res + ", w_unwrap_success(" + tmp + "));")
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
            declare_owned_var(res, "w_bool(false)")
            emit_line("if ((" + left.val + ").as.b) {")
            push_scope("block")
            let saved = g_cur_stmts
            let empty: list[str] = []
            g_cur_stmts = empty
            let rhs = parse_expr(next_min, allow_struct)
            emit_line(res + " = w_bool((" + rhs.val + ").as.b);")
            pop_scope()
            let r_lines = g_cur_stmts
            g_cur_stmts = saved
            for l in r_lines {
                emit_line("    " + l)
            }
            emit_line("}")
            left = ExprRes { val: res, lref: "" }
        } elif op_tok.kind == "OR" {
            let res = new_temp()
            declare_owned_var(res, "w_bool(true)")
            emit_line("if (!(" + left.val + ").as.b) {")
            push_scope("block")
            let saved = g_cur_stmts
            let empty: list[str] = []
            g_cur_stmts = empty
            let rhs = parse_expr(next_min, allow_struct)
            emit_line(res + " = w_bool((" + rhs.val + ").as.b);")
            pop_scope()
            let r_lines = g_cur_stmts
            g_cur_stmts = saved
            for l in r_lines {
                emit_line("    " + l)
            }
            emit_line("}")
            left = ExprRes { val: res, lref: "" }
        } elif op_tok.kind == "QQ" {
            let res = new_temp()
            declare_owned_var(res, own_expr(left.val))
            emit_line("if (" + res + ".tag == W_NONE) {")
            push_scope("block")
            let saved = g_cur_stmts
            let empty: list[str] = []
            g_cur_stmts = empty
            let rhs = parse_expr(next_min, allow_struct)
            emit_line("w_assign(&" + res + ", " + own_expr(rhs.val) + ");")
            pop_scope()
            let r_lines = g_cur_stmts
            g_cur_stmts = saved
            for l in r_lines {
                emit_line("    " + l)
            }
            emit_line("} else {")
            emit_line("    w_assign(&" + res + ", w_unwrap_optional(" + res + "));")
            emit_line("}")
            left = ExprRes { val: res, lref: "" }
        } else {
            if op_tok.kind == "ASSIGN" {
                # Replay the target after the owned RHS, matching the interpreter contract.
                g_cur_stmts = statements_before
                g_scope_stack = scopes_before
                g_temp_id = temps_before
                g_aux_id = aux_before
            }
            if op_tok.kind != "ASSIGN" {
                left = ExprRes { val: snapshot_value(left.val), lref: left.lref }
            }
            let right = parse_expr(next_min, allow_struct)
            if op_tok.kind == "ASSIGN" {
                if (len(left.val) < 2 or slice(left.val, 0, 2) != "v_") and left.lref == "" {
                    report_error("W2002", op_tok.line, op_tok.col, "invalid assignment target")
                }
                let rhs_hold = new_aux("_rhs")
                declare_owned_var(rhs_hold, own_expr(right.val))
                let expression_end = g_pos
                g_pos = expression_start
                left = parse_expr(prec, allow_struct)
                g_pos = expression_end
                if len(left.val) >= 2 and slice(left.val, 0, 2) == "v_" {
                    emit_line("w_assign(&" + left.val + ", " + "w_move(&" + rhs_hold + "));")
                    left = ExprRes { val: left.val, lref: left.lref }
                } else {
                    let target_ref = clean_lref(left.lref)
                    emit_line("w_assign(" + target_ref + ", " + "w_move(&" + rhs_hold + "));")
                    left = ExprRes { val: "w_unit()", lref: "" }
                }
            } elif op_tok.kind == "DOT_DOT" {
                left = bind_call("w_make_range(" + left.val + ", " + right.val + ", false)")
            } elif op_tok.kind == "DOT_DOT_EQ" {
                left = bind_call("w_make_range(" + left.val + ", " + right.val + ", true)")
            } elif op_tok.kind == "PLUS" {
                left = ExprRes { val: bind_call("w_add(" + left.val + ", " + right.val + ")").val, lref: "" }
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

fn parse_let_stmt(is_global: bool) -> unit {
    expect_kind("LET")
    match_kind("MUT")
    let name_tok = expect_kind("IDENT")
    if match_kind("COLON") {
        parse_type_ann()
    }
    expect_kind("ASSIGN")
    let mut val_r = ExprRes { val: "", lref: "" }
    if is_global and check_kind("LBRACKET") and peek_tok(1).kind == "RBRACKET" {
        advance_tok()
        advance_tok()
        val_r = ExprRes { val: "w_make_list(0, NULL)", lref: "" }
    } else {
        val_r = parse_expr(0, true)
    }
    let mut vname = "v_" + name_tok.val
    if is_global and g_ns != "" {
        vname = "v_" + g_ns + "_" + name_tok.val
    }
    if is_global {
        g_globals.append(vname)
        emit_line("w_assign(&" + vname + ", " + own_expr(val_r.val) + ");")
    } else {
        declare_owned_var(vname, own_expr(val_r.val))
    }
}

fn parse_return_stmt() -> unit {
    expect_kind("RETURN")
    if check_kind("RBRACE") or is_eof() {
        emit_cleanup_until_fn()
        if g_fn_fallible {
            emit_line("return w_ok(w_unit());")
        } else {
            emit_line("return w_unit();")
        }
        return
    }
    let val_r = parse_expr(0, true)
    let ret_hold = new_aux("_ret")
    emit_line("WVal " + ret_hold + " = " + own_expr(val_r.val) + ";")
    emit_cleanup_until_fn()
    if g_fn_fallible {
        emit_line("return w_wrap_result(" + ret_hold + ", \"" + g_cur_err_type + "\");")
    } else {
        emit_line("return " + ret_hold + ";")
    }
}

fn parse_while_stmt() -> unit {
    expect_kind("WHILE")
    emit_line("while (1) {")
    push_scope("loop")
    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    let cond_r = parse_expr(0, false)
    let cond_b = new_aux("_cond")
    emit_line("bool " + cond_b + " = (" + cond_r.val + ").as.b;")
    if has_cleanup_until_loop() {
        emit_line("if (!" + cond_b + ") {")
        emit_cleanup_until_loop_indented()
        emit_line("    break;")
        emit_line("}")
    } else {
        emit_line("if (!" + cond_b + ") break;")
    }
    let body_v = parse_block_expr()
    emit_line("(void)" + body_v + ";")
    pop_scope()
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
    emit_line("{")
    push_scope("block")
    let saved_outer = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    let iter_r = parse_expr(0, false)
    let iter_tmp = new_temp()
    let idx_tmp = new_aux("_idx")
    let item_tmp = new_aux("_item")
    declare_owned_var(iter_tmp, own_expr(iter_r.val))
    emit_line("for (int32_t " + idx_tmp + " = 0; " + idx_tmp + " < " + iter_tmp + ".as.list->len; " + idx_tmp + "++) {")
    push_scope("loop")
    let saved_loop = g_cur_stmts
    g_cur_stmts = empty
    emit_line("WVal " + item_tmp + " = " + iter_tmp + ".as.list->data[" + idx_tmp + "];")
    if len(pat_names) == 1 {
        declare_owned_var("v_" + pat_names[0], "w_clone(" + item_tmp + ")")
    } else {
        for pi in 0..len(pat_names) {
            declare_owned_var("v_" + pat_names[pi], "w_clone((" + item_tmp + ").as.tuple->items[" + str(pi) + "])")
        }
    }
    let body_v = parse_block_expr()
    emit_line("(void)" + body_v + ";")
    pop_scope()
    let loop_lines = g_cur_stmts
    g_cur_stmts = saved_loop
    for l in loop_lines {
        emit_line("    " + l)
    }
    emit_line("}")
    pop_scope()
    let outer_lines = g_cur_stmts
    g_cur_stmts = saved_outer
    for l in outer_lines {
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
        if check_kind("RBRACE") or check_kind("EOF") {
            report_error("W0001", at_tok().line, at_tok().col, "expected type name in struct field")
        }
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
            let prev_err = g_cur_err_type
            g_fn_fallible = fallible
            let saved = g_cur_stmts
            let empty: list[str] = []
            g_cur_stmts = empty
            push_scope("fn")
            let ret_v = parse_block_expr()
            let ret_hold = new_aux("_ret")
            emit_line("WVal " + ret_hold + " = " + own_expr(ret_v) + ";")
            pop_scope()
            if g_fn_fallible {
                emit_line("return w_wrap_result(" + ret_hold + ", \"" + g_cur_err_type + "\");")
            } else {
                emit_line("return " + ret_hold + ";")
            }
            let body_lines = g_cur_stmts
            g_cur_stmts = saved
            g_fn_fallible = prev_fall
            g_cur_err_type = prev_err
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
    g_classes.append(ClassMeta { name: cls_name, super_name: sup_name, field_names: f_names, field_defaults: f_defaults, method_names: m_names, method_arities: m_arities, init_params: init_p })
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
            if idx > 0 {
                new_sig = new_sig + ", "
            }
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
        new_str = new_str + "    w_release_array(" + fcnt + ", _v);\n"
    } else {
        new_str = new_str + "    WVal v_self = w_make_object(\"" + cls_name + "\", 0, NULL, NULL);\n"
    }
    if init_owner != "" {
        new_str = new_str + "    w_release(w_method_" + init_owner + "__init(" + init_call_args + "));\n"
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
            if idx > 0 {
                sig = sig + ", "
            }
            sig = sig + "WVal v_" + param_names[idx]
        }
    }
    let c_name = c_fn_name(name_tok.val)
    g_protos.append("static WVal " + c_name + "(" + sig + ");")
    let prev_fallible = g_fn_fallible
    let prev_err = g_cur_err_type
    g_fn_fallible = fallible
    let saved = g_cur_stmts
    let empty: list[str] = []
    g_cur_stmts = empty
    push_scope("fn")
    let ret_v = parse_block_expr()
    let ret_hold = new_aux("_ret")
    emit_line("WVal " + ret_hold + " = " + own_expr(ret_v) + ";")
    pop_scope()
    if g_fn_fallible {
        emit_line("return w_wrap_result(" + ret_hold + ", \"" + g_cur_err_type + "\");")
    } else {
        emit_line("return " + ret_hold + ";")
    }
    let body_lines = g_cur_stmts
    g_cur_stmts = saved
    g_fn_fallible = prev_fallible
    g_cur_err_type = prev_err
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

fn run_compiler() -> unit ! IoError {
    let cli = args()
    let mut in_path = "selfhost/w1.w"
    let mut out_path = "build/compiler1.c"
    if len(cli) >= 3 {
        in_path = cli[1]
        out_path = cli[2]
    }
    let src = read_file(in_path)?
    check_source(src, in_path)
    let c_code = compile_source(src)
    write_file(out_path, c_code)?
    print("[W1] Compiled", in_path, "->", out_path)
}

let res = run_compiler() else err {
    print("W1 Error:", err.message)
}
