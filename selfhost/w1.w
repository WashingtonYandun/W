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
let mut g_enum_variant_names: list[str] = []
let mut g_enum_variant_owners: list[str] = []
let mut g_enum_variant_arities: list[int] = []
let mut g_pattern_bind_lines: list[str] = []
let mut g_pattern_bind_names: list[str] = []
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


let mut g_borrowed_vars: list[str] = []

# Standalone semantic parsing. Types are interned structures, never fixture names.
struct SemType { kind: str, name: str, args: list[int] }
struct SemGenericType { name: str, kind: str, params: list[str] }
struct SemVar { name: str, type_id: int, mutable: bool, depth: int }
struct SemFunction { name: str, params: list[str], type_params: list[str], constraints: list[str], type_id: int, body: int, end: int, owner: str, visible: bool }
struct SemField { owner: str, name: str, type_id: int, visible: bool }
struct SemClass { name: str, parent: str, interfaces: list[str] }
struct SemValue { type_id: int, root: str, writable: int, terminates: bool }
struct SemFlow { type_id: int, terminates: bool }
let mut sem_tokens: list[Token] = []
let mut sem_pos = 0
let mut sem_types: list[SemType] = []
let mut sem_generic_types: list[SemGenericType] = []
let mut sem_type_params: list[str] = []
let mut sem_active_constraints: list[str] = []
let mut sem_unify_names: list[str] = []
let mut sem_unify_types: list[int] = []
let mut sem_variables: list[SemVar] = []
let mut sem_functions: list[SemFunction] = []
let mut sem_fields: list[SemField] = []
let mut sem_classes: list[SemClass] = []
let mut sem_variants: list[str] = []
let mut sem_variant_types: list[int] = []
let mut sem_variant_payloads: list[list[int]] = []
let mut sem_depth = 0
let mut sem_return = 0
let mut sem_owner = ""
let mut sem_current_function = ""
let mut sem_layout_seen: list[str] = []
let mut sem_loop = 0
let mut sem_int = 0
let mut sem_float = 0
let mut sem_bool = 0
let mut sem_str = 0
let mut sem_unit = 0
let mut sem_none = 0
let mut sem_initializing = false
let mut sem_initialized: list[str] = []


struct SemLambda { position: int, line: int, col: int, params: list[str], captures: list[str], type_id: int }
let mut sem_lambdas: list[SemLambda] = []
let mut sem_capture_names: list[str] = []
let mut sem_capture_depth = -1

let mut sem_statement_context = false

let mut sem_token_offset = 0

let mut sem_indirect_positions: list[int] = []

let mut sem_class_projection_positions: list[int] = []

let mut sem_collection_call_positions: list[int] = []
let mut sem_result_lift_positions: list[int] = []
let mut sem_error_pattern_positions: list[int] = []
let mut sem_error_pattern_kinds: list[str] = []
let mut sem_error_pattern_names: list[str] = []
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
    if word == "as" { return "AS" }
    if word == "pub" { return "PUB" }
    if word == "extern" { return "EXTERN" }
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
                if ch == "|" { kind = "PIPE"
                } elif ch == "(" {
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

# Module expansion shares one token stream with the standalone semantic checker.
let mut module_paths: list[str] = []
let mut module_states: list[int] = []
let mut module_public_names: list[list[str]] = []
let mut module_all_names: list[list[str]] = []
let mut module_import_owners: list[int] = []
let mut module_import_aliases: list[str] = []
let mut module_import_targets: list[int] = []
let mut module_import_public: list[bool] = []
let mut module_output: list[Token] = []

fn module_normalize(path: str) -> str {
    let mut parts: list[str] = []
    let mut part = ""
    for i in 0..len(path) + 1 {
        let mut ch = "/"
        if i < len(path) { ch = path[i] }
        if ch == "/" {
            if part == ".." and len(parts) > 0 { parts.pop() }
            elif part != "" and part != "." { parts.append(part) }
            part = ""
        } else { part = part + ch }
    }
    let mut result = ""
    if len(path) > 0 and path[0] == "/" { result = "/" }
    for i in 0..len(parts) {
        if i > 0 { result = result + "/" }
        result = result + parts[i]
    }
    return result
}
fn module_directory(path: str) -> str {
    let mut boundary = -1
    for i in 0..len(path) { if path[i] == "/" { boundary = i } }
    if boundary < 0 { return "" }
    return slice(path, 0, boundary + 1)
}
fn module_name(index: int, name: str) -> str { return "__w1_m" + str(index) + "__" + name }
fn module_contains(names: list[str], name: str) -> bool {
    for candidate in names { if candidate == name { return true } }
    return false
}
fn module_expand(src: str, path: str, entry: bool) -> int {
    let canonical = module_normalize(path)
    for i in 0..len(module_paths) {
        if module_paths[i] == canonical {
            if module_states[i] == 1 { report_error("W1003", 1, 1, "circular import: " + canonical) }
            return i
        }
    }
    let index = len(module_paths)
    module_paths.append(canonical)
    module_states.append(1)
    let mut names: list[str] = []
    let mut exports: list[str] = []
    let tokens = tokenize(src)
    for token in tokens {
        if token.kind == "IDENT" {
            if (len(token.val) >= 6 and slice(token.val, 0, 6) == "__w1_m") or (len(token.val) >= 5 and slice(token.val, 0, 5) == "__wm_") or (len(token.val) >= 3 and slice(token.val, 0, 3) == "_W_") { report_error("W1002", token.line, token.col, "reserved compiler namespace") }
        }
    }
    let mut depth = 0
    let mut exported = false
    for i in 0..len(tokens) - 1 {
        let kind = tokens[i].kind
        if depth == 0 {
            if kind == "PUB" { exported = true }
            elif kind == "FN" or kind == "STRUCT" or kind == "ENUM" or kind == "CLASS" or kind == "INTERFACE" or kind == "LET" {
                let mut offset = 1
                if kind == "LET" and tokens[i + 1].kind == "MUT" { offset = 2 }
                let name = tokens[i + offset].val
                names.append(name)
                if exported { exports.append(name) }
                exported = false
            }
        }
        if kind == "LBRACE" { depth = depth + 1 }
        if kind == "RBRACE" { depth = depth - 1 }
    }
    module_all_names.append(names)
    module_public_names.append(exports)
    let mut aliases: list[str] = []
    let mut dependencies: list[int] = []
    let mut body: list[Token] = []
    let mut position = 0
    while position < len(tokens) - 1 {
        let token = tokens[position]
        if token.kind == "IMPORT" {
            let public_import = position > 0 and tokens[position - 1].kind == "PUB"
            if public_import and len(body) > 0 and body[len(body) - 1].kind == "PUB" { body.pop() }
            let requested = tokens[position + 1].val
            let mut resolved = module_normalize(module_directory(canonical) + requested)
            if len(requested) >= 4 and slice(requested, 0, 4) == "std/" { resolved = "stdlib/" + slice(requested, 4, len(requested)) + ".w" }
            let mut content = read_file(resolved) else err { "" }
            if content == "" {
                resolved = module_normalize(requested)
                content = read_file(resolved) else err { report_error("W1003", token.line, token.col, "module not found: " + requested) "" }
            }
            let dependency = module_expand(content, resolved, false)
            let mut alias = extract_module_ns(requested)
            position = position + 2
            if tokens[position].kind == "AS" { alias = tokens[position + 1].val position = position + 2 }
            if module_contains(aliases, alias) or module_contains(names, alias) { report_error("W1002", token.line, token.col, "duplicate module alias") }
            aliases.append(alias)
            dependencies.append(dependency)
            module_import_owners.append(index)
            module_import_aliases.append(alias)
            module_import_targets.append(dependency)
            module_import_public.append(public_import)
            if public_import { module_public_names[index].append(alias) }
        } else {
            body.append(token)
            position = position + 1
        }
    }
    position = 0
    let mut braces = 0
    let mut parentheses = 0
    while position < len(body) {
        let token = body[position]
        let mut consumed = false
        if token.kind == "IDENT" {
            for i in 0..len(aliases) {
                if token.val == aliases[i] and position + 2 < len(body) and body[position + 1].kind == "DOT" {
                    let member = body[position + 2]
                    let dependency = dependencies[i]
                    let mut nested_target = -1
                    for import_index in 0..len(module_import_owners) {
                        if module_import_owners[import_index] == dependency and module_import_aliases[import_index] == member.val and module_import_public[import_index] { nested_target = module_import_targets[import_index] }
                    }
                    if nested_target >= 0 and position + 4 < len(body) and body[position + 3].kind == "DOT" {
                        let nested_member = body[position + 4]
                        if not module_contains(module_public_names[nested_target], nested_member.val) { report_error("W1001", nested_member.line, nested_member.col, "member is not exported: " + nested_member.val) }
                        module_output.append(Token { kind: "IDENT", val: module_name(nested_target, nested_member.val), line: token.line, col: token.col })
                        position = position + 5
                    } else {
                        if not module_contains(module_public_names[dependency], member.val) { report_error("W1001", member.line, member.col, "member is not exported: " + member.val) }
                        module_output.append(Token { kind: "IDENT", val: module_name(dependency, member.val), line: token.line, col: token.col })
                        position = position + 3
                    }
                    consumed = true
                }
            }
            if not consumed and not entry and module_contains(names, token.val) {
                let mut field = false
                if position > 0 and body[position - 1].kind == "DOT" { field = true }
                if position + 1 < len(body) and body[position + 1].kind == "COLON" and parentheses == 0 {
                    field = true
                    if position > 0 and (body[position - 1].kind == "LET" or body[position - 1].kind == "MUT") { field = false }
                }
                if braces > 0 and position > 0 and body[position - 1].kind == "FN" { field = true }
                if not field { module_output.append(Token { kind: token.kind, val: module_name(index, token.val), line: token.line, col: token.col }) consumed = true position = position + 1 }
            }
        }
        if not consumed { module_output.append(token) position = position + 1 }
        if token.kind == "LBRACE" { braces = braces + 1 }
        if token.kind == "RBRACE" { braces = braces - 1 }
        if token.kind == "LPAREN" { parentheses = parentheses + 1 }
        if token.kind == "RPAREN" { parentheses = parentheses - 1 }
    }
    module_states[index] = 2
    return index
}
fn module_tokens(src: str, path: str) -> list[Token] {
    let empty_names: list[str] = []
    let empty_states: list[int] = []
    let empty_groups: list[list[str]] = []
    let empty_tokens: list[Token] = []
    module_paths = empty_names
    module_states = empty_states
    module_public_names = empty_groups
    module_all_names = empty_groups
    let empty_ids: list[int] = []
    let empty_public: list[bool] = []
    module_import_owners = empty_ids
    module_import_aliases = empty_names
    module_import_targets = empty_ids
    module_import_public = empty_public
    module_output = empty_tokens
    module_expand(src, path, true)
    module_output.append(Token { kind: "EOF", val: "", line: 1, col: 1 })
    return module_output
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

fn is_bound_variable(value: str) -> bool {
    for name in g_borrowed_vars { if name == value { return true } }
    for name in g_globals { if name == value { return true } }
    for scope in g_scope_stack { for name in scope.vars { if name == value { return true } } }
    return false
}
fn emit_indirect_call(callee: str, args: list[str]) -> ExprRes {
    let mut joined = ""
    for i in 0..len(args) {
        if i > 0 { joined = joined + ", " }
        joined = joined + args[i]
    }
    if len(args) == 0 { return bind_call("w_call(" + callee + ", 0, NULL)") }
    let array = new_aux("_call_args")
    emit_line("WVal " + array + "[" + str(len(args)) + "] = { " + joined + " };")
    return bind_call("w_call(" + callee + ", " + str(len(args)) + ", " + array + ")")
}

fn emit_function_value(name: str) -> ExprRes {
    let index = sem_function(name)
    let arity = len(sem_functions[index].params)
    let adapter = "w_adapter_" + name
    let prototype = "static WVal " + adapter + "(WVal, int32_t, const WVal*);"
    let mut exists = false
    for declaration in g_protos { if declaration == prototype { exists = true } }
    if not exists {
        g_protos.append(prototype)
        let mut arguments = ""
        for i in 0..arity {
            if i > 0 { arguments = arguments + ", " }
            arguments = arguments + "argv[" + str(i) + "]"
        }
        g_fn_defs.append("static WVal " + adapter + "(WVal environment, int32_t argc, const WVal* argv) { (void)environment; if (argc != " + str(arity) + ") (fprintf(stderr, \"[W4003] RuntimeError: Call arity mismatch\\n\"), exit(1)); return " + c_fn_name(name) + "(" + arguments + "); }")
    }
    return bind_call("w_function_new(" + adapter + ", w_unit())")
}

fn emit_struct_constructor(name: str, values: list[str]) -> ExprRes {
    let mut keys: list[str] = []
    let mut field_count = 0
    for field in sem_fields {
        if field.owner == name {
            keys.append("\"" + field.name + "\"")
            field_count = field_count + 1
        }
    }
    if field_count != len(values) { report_error("W2005", at_tok().line, at_tok().col, "struct constructor arity: " + name) }
    if field_count == 0 { return bind_call("w_make_struct(\"" + name + "\", 0, NULL, NULL)") }
    let keys_var = new_aux("_keys")
    let values_var = new_aux("_values")
    let mut joined_keys = ""
    let mut joined_values = ""
    for i in 0..field_count {
        if i > 0 { joined_keys = joined_keys + ", " joined_values = joined_values + ", " }
        joined_keys = joined_keys + keys[i]
        joined_values = joined_values + values[i]
    }
    let count = str(field_count)
    emit_line("const char* " + keys_var + "[" + count + "] = { " + joined_keys + " };")
    emit_line("WVal " + values_var + "[" + count + "] = { " + joined_values + " };")
    return bind_call("w_make_struct(\"" + name + "\", " + count + ", " + keys_var + ", " + values_var + ")")
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
            out = out + "\\000"
        } elif code == 63 {
            out = out + "\\077"
        } else {
            out = out + ch
        }
    }
    out = out + "\""
    return out
}

fn parse_type_ann() -> bool {
    let mut is_fallible = false
    if match_kind("FN") {
        expect_kind("LPAREN")
        if not check_kind("RPAREN") {
            parse_type_ann()
            while match_kind("COMMA") { parse_type_ann() }
        }
        expect_kind("RPAREN")
        expect_kind("ARROW")
        return parse_type_ann()
    }
    if match_kind("LPAREN") {
        is_fallible = parse_type_ann()
        expect_kind("RPAREN")
    } else {
        let type_token = at_tok()
        advance_tok()
        if type_token.kind == "IDENT" and type_token.val == "Result" { is_fallible = true }
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
        while match_kind("PIPE") { parse_type_ann() }
        is_fallible = true
        g_cur_err_type = err_tok.val
    }
    return is_fallible
}

fn parse_field_default() -> str {
    let tname = at_tok().val
    let mut def_c = "w_none()"
    if tname == "Weak" {
        def_c = "w_empty_weak()"
    } elif tname == "int" {
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
fn snapshot_callee(callee: ExprRes, collection: bool) -> ExprRes {
    if is_bound_variable(callee.val) { return ExprRes { val: snapshot_value(callee.val), lref: "" } }
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
    if (collection and (method == "append" or method == "pop" or method == "clear")) or receiver == "v_super" { return callee }
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


fn emit_call(callee: ExprRes, args_c: list[str], collection: bool, line: int, col: int) -> ExprRes {
    if len(callee.val) >= 6 and slice(callee.val, 0, 6) == "enum::" {
        let marker = slice(callee.val, 6, len(callee.val))
        let mut separator = -1
        for i in 0..len(marker) - 1 { if slice(marker, i, i + 2) == "::" { separator = i } }
        if separator < 0 { report_error("W9999", at_tok().line, at_tok().col, "invalid enum constructor marker") }
        let owner = slice(marker, 0, separator)
        let variant = slice(marker, separator + 2, len(marker))
        if owner == "Option" and variant == "Some" {
            if len(args_c) != 1 { report_error("W2005", at_tok().line, at_tok().col, "Option.Some arity") }
            return bind_call("w_enum_payload(\"Option\", \"Some\", " + own_expr(args_c[0]) + ")")
        }
        if owner == "Result" and variant == "Ok" {
            if len(args_c) != 1 { report_error("W2005", at_tok().line, at_tok().col, "Result.Ok arity") }
            return bind_call("w_ok(" + own_expr(args_c[0]) + ")")
        }
        if owner == "Result" and variant == "Err" {
            if len(args_c) != 1 { report_error("W2005", at_tok().line, at_tok().col, "Result.Err arity") }
            return bind_call("w_err(" + own_expr(args_c[0]) + ")")
        }
        let mut arity = -1
        for i in 0..len(g_enum_variant_names) {
            if g_enum_variant_names[i] == variant and g_enum_variant_owners[i] == owner { arity = g_enum_variant_arities[i] }
        }
        if arity != len(args_c) { report_error("W2005", at_tok().line, at_tok().col, "enum constructor arity: " + owner + "." + variant) }
        if arity == 0 { return bind_call("w_enum(\"" + owner + "\", \"" + variant + "\")") }
        if arity == 1 { return bind_call("w_enum_payload(\"" + owner + "\", \"" + variant + "\", " + own_expr(args_c[0]) + ")") }
        let payload_values = new_aux("_enum_values")
        let mut values = ""
        for i in 0..len(args_c) {
            if i > 0 { values = values + ", " }
            values = values + args_c[i]
        }
        emit_line("WVal " + payload_values + "[" + str(len(args_c)) + "] = { " + values + " };")
        let payload = "w_make_tuple(" + str(len(args_c)) + ", " + payload_values + ")"
        return bind_call("w_enum_payload(\"" + owner + "\", \"" + variant + "\", " + payload + ")")
    }
    if is_bound_variable(callee.val) or (callee.lref == "" and not (len(callee.val) >= 2 and slice(callee.val, 0, 2) == "v_")) {
        return emit_indirect_call(callee.val, args_c)
    }
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
        if collection and method == "append" {
            return bind_call("w_list_append(" + recv_lref + ", " + args_c[0] + ")")
        }
        if collection and method == "pop" {
            return bind_call("w_list_pop_at(" + recv_lref + ", " + escape_c_str(g_in_path) + ", " + str(line) + ", " + str(col) + ")")
        }
        if collection and method == "clear" {
            return bind_call("w_list_clear(" + recv_lref + ")")
        }
        if collection and method == "get" {
            return bind_call("w_dict_get(" + recv_val + ", " + args_c[0] + ")")
        }
        if collection and method == "keys" {
            return bind_call("w_dict_keys(" + recv_val + ")")
        }
        if collection and method == "values" {
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
        if fn_name == "weak" or fn_name == "upgrade" {
            if len(args_c) != 1 { report_error("W2005", at_tok().line, at_tok().col, "weak/upgrade expects one argument") }
            if fn_name == "weak" {
                return bind_call("w_builtin_weak_owned(" + own_expr(args_c[0]) + ")")
            }
            return bind_call("w_builtin_" + fn_name + "(" + args_c[0] + ")")
        }
        if fn_name == "Ok" and len(args_c) == 1 {
            return bind_call("w_ok(" + own_expr(args_c[0]) + ")")
        }
        if fn_name == "Err" and len(args_c) == 1 {
            return bind_call("w_err(" + own_expr(args_c[0]) + ")")
        }
        if fn_name == "Some" and len(args_c) == 1 {
            return bind_call("w_enum_payload(\"Option\", \"Some\", " + own_expr(args_c[0]) + ")")
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
        if fn_name == "join_strings" { return bind_call("w_builtin_join_strings(" + args_c[0] + ", " + args_c[1] + ")") }
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
        let generic_type = sem_generic_type(fn_name)
        if generic_type >= 0 and sem_generic_types[generic_type].kind == "struct" { return emit_struct_constructor(fn_name, args_c) }
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

fn parse_pattern_condition(subject: str) -> str {
    let pattern_position = g_pos + 1
    let mut error_pattern_kind = ""
    let mut error_pattern_name = ""
    for i in 0..len(sem_error_pattern_positions) {
        if sem_error_pattern_positions[i] == pattern_position {
            error_pattern_kind = sem_error_pattern_kinds[i]
            error_pattern_name = sem_error_pattern_names[i]
        }
    }
    if error_pattern_kind != "" {
        expect_kind("IDENT")
        expect_kind("LPAREN")
        let mut condition = "w_value_is_error_type(" + subject + ", " + escape_c_str(error_pattern_kind) + ", " + escape_c_str(error_pattern_name) + ")"
        if not check_kind("RPAREN") {
            let child = parse_pattern_condition(subject)
            condition = "(" + condition + ") && (" + child + ")"
        }
        expect_kind("RPAREN")
        return condition
    }
    if match_kind("ELSE") { return "true" }
    if match_kind("NONE") { return "w_is_none(" + subject + ")" }
    if check_kind("INT") or check_kind("FLOAT") or check_kind("STR") or check_kind("TRUE") or check_kind("FALSE") {
        let literal = parse_prefix_expr(false)
        return "w_eq(" + subject + ", " + literal.val + ")"
    }
    let name = expect_kind("IDENT").val
    if name == "_" { return "true" }
    let mut owner = ""
    let mut variant = name
    if match_kind("DOT") {
        owner = name
        variant = expect_kind("IDENT").val
    }
    let mut enum_owner = owner
    let mut arity = -1
    if owner == "Option" and variant == "None" { return "w_is_none(" + subject + ")" }
    if (owner == "Option" or owner == "") and variant == "Some" { arity = 1 enum_owner = "Option" }
    if (owner == "Result" or owner == "") and (variant == "Ok" or variant == "Err") { arity = 1 enum_owner = "Result" }
    if arity < 0 {
        for i in 0..len(g_enum_variant_names) {
            if g_enum_variant_names[i] == variant and (owner == "" or g_enum_variant_owners[i] == owner) {
                arity = g_enum_variant_arities[i]
                enum_owner = g_enum_variant_owners[i]
            }
        }
    }
    if arity >= 0 {
        let mut condition = "true"
        if enum_owner == "Option" and variant == "Some" { condition = "!w_is_none(" + subject + ")" }
        elif enum_owner == "Result" and variant == "Ok" { condition = "(" + subject + ").tag == W_OK" }
        elif enum_owner == "Result" and variant == "Err" { condition = "(" + subject + ").tag == W_ERR" }
        else { condition = "w_is_enum_variant(" + subject + ", \"" + enum_owner + "\", \"" + variant + "\")" }
        if match_kind("LPAREN") {
            let mut index = 0
            if not check_kind("RPAREN") {
                let mut payload = "w_peek_enum_payload(" + subject + ")"
                if enum_owner == "Option" { payload = "w_peek_optional(" + subject + ")" }
                elif enum_owner == "Result" and variant == "Ok" { payload = "w_peek_ok(" + subject + ")" }
                elif enum_owner == "Result" and variant == "Err" { payload = "w_peek_err(" + subject + ")" }
                if arity > 1 { payload = "(" + payload + ").as.tuple->items[0]" }
                let child = parse_pattern_condition(payload)
                condition = "(" + condition + ") && (" + child + ")"
                index = 1
                while match_kind("COMMA") {
                    if check_kind("RPAREN") { break }
                    if index >= arity { report_error("W2001", at_tok().line, at_tok().col, "too many enum pattern elements") }
                    let mut next_payload = "w_peek_enum_payload(" + subject + ")"
                    if enum_owner == "Option" { next_payload = "w_peek_optional(" + subject + ")" }
                    elif enum_owner == "Result" and variant == "Ok" { next_payload = "w_peek_ok(" + subject + ")" }
                    elif enum_owner == "Result" and variant == "Err" { next_payload = "w_peek_err(" + subject + ")" }
                    next_payload = "(" + next_payload + ").as.tuple->items[" + str(index) + "]"
                    let next_condition = parse_pattern_condition(next_payload)
                    condition = "(" + condition + ") && (" + next_condition + ")"
                    index = index + 1
                }
            }
            expect_kind("RPAREN")
            if index != arity { report_error("W2001", at_tok().line, at_tok().col, "enum pattern arity") }
        } elif arity != 0 {
            report_error("W2005", at_tok().line, at_tok().col, "enum pattern requires payload")
        }
        return condition
    }
    if owner != "" { return "w_is_enum_variant(" + subject + ", \"" + owner + "\", \"" + variant + "\")" }
    g_pattern_bind_lines.append("WVal v_" + name + " = w_clone(" + subject + ");")
    g_pattern_bind_names.append("v_" + name)
    return "true"
}

fn parse_match_arms(subj_tmp: str, res: str) -> unit {
    let matched = new_aux("_match_taken")
    emit_line("bool " + matched + " = false;")
    while not check_kind("RBRACE") and not is_eof() {
        let empty_bindings: list[str] = []
        g_pattern_bind_lines = empty_bindings
        g_pattern_bind_names = empty_bindings
        let condition = parse_pattern_condition(subj_tmp)
        emit_line("if (!" + matched + " && (" + condition + ")) {")
        push_scope("block")
        for binding in g_pattern_bind_lines { emit_line(binding) }
        for binding_name in g_pattern_bind_names { register_var(binding_name) }
        let has_guard = match_kind("IF")
        if has_guard {
            let guard = parse_expr(0, false)
            emit_line("if ((" + guard.val + ").as.b) {")
            push_scope("block")
        }
        expect_kind("FAT_ARROW")
        if check_kind("LBRACE") {
            let arm_value = parse_block_expr()
            emit_line("w_assign(&" + res + ", " + own_expr(arm_value) + ");")
        } else {
            let arm_value = parse_expr(0, true)
            emit_line("w_assign(&" + res + ", " + own_expr(arm_value.val) + ");")
        }
        emit_line(matched + " = true;")
        if has_guard { pop_scope() emit_line("}") }
        pop_scope()
        emit_line("}")
        match_kind("COMMA")
    }
}

fn parse_prefix_expr(allow_struct: bool) -> ExprRes {
    let tok = at_tok()
    if check_kind("PIPE") { return parse_lambda() }
    if match_kind("INT") {
        return ExprRes { val: "w_int(" + tok.val + "LL)", lref: "" }
    }
    if match_kind("FLOAT") {
        return ExprRes { val: "w_float(" + tok.val + ")", lref: "" }
    }
    if match_kind("STR") {
        return ExprRes { val: "w_str_n(" + escape_c_str(tok.val) + ", " + str(len(bytes(tok.val))) + ")", lref: "" }
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
        if name == "None" and not is_bound_variable("v_" + name) { return ExprRes { val: "w_none()", lref: "" } }
        let function_index = sem_function(name)
        if function_index >= 0 and not is_bound_variable("v_" + name) and len(sem_functions[function_index].type_params) > 0 and match_kind("LBRACKET") {
            while not check_kind("RBRACKET") and not is_eof() {
                parse_type_ann()
                if not match_kind("COMMA") { break }
            }
            expect_kind("RBRACKET")
        }
        let generic_type = sem_generic_type(name)
        if generic_type >= 0 and not is_bound_variable("v_" + name) and match_kind("LBRACKET") {
            while not check_kind("RBRACKET") and not is_eof() {
                parse_type_ann()
                if not match_kind("COMMA") { break }
            }
            expect_kind("RBRACKET")
        }
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
                let mut ordered_names: list[str] = []
                let mut ordered_values: list[str] = []
                for field in sem_fields {
                    if field.owner == name {
                        let key = "\"" + field.name + "\""
                        for index in 0..len(f_names) {
                            if f_names[index] == key {
                                ordered_names.append(key)
                                ordered_values.append(f_vals[index])
                            }
                        }
                    }
                }
                f_names = ordered_names
                f_vals = ordered_values
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
        if not check_kind("LPAREN") and not is_bound_variable("v_" + name) and sem_function(name) >= 0 {
            return emit_function_value(name)
        }
        if not is_bound_variable("v_" + name) {
            let mut variant_owner = ""
            let mut variant_arity = -1
            for variant_index in 0..len(g_enum_variant_names) {
                if g_enum_variant_names[variant_index] == name {
                    variant_owner = g_enum_variant_owners[variant_index]
                    variant_arity = g_enum_variant_arities[variant_index]
                }
            }
            if variant_arity == 0 { return ExprRes { val: "w_enum(\"" + variant_owner + "\", \"" + name + "\")", lref: "" } }
            if variant_arity > 0 { return ExprRes { val: "enum::" + variant_owner + "::" + name, lref: "" } }
        }
        return ExprRes { val: "v_" + name, lref: "&v_" + name }
    }
    if match_kind("MINUS") {
        # SPEC 5 puts unary at level 3, tighter than multiplicative (level 4), so the
        # operand stops below `* / %`. A literal operand folds into a negative constant
        # so negated whole-number literals emit identically to W0's C99 backend, which
        # is what keeps the three-stage bootstrap hash a fixed point.
        if check_kind("INT") {
            let mut lit = advance_tok().val
            let digits = slice(lit, 0, len(lit))
            return ExprRes { val: "w_int(-" + digits + "LL)", lref: "" }
        }
        let op_r = parse_expr(9, allow_struct)
        return ExprRes { val: "w_neg(" + op_r.val + ")", lref: "" }
    }
    if match_kind("NOT") {
        let op_r = parse_expr(9, allow_struct)
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
                let call_tok = at_tok()
                let mut collection = false
                for position in sem_collection_call_positions { if position == g_pos + 1 { collection = true } }
                for position in sem_indirect_positions {
                    if position == g_pos + 1 { left = ExprRes { val: snapshot_value(left.val), lref: "" } }
                }
                left = snapshot_callee(left, collection)
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
                left = emit_call(left, args_c, collection, call_tok.line, call_tok.col)
            } elif check_kind("DOT") {
                let projection_position = g_pos + 1
                advance_tok()
                let prop_tok = expect_kind("IDENT")
                let prop = prop_tok.val
                if projection_is_mutated() {
                    for position in sem_class_projection_positions {
                        if position == projection_position {
                            let held = snapshot_value(left.val)
                            left = ExprRes { val: held, lref: "&" + held }
                        }
                    }
                }
                if len(left.val) >= 2 and slice(left.val, 0, 2) == "v_" {
                    let raw_obj = slice(left.val, 2, len(left.val))
                    if (is_enum_name(raw_obj) or raw_obj == "Option" or raw_obj == "Result") and not is_bound_variable(left.val) {
                        if raw_obj == "Option" and prop == "None" { left = ExprRes { val: "w_none()", lref: "" } }
                        elif (raw_obj == "Option" and prop == "Some") or (raw_obj == "Result" and (prop == "Ok" or prop == "Err")) { left = ExprRes { val: "enum::" + raw_obj + "::" + prop, lref: "" } }
                        else {
                            let mut variant_arity = 0
                            for variant_index in 0..len(g_enum_variant_names) {
                                if g_enum_variant_names[variant_index] == prop and g_enum_variant_owners[variant_index] == raw_obj { variant_arity = g_enum_variant_arities[variant_index] }
                            }
                            if variant_arity > 0 { left = ExprRes { val: "enum::" + raw_obj + "::" + prop, lref: "" } }
                            else { left = ExprRes { val: "w_enum(\"" + raw_obj + "\", \"" + prop + "\")", lref: "" } }
                        }
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
                let bracket_tok = at_tok()
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
                let source_args = escape_c_str(g_in_path) + ", " + str(bracket_tok.line) + ", " + str(bracket_tok.col)
                let index_lref = "w_index_ref_at(" + clean_lref(left.lref) + ", " + idx_r.val + ", " + source_args + ")"
                if mutated {
                    left = ExprRes { val: "w_index_get_at(" + left.val + ", " + idx_r.val + ", " + source_args + ")", lref: index_lref }
                } else {
                    left = ExprRes { val: bind_call("w_index_get_owned_at(" + object_value + ", " + idx_r.val + ", " + source_args + ")").val, lref: index_lref }
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
                if len(left.val) >= 2 and slice(left.val, 0, 2) == "v_" {
                    emit_line("w_assign(&" + left.val + ", " + "w_move(&" + rhs_hold + "));")
                    left = ExprRes { val: left.val, lref: left.lref }
                } else {
                    let target_ref = clean_lref(left.lref)
                    left = bind_call("w_clone(w_assign(" + target_ref + ", w_move(&" + rhs_hold + ")))")
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
                left = ExprRes { val: "w_div_at(" + left.val + ", " + right.val + ", " + escape_c_str(g_in_path) + ", " + str(op_tok.line) + ", " + str(op_tok.col) + ")", lref: "" }
            } elif op_tok.kind == "PERCENT" {
                left = ExprRes { val: "w_mod_at(" + left.val + ", " + right.val + ", " + escape_c_str(g_in_path) + ", " + str(op_tok.line) + ", " + str(op_tok.col) + ")", lref: "" }
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
    let mut needs_result_lift = false
    for position in sem_result_lift_positions { if position == expression_start + 1 { needs_result_lift = true } }
    if needs_result_lift { left = bind_call("w_ok(" + own_expr(left.val) + ")") }
    return left
}

fn parse_lambda() -> ExprRes {
    let token = expect_kind("PIPE")
    let mut index = -1
    for i in 0..len(sem_lambdas) { if sem_lambdas[i].position == g_pos { index = i } }
    if index < 0 { report_error("W9999", token.line, token.col, "missing checked closure") }
    let lambda = sem_lambdas[index]
    while not check_kind("PIPE") {
        expect_kind("IDENT")
        if match_kind("COLON") { parse_type_ann() }
        if not match_kind("COMMA") { break }
    }
    expect_kind("PIPE")
    if match_kind("ARROW") { parse_type_ann() }
    let saved_statements = g_cur_stmts
    let saved_scopes = g_scope_stack
    let saved_borrowed = g_borrowed_vars
    let saved_fallible = g_fn_fallible
    let saved_error = g_cur_err_type
    let empty_statements: list[str] = []
    let empty_scopes: list[CleanupScope] = []
    let mut borrowed: list[str] = []
    g_cur_stmts = empty_statements
    g_scope_stack = empty_scopes
    g_fn_fallible = false
    g_cur_err_type = ""
    push_scope("fn")
    for i in 0..len(lambda.params) {
        let variable = "v_" + lambda.params[i]
        emit_line("WVal " + variable + " = argv[" + str(i) + "];")
        borrowed.append(variable)
    }
    for i in 0..len(lambda.captures) {
        let variable = "v_" + lambda.captures[i]
        declare_owned_var(variable, "w_clone(environment.as.tuple->items[" + str(i) + "])")
    }
    g_borrowed_vars = borrowed
    let mut result = "w_unit()"
    if match_kind("FAT_ARROW") { result = parse_expr(0, true).val }
    else { result = parse_block_expr() }
    let returned = new_aux("_ret")
    emit_line("WVal " + returned + " = " + own_expr(result) + ";")
    pop_scope()
    emit_line("return " + returned + ";")
    let name = "w_lambda_" + str(index)
    let signature = "static WVal " + name + "(WVal environment, int32_t argc, const WVal* argv)"
    let mut definition = signature + " {\n"
    definition = definition + "    if (argc != " + str(len(lambda.params)) + ") { fprintf(stderr, \"[W4003] RuntimeError: Call arity mismatch\\n\"); exit(1); }\n"
    for line in g_cur_stmts { definition = definition + "    " + line + "\n" }
    definition = definition + "}"
    g_protos.append(signature + ";")
    g_fn_defs.append(definition)
    g_cur_stmts = saved_statements
    g_scope_stack = saved_scopes
    g_borrowed_vars = saved_borrowed
    g_fn_fallible = saved_fallible
    g_cur_err_type = saved_error
    let mut captures = ""
    for i in 0..len(lambda.captures) {
        if i > 0 { captures = captures + ", " }
        captures = captures + "v_" + lambda.captures[i]
    }
    let mut environment = "w_make_tuple(0, NULL)"
    if len(lambda.captures) > 0 {
        let array = new_aux("_captures")
        emit_line("WVal " + array + "[" + str(len(lambda.captures)) + "] = { " + captures + " };")
        environment = "w_make_tuple(" + str(len(lambda.captures)) + ", " + array + ")"
    }
    return bind_call("w_function_new(" + name + ", " + environment + ")")
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
        let initial = snapshot_value(val_r.val)
        declare_owned_var(vname, own_expr(initial))
    }
}

fn parse_return_stmt() -> unit {
    let return_token = expect_kind("RETURN")
    if check_kind("RBRACE") or is_eof() or at_tok().line > return_token.line {
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
    if match_kind("LBRACKET") {
        while not check_kind("RBRACKET") and not is_eof() {
            expect_kind("IDENT")
            if match_kind("COLON") { parse_type_ann() }
            if not match_kind("COMMA") { break }
        }
        expect_kind("RBRACKET")
    }
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
    if match_kind("LBRACKET") {
        while not check_kind("RBRACKET") and not is_eof() {
            expect_kind("IDENT")
            if match_kind("COLON") { expect_kind("IDENT") }
            if not match_kind("COMMA") { break }
        }
        expect_kind("RBRACKET")
    }
    expect_kind("LBRACE")
    while not check_kind("RBRACE") and not is_eof() {
        let variant = expect_kind("IDENT")
        let mut arity = 0
        if match_kind("LPAREN") {
            if not check_kind("RPAREN") {
                parse_type_ann()
                arity = 1
                while match_kind("COMMA") {
                    if check_kind("RPAREN") { break }
                    parse_type_ann()
                    arity = arity + 1
                }
            }
            expect_kind("RPAREN")
        }
        g_enum_variant_names.append(variant.val)
        g_enum_variant_owners.append(name_tok.val)
        g_enum_variant_arities.append(arity)
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
        let mut is_pub = true
        if check_kind("PUBLIC") {
            advance_tok()
            is_pub = true
        } elif check_kind("PRIVATE") {
            advance_tok()
            is_pub = false
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
    g_protos.append("static const WClassVTable w_vtable_" + cls_name + ";")
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
    new_str = new_str + "    v_self.as.st->vtable = &w_vtable_" + cls_name + ";\n"
    if init_owner != "" {
        new_str = new_str + "    w_release(w_method_" + init_owner + "__init(" + init_call_args + "));\n"
    }
    new_str = new_str + "    return v_self;\n}"
    g_fn_defs.append(new_str)
}

fn emit_oop_dispatchers() -> unit {
    let mut adapters: list[str] = []
    let mut tables: list[str] = []
    for class_ in g_classes {
        let mut slots: list[str] = []
        for di in 0..len(g_dispatch_names) {
            let name = g_dispatch_names[di]
            let arity = g_dispatch_arities[di]
            let owner = find_class_method_owner(class_.name, name)
            if owner == "" or find_class_method_arity(class_.name, name) != arity { slots.append("NULL") }
            else {
                let adapter = "w_vinvoke_" + owner + "__" + name
                slots.append(adapter)
                if not module_contains(adapters, adapter) {
                    adapters.append(adapter)
                    let mut arguments = "receiver"
                    for i in 0..arity { arguments = arguments + ", argv[" + str(i) + "]" }
                    g_fn_defs.append("static WVal " + adapter + "(WVal receiver, int32_t argc, const WVal* argv) { (void)argc; (void)argv; return w_method_" + owner + "__" + name + "(" + arguments + "); }")
                }
            }
        }
        if len(slots) > 0 {
            let mut joined = ""
            for i in 0..len(slots) { if i > 0 { joined = joined + ", " } joined = joined + slots[i] }
            tables.append("static const WInvoke w_slots_" + class_.name + "[" + str(len(slots)) + "] = { " + joined + " };")
            tables.append("static const WClassVTable w_vtable_" + class_.name + " = { " + str(len(slots)) + ", w_slots_" + class_.name + " };")
        } else { tables.append("static const WClassVTable w_vtable_" + class_.name + " = { 0, NULL };") }
    }
    for table in tables { g_fn_defs.append(table) }
    for di in 0..len(g_dispatch_names) {
        let name = g_dispatch_names[di]
        let arity = g_dispatch_arities[di]
        let mut signature = "WVal v_self"
        let mut arguments = ""
        for i in 0..arity {
            signature = signature + ", WVal _a" + str(i)
            if i > 0 { arguments = arguments + ", " }
            arguments = arguments + "_a" + str(i)
        }
        if arity == 0 { arguments = "NULL" } else { arguments = "(WVal[]){ " + arguments + " }" }
        g_fn_defs.append("static WVal w_dispatch__" + name + "__" + str(arity) + "(" + signature + ") { return w_virtual_call(v_self, " + str(di) + ", " + str(arity) + ", " + arguments + "); }")
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
        if match_kind("PUB") { continue }
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
    if match_kind("LBRACKET") {
        while not check_kind("RBRACKET") and not is_eof() {
            expect_kind("IDENT")
            if match_kind("COLON") { parse_type_ann() }
            if not match_kind("COMMA") { break }
        }
        expect_kind("RBRACKET")
    }
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
    let previous_bindings = g_borrowed_vars
    let mut borrowed: list[str] = []
    for parameter in param_names { borrowed.append("v_" + parameter) }
    g_borrowed_vars = borrowed
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
    g_borrowed_vars = previous_bindings
    g_fn_fallible = prev_fallible
    g_cur_err_type = prev_err
    let mut fn_str = "static WVal " + c_name + "(" + sig + ") {\n"
    for l in body_lines {
        fn_str = fn_str + "    " + l + "\n"
    }
    fn_str = fn_str + "}"
    g_fn_defs.append(fn_str)
}

fn ffi_c_type(name: str, returned: bool) -> str {
    if name == "int32" { return "int32_t" }
    if name == "int" or name == "int64" { return "int64_t" }
    if name == "float" or name == "double" { return "double" }
    if name == "bool" { return "bool" }
    if name == "opaque" { return "void*" }
    if name == "unit" and returned { return "void" }
    report_error("W2001", at_tok().line, at_tok().col, "unsupported C ABI type")
    return "void"
}
fn parse_extern_decl() {
    expect_kind("EXTERN")
    if expect_kind("STR").val != "C" { report_error("W2013", at_tok().line, at_tok().col, "only C ABI is supported") }
    expect_kind("FN")
    let name = expect_kind("IDENT").val
    expect_kind("LPAREN")
    let mut types: list[str] = []
    while not check_kind("RPAREN") {
        expect_kind("IDENT")
        expect_kind("COLON")
        types.append(expect_kind("IDENT").val)
        if not match_kind("COMMA") { break }
    }
    expect_kind("RPAREN")
    expect_kind("ARROW")
    let returned = expect_kind("IDENT").val
    let mut native_name = name
    if len(name) > 6 and slice(name, 0, 6) == "__w1_m" {
        for i in 6..len(name) - 1 { if slice(name, i, i + 2) == "__" { native_name = slice(name, i + 2, len(name)) break } }
    }
    let mut native_params = ""
    let mut wrapped_params = ""
    let mut arguments = ""
    for i in 0..len(types) {
        if i > 0 { native_params = native_params + ", " wrapped_params = wrapped_params + ", " arguments = arguments + ", " }
        native_params = native_params + ffi_c_type(types[i], false)
        let variable = "v_" + str(i)
        wrapped_params = wrapped_params + "WVal " + variable
        if types[i] == "int32" { arguments = arguments + "w_ffi_int32(" + variable + ")" }
        elif types[i] == "int" or types[i] == "int64" { arguments = arguments + variable + ".as.i" }
        elif types[i] == "float" or types[i] == "double" { arguments = arguments + variable + ".as.f" }
        elif types[i] == "bool" { arguments = arguments + variable + ".as.b" }
        else { arguments = arguments + variable + ".as.pointer" }
    }
    if len(types) == 0 { native_params = "void" wrapped_params = "void" }
    let c_name = c_fn_name(name)
    g_protos.append("extern " + ffi_c_type(returned, true) + " " + native_name + "(" + native_params + ");")
    g_protos.append("static WVal " + c_name + "(" + wrapped_params + ");")
    let call = native_name + "(" + arguments + ")"
    let mut result = ""
    if returned == "unit" { result = call + "; return w_unit();" }
    elif returned == "int" or returned == "int32" or returned == "int64" { result = "return w_int(" + call + ");" }
    elif returned == "float" or returned == "double" { result = "return w_float(" + call + ");" }
    elif returned == "bool" { result = "return w_bool(" + call + ");" }
    else { result = "return w_pointer(" + call + ");" }
    g_fn_defs.append("static WVal " + c_name + "(" + wrapped_params + ") { " + result + " }")
}
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
    check_match_syntax(tokens)
    sem_validate(tokens)
}

fn check_match_syntax(tokens: list[Token]) {
    for start in 0..len(tokens) {
        if tokens[start].kind == "MATCH" {
            let mut position = start + 1
            while position < len(tokens) and tokens[position].kind != "LBRACE" { position = position + 1 }
            position = position + 1
            let mut expects_arrow = true
            let mut guarded = false
            let mut depth = 0
            let mut parentheses = 0
            while position < len(tokens) {
                let token = tokens[position]
                if token.kind == "LPAREN" or token.kind == "LBRACKET" { parentheses = parentheses + 1 }
                if token.kind == "RPAREN" or token.kind == "RBRACKET" { parentheses = parentheses - 1 }
                if depth == 0 and parentheses == 0 {
                    if token.kind == "RBRACE" { break }
                    if token.kind == "FAT_ARROW" { expects_arrow = false }
                    elif token.kind == "IF" { guarded = true }
                    elif token.kind == "COMMA" { expects_arrow = true guarded = false }
                    elif token.kind == "LBRACE" and expects_arrow and not guarded { report_error("W0001", token.line, token.col, "expected '=>' after match pattern") }
                }
                if token.kind == "LBRACE" { depth = depth + 1 }
                if token.kind == "RBRACE" { depth = depth - 1 }
                position = position + 1
            }
        }
    }
}
fn sem_at() -> Token { return sem_tokens[sem_pos] }
fn sem_is(kind: str) -> bool { return sem_at().kind == kind }
fn sem_take() -> Token {
    let token = sem_at()
    if sem_pos + 1 < len(sem_tokens) { sem_pos = sem_pos + 1 }
    return token
}
fn sem_match(kind: str) -> bool {
    if sem_is(kind) { sem_take() return true }
    return false
}
fn sem_error(code: str, message: str) {
    report_error(code, sem_at().line, sem_at().col, message)
}
fn sem_expect(kind: str) -> Token {
    if not sem_is(kind) { sem_error("W0006", "expected " + kind) }
    return sem_take()
}
fn sem_intern(kind: str, name: str, args: list[int]) -> int {
    for i in 0..len(sem_types) {
        let candidate = sem_types[i]
        if candidate.kind == kind and candidate.name == name and candidate.args == args { return i }
    }
    sem_types.append(SemType { kind: kind, name: name, args: args })
    return len(sem_types) - 1
}
fn sem_simple(kind: str) -> int {
    let empty: list[int] = []
    return sem_intern(kind, "", empty)
}
fn sem_wrap(kind: str, child: int) -> int { return sem_intern(kind, "", [child]) }
fn sem_kind(type_id: int) -> str { return sem_types[type_id].kind }
fn sem_error_type_name(type_id: int) -> str {
    let type_ = sem_types[type_id]
    if type_.kind == "int" { return "int" }
    if type_.kind == "float" { return "float" }
    if type_.kind == "bool" { return "bool" }
    if type_.kind == "str" { return "str" }
    return type_.name
}
fn sem_error_union(first: int) -> int {
    let mut alternatives: list[int] = [first]
    let mut has_union = false
    while sem_match("PIPE") { has_union = true alternatives.append(sem_type()) }
    if not has_union { return first }
    let mut unique: list[int] = []
    for alternative in alternatives {
        let kind = sem_kind(alternative)
        if kind != "int" and kind != "float" and kind != "bool" and kind != "str" and kind != "struct" and kind != "enum" {
            sem_error("W2001", "error union alternatives must be scalar, non-generic struct, or non-generic enum types")
        }
        if len(sem_types[alternative].args) > 0 and (kind == "struct" or kind == "enum") {
            sem_error("W2001", "generic nominal types cannot be error union alternatives")
        }
        let mut found = false
        for existing in unique { if existing == alternative { found = true } }
        if not found { unique.append(alternative) }
    }
    if len(unique) < 2 { sem_error("W2001", "an error union requires at least two distinct alternatives") }
    let mut canonical: list[int] = []
    let mut previous = -1
    while len(canonical) < len(unique) {
        let mut next = -1
        for alternative in unique {
            if alternative > previous and (next < 0 or alternative < next) { next = alternative }
        }
        if next < 0 { sem_error("W9999", "failed to canonicalize error union") }
        canonical.append(next)
        previous = next
    }
    return sem_intern("error_union", "", canonical)
}
fn sem_named(name: str) -> int {
    for i in 0..len(sem_types) { if sem_types[i].name == name { return i } }
    sem_error("W1001", "unknown type: " + name)
    return sem_unit
}
fn sem_generic_type(name: str) -> int {
    for i in 0..len(sem_generic_types) { if sem_generic_types[i].name == name { return i } }
    return -1
}
fn sem_same_type_declaration(declaration: int, instance: int) -> bool {
    let declared = sem_types[declaration]
    let concrete = sem_types[instance]
    return declared.kind == concrete.kind and declared.name == concrete.name
}
fn sem_function(name: str) -> int {
    for i in 0..len(sem_functions) { if sem_functions[i].name == name { return i } }
    return -1
}
fn sem_method(owner: str, name: str) -> int {
    let mut current = owner
    let mut visits = 0
    while current != "" and visits <= len(sem_classes) {
        let index = sem_function(current + "." + name)
        if index >= 0 { return index }
        let mut next = ""
        for class_ in sem_classes { if class_.name == current { next = class_.parent } }
        current = next
        visits = visits + 1
    }
    return -1
}
fn sem_error_channel_assignable(source: int, target: int) -> bool {
    if source == target { return true }
    let s = sem_types[source]
    let t = sem_types[target]
    let source_members = if s.kind == "error_union" { s.args } else { [source] }
    let target_members = if t.kind == "error_union" { t.args } else { [target] }
    for source_member in source_members {
        let mut covered = false
        for target_member in target_members { if source_member == target_member { covered = true } }
        if not covered { return false }
    }
    return true
}
fn sem_assignable(source: int, target: int) -> bool {
    if source == target { return true }
    let s = sem_types[source]
    let t = sem_types[target]
    if s.kind == "empty" and (t.kind == "list" or t.kind == "dict") { return true }
    if t.kind == "optional" {
        if source == sem_none { return true }
        if s.kind == "optional" { return sem_assignable(s.args[0], t.args[0]) }
        return sem_assignable(source, t.args[0])
    }
    if t.kind == "result" {
        if s.kind == "result" {
            if s.args[0] == t.args[0] and sem_error_channel_assignable(s.args[1], t.args[1]) { return true }
            return sem_assignable(source, t.args[0])
        }
        if s.kind == "ok" { return sem_assignable(s.args[0], t.args[0]) }
        if s.kind == "err" { return sem_error_channel_assignable(s.args[0], t.args[1]) }
        return sem_assignable(source, t.args[0])
    }
    if t.kind == "error_union" {
        return sem_error_channel_assignable(source, target)
    }
    if s.kind == "class" and (t.kind == "class" or t.kind == "interface") {
        let mut current = s.name
        let mut visits = 0
        while current != "" and visits <= len(sem_classes) {
            if current == t.name { return true }
            let mut next = ""
            for class_ in sem_classes {
                if class_.name == current {
                    for interface_ in class_.interfaces { if interface_ == t.name { return true } }
                    next = class_.parent
                }
            }
            current = next
            visits = visits + 1
        }
    }
    return false
}
fn sem_require(source: int, target: int, code: str) {
    if not sem_assignable(source, target) { sem_error(code, "incompatible types") }
}
fn sem_mark_result_lift(position: int, source: int, target: int) {
    if target >= 0 and sem_kind(source) == "result" and sem_kind(target) == "result" {
        let source_type = sem_types[source]
        let target_type = sem_types[target]
        if source_type.args[0] == target_type.args[0] and sem_error_channel_assignable(source_type.args[1], target_type.args[1]) { return }
    }
    if target < 0 or sem_kind(target) != "result" or sem_kind(source) == "ok" or sem_kind(source) == "err" or source == target or not sem_assignable(source, target) { return }
    for existing in sem_result_lift_positions { if existing == position { return } }
    sem_result_lift_positions.append(position)
}
fn sem_type() -> int {
    let mut result = sem_unit
    if sem_match("FN") {
        sem_expect("LPAREN")
        let mut args: list[int] = []
        if not sem_is("RPAREN") {
            args.append(sem_type())
            while sem_match("COMMA") { args.append(sem_type()) }
        }
        sem_expect("RPAREN")
        sem_expect("ARROW")
        args.append(sem_type())
        return sem_intern("function", "", args)
    } elif sem_match("LPAREN") {
        result = sem_type()
        sem_expect("RPAREN")
    } else {
        let name = sem_expect("IDENT").val
        let mut is_parameter = false
        for parameter in sem_type_params { if parameter == name { is_parameter = true } }
        if is_parameter {
            let empty: list[int] = []
            result = sem_intern("typeparam", name, empty)
        } elif name == "int" or name == "int32" or name == "int64" { result = sem_int }
        elif name == "float" or name == "double" { result = sem_float }
        elif name == "bool" { result = sem_bool }
        elif name == "str" { result = sem_str }
        elif name == "unit" { result = sem_unit }
        elif name == "list" or name == "dict" or name == "tuple" or name == "Option" or name == "Result" or name == "Weak" {
            sem_expect("LBRACKET")
            let mut args: list[int] = [sem_type()]
            while sem_match("COMMA") { args.append(sem_type()) }
            sem_expect("RBRACKET")
            let mut kind = name
            if name == "Option" { kind = "optional" }
            if name == "Result" { kind = "result" }
            if name == "Weak" { kind = "weak" }
            if (kind == "list" or kind == "optional" or kind == "weak") and len(args) != 1 { sem_error("W2001", "type arity") }
            if (kind == "dict" or kind == "result") and len(args) != 2 { sem_error("W2001", "type arity") }
            if kind == "dict" and not sem_key(args[0]) { sem_error("W2010", "invalid dictionary key") }
            result = sem_intern(kind, "", args)
        } else {
            let base = sem_named(name)
            let generic = sem_generic_type(name)
            if sem_match("LBRACKET") {
                if generic < 0 { sem_error("W2001", "type is not generic: " + name) }
                let mut arguments: list[int] = [sem_type()]
                while sem_match("COMMA") { arguments.append(sem_type()) }
                sem_expect("RBRACKET")
                if len(arguments) != len(sem_generic_types[generic].params) { sem_error("W2001", "generic type arity: " + name) }
                result = sem_intern(sem_types[base].kind, name, arguments)
            } else {
                if generic >= 0 { sem_error("W2001", "generic type arguments required: " + name) }
                result = base
            }
        }
    }
    if sem_match("QUESTION") { result = sem_wrap("optional", result) }
    if sem_match("BANG") { result = sem_intern("result", "", [result, sem_error_union(sem_type())]) }
    return result
}
fn sem_key(type_id: int) -> bool {
    return type_id == sem_int or type_id == sem_str or type_id == sem_bool or sem_kind(type_id) == "enum"
}
fn sem_lookup(name: str) -> int {
    let mut i = len(sem_variables) - 1
    while i >= 0 {
        if sem_variables[i].name == name { return i }
        i = i - 1
    }
    return -1
}
fn sem_declare(name: str, type_id: int, mutable: bool) {
    for variable in sem_variables {
        if variable.name == name and variable.depth == sem_depth { sem_error("W1002", "duplicate declaration: " + name) }
    }
    sem_variables.append(SemVar { name: name, type_id: type_id, mutable: mutable, depth: sem_depth })
}
fn sem_value(type_id: int) -> SemValue {
    return SemValue { type_id: type_id, root: "", writable: -1, terminates: false }
}
fn sem_mutable(root: str) {
    if len(root) >= 5 and slice(root, 0, 5) == "this:" { return }
    if root != "" {
        let variable = sem_lookup(root)
        if variable >= 0 and sem_capture_depth >= 0 and sem_variables[variable].depth < sem_capture_depth { sem_error("W3001", "captured snapshots are immutable") }
        if variable < 0 or not sem_variables[variable].mutable { sem_error("W3001", "mutation of immutable binding") }
    }
}
fn sem_skip_block() -> int {
    sem_expect("LBRACE")
    let mut depth = 1
    while depth > 0 and not sem_is("EOF") {
        if sem_match("LBRACE") { depth = depth + 1 }
        elif sem_match("RBRACE") { depth = depth - 1 }
        else { sem_take() }
    }
    if depth != 0 { sem_error("W0006", "unclosed block") }
    return sem_pos
}
fn sem_collect_function(owner: str, visible: bool) {
    sem_expect("FN")
    let local = sem_expect("IDENT").val
    let previous_type_params = sem_type_params
    let mut type_params: list[str] = []
    let mut constraints: list[str] = []
    if sem_match("LBRACKET") {
        while not sem_is("RBRACKET") {
            let parameter = sem_expect("IDENT")
            for previous in type_params { if previous == parameter.val { report_error("W2001", parameter.line, parameter.col, "duplicate generic type parameter") } }
            type_params.append(parameter.val)
            let mut constraint = ""
            if sem_match("COLON") { constraint = sem_expect("IDENT").val }
            constraints.append(constraint)
            if not sem_match("COMMA") { break }
        }
        sem_expect("RBRACKET")
    }
    sem_type_params = type_params
    let name = owner + local
    if sem_function(name) >= 0 { sem_error("W1002", "duplicate function: " + name) }
    sem_expect("LPAREN")
    let mut params: list[str] = []
    let mut types: list[int] = []
    while not sem_is("RPAREN") {
        params.append(sem_expect("IDENT").val)
        sem_expect("COLON")
        types.append(sem_type())
        if not sem_match("COMMA") { break }
    }
    sem_expect("RPAREN")
    let mut returned = sem_unit
    if sem_match("ARROW") { returned = sem_type() }
    types.append(returned)
    let signature = sem_intern("function", "", types)
    let mut body = -1
    let mut end = sem_pos
    if sem_is("LBRACE") { body = sem_pos end = sem_skip_block() }
    sem_type_params = previous_type_params
    sem_functions.append(SemFunction { name: name, params: params, type_params: type_params, constraints: constraints, type_id: signature, body: body, end: end, owner: owner, visible: visible })
}
fn sem_collect_record(kind: str) {
    sem_take()
    let name = sem_expect("IDENT").val
    let previous_type_params = sem_type_params
    let mut type_params: list[str] = []
    let generic = sem_generic_type(name)
    if generic >= 0 { type_params = sem_generic_types[generic].params }
    sem_type_params = type_params
    if generic >= 0 {
        sem_expect("LBRACKET")
        let mut parameter_index = 0
        while not sem_is("RBRACKET") {
            let parameter = sem_expect("IDENT")
            if parameter_index >= len(type_params) or type_params[parameter_index] != parameter.val { report_error("W0006", parameter.line, parameter.col, "generic parameter list changed during collection") }
            if sem_match("COLON") { sem_expect("IDENT") }
            parameter_index = parameter_index + 1
            if not sem_match("COMMA") { break }
        }
        sem_expect("RBRACKET")
    }
    let type_id = sem_named(name)
    let mut parent = ""
    let mut interfaces: list[str] = []
    if sem_match("EXTENDS") { parent = sem_expect("IDENT").val }
    if sem_match("IMPLEMENTS") {
        interfaces.append(sem_expect("IDENT").val)
        while sem_match("COMMA") { interfaces.append(sem_expect("IDENT").val) }
    }
    if kind == "class" { sem_classes.append(SemClass { name: name, parent: parent, interfaces: interfaces }) }
    sem_expect("LBRACE")
    while not sem_is("RBRACE") {
        let mut visible = true
        if sem_match("PRIVATE") { visible = false } else { sem_match("PUBLIC") }
        if sem_is("FN") { sem_collect_function(name + ".", visible) }
        elif kind == "enum" {
            let variant = sem_expect("IDENT").val
            let mut payload_types: list[int] = []
            if sem_match("LPAREN") {
                if not sem_is("RPAREN") {
                    payload_types.append(sem_type())
                    while sem_match("COMMA") {
                        if sem_is("RPAREN") { break }
                        payload_types.append(sem_type())
                    }
                }
                sem_expect("RPAREN")
            }
            sem_variants.append(variant)
            sem_variant_types.append(type_id)
            sem_variant_payloads.append(payload_types)
            sem_match("COMMA")
        } else {
            let field = sem_expect("IDENT").val
            sem_expect("COLON")
            let field_type = sem_type()
            sem_fields.append(SemField { owner: name, name: field, type_id: field_type, visible: visible })
            sem_match("COMMA")
        }
    }
    sem_expect("RBRACE")
    sem_type_params = previous_type_params
}
let mut sem_expected = -1
fn sem_builtin(name: str) -> bool {
    return name == "join_strings" or name == "print" or name == "eprint" or name == "len" or name == "int" or name == "float" or name == "str" or name == "ord" or name == "chr" or name == "bytes" or name == "slice" or name == "args" or name == "exit" or name == "enumerate" or name == "dict_items" or name == "read_file" or name == "write_file" or name == "Some" or name == "Ok" or name == "Err" or name == "weak" or name == "upgrade"
}
fn sem_call_builtin(name: str, args: list[int]) -> int {
    let count = len(args)
    if name == "print" or name == "eprint" { return sem_unit }
    if name == "args" {
        if count != 0 { sem_error("W2005", "args arity") }
        return sem_wrap("list", sem_str)
    }
    let mut arity = 1
    if name == "slice" { arity = 3 }
    if name == "write_file" or name == "join_strings" { arity = 2 }
    if count != arity { sem_error("W2005", "builtin arity: " + name) }
    if name == "join_strings" {
        if count != 2 { sem_error("W2005", "join_strings arity") }
        sem_require(args[0], sem_wrap("list", sem_str), "W2001")
        sem_require(args[1], sem_str, "W2001")
        return sem_str
    }
    let first = args[0]
    let kind = sem_kind(first)
    if name == "Some" { return sem_wrap("optional", first) }
    if name == "Ok" or name == "Err" {
        if sem_expected >= 0 and sem_kind(sem_expected) == "result" {
            let channel = sem_types[sem_expected].args
            if name == "Ok" { sem_require(first, channel[0], "W2001") }
            else { sem_require(first, channel[1], "W2001") }
            return sem_expected
        }
        if name == "Ok" { return sem_wrap("ok", first) }
        return sem_wrap("err", first)
    }
    if name == "len" {
        if kind != "list" and kind != "dict" and kind != "tuple" and first != sem_str { sem_error("W2001", "len requires a collection or string") }
        return sem_int
    }
    if name == "int" or name == "float" or name == "str" {
        if name != "str" and first != sem_int and first != sem_float and first != sem_str and first != sem_bool { sem_error("W2001", "conversion argument") }
        if name == "int" { return sem_int }
        if name == "float" { return sem_float }
        return sem_str
    }
    if name == "chr" or name == "exit" {
        sem_require(first, sem_int, "W2001")
        if name == "chr" { return sem_str }
        return sem_unit
    }
    if name == "slice" {
        # SPEC 11.1: slice() is polymorphic over str and list[T] and preserves the
        # container kind.
        let first_type = sem_types[first]
        sem_require(args[1], sem_int, "W2001")
        sem_require(args[2], sem_int, "W2001")
        if first == sem_str { return sem_str }
        if first_type.kind == "list" { return first }
        sem_error("W2001", "slice expects str or list")
        return sem_str
    }
    if name == "ord" or name == "bytes" or name == "read_file" or name == "write_file" {
        sem_require(first, sem_str, "W2001")
        if name == "ord" { return sem_int }
        if name == "bytes" { return sem_wrap("list", sem_int) }
        let io = sem_named("IoError")
        if name == "read_file" { return sem_intern("result", "", [sem_str, io]) }
        sem_require(args[1], sem_str, "W2001")
        return sem_intern("result", "", [sem_unit, io])
    }
    if name == "weak" {
        if kind != "class" { sem_error("W2001", "weak requires class") }
        return sem_wrap("weak", first)
    }
    if name == "upgrade" {
        if kind != "weak" { sem_error("W2001", "upgrade requires weak") }
        return sem_wrap("optional", sem_types[first].args[0])
    }
    if name == "enumerate" {
        if kind != "list" { sem_error("W2001", "enumerate requires list") }
        return sem_wrap("list", sem_intern("tuple", "", [sem_int, sem_types[first].args[0]]))
    }
    if name == "dict_items" {
        if kind != "dict" { sem_error("W2001", "dict_items requires dict") }
        return sem_wrap("list", sem_intern("tuple", "", sem_types[first].args))
    }
    sem_error("W1001", "unknown builtin")
    return sem_unit
}
fn sem_check_call(signature: int, args: list[int]) -> int {
    let type_ = sem_types[signature]
    if type_.kind == "builtin" { return sem_call_builtin(type_.name, args) }
    if type_.kind == "enum_ctor" {
        let mut separator = -1
        for i in 0..len(type_.name) - 1 { if slice(type_.name, i, i + 1) == "." { separator = i } }
        if separator < 0 { sem_error("W9999", "invalid enum constructor metadata") }
        let owner = slice(type_.name, 0, separator)
        let variant = slice(type_.name, separator + 1, len(type_.name))
        if owner == "Option" and variant == "Some" {
            if len(args) != 1 { sem_error("W2005", "Option.Some arity") }
            return sem_wrap("optional", args[0])
        }
        if owner == "Result" and (variant == "Ok" or variant == "Err") {
            if len(args) != 1 { sem_error("W2005", "Result constructor arity") }
            if sem_expected >= 0 and sem_kind(sem_expected) == "result" {
                let expected = sem_types[sem_expected]
                if variant == "Ok" { sem_require(args[0], expected.args[0], "W2001") }
                else { sem_require(args[0], expected.args[1], "W2001") }
            }
            if variant == "Ok" { return sem_wrap("ok", args[0]) }
            return sem_wrap("err", args[0])
        }
        let mut target = type_.args[0]
        let generic = sem_generic_type(owner)
        let mut payload_types: list[int] = []
        for i in 1..len(type_.args) { payload_types.append(type_.args[i]) }
        if len(args) != len(payload_types) { sem_error("W2005", "enum constructor arity: " + owner + "." + variant) }
        if generic >= 0 and len(sem_types[target].args) == 0 {
            let empty_names: list[str] = []
            let empty_types: list[int] = []
            sem_unify_names = empty_names
            sem_unify_types = empty_types
            for i in 0..len(args) { if not sem_unify_type(payload_types[i], args[i]) { sem_error("W2001", "enum payload type mismatch") } }
            let mut concrete: list[int] = []
            for parameter in sem_generic_types[generic].params {
                let mut found = -1
                for i in 0..len(sem_unify_names) { if sem_unify_names[i] == parameter { found = sem_unify_types[i] } }
                if found < 0 { sem_error("W2001", "cannot infer enum type argument: " + parameter) }
                concrete.append(found)
            }
            target = sem_intern("enum", owner, concrete)
        } elif generic >= 0 {
            sem_unify_names = sem_generic_types[generic].params
            sem_unify_types = sem_types[target].args
            for i in 0..len(args) {
                sem_require(args[i], sem_substitute_type(payload_types[i], sem_unify_names, sem_unify_types), "W2001")
            }
        } else {
            for i in 0..len(args) { sem_require(args[i], payload_types[i], "W2001") }
        }
        return target
    }
    if type_.kind == "struct_ctor" {
        let generic = sem_generic_type(type_.name)
        let mut target = sem_named(type_.name)
        let mut explicit = false
        if len(type_.args) == 1 { target = type_.args[0] explicit = true }
        let mut fields: list[int] = []
        for i in 0..len(sem_fields) { if sem_fields[i].owner == type_.name { fields.append(i) } }
        if len(args) != len(fields) { sem_error("W2005", "struct constructor arity: " + type_.name) }
        let empty_names: list[str] = []
        let empty_types: list[int] = []
        sem_unify_names = empty_names
        sem_unify_types = empty_types
        if explicit and generic >= 0 {
            sem_unify_names = sem_generic_types[generic].params
            sem_unify_types = sem_types[target].args
        }
        for i in 0..len(args) {
            let field_type = sem_fields[fields[i]].type_id
            if generic >= 0 and not explicit { sem_unify_type(field_type, args[i]) }
            sem_require(args[i], sem_substitute_type(field_type, sem_unify_names, sem_unify_types), "W2001")
        }
        if generic >= 0 and not explicit {
            let mut concrete: list[int] = []
            for parameter in sem_generic_types[generic].params {
                let mut inferred = -1
                for i in 0..len(sem_unify_names) { if sem_unify_names[i] == parameter { inferred = sem_unify_types[i] } }
                if inferred < 0 { sem_error("W2001", "cannot infer generic struct type argument: " + parameter) }
                concrete.append(inferred)
            }
            target = sem_intern(sem_generic_types[generic].kind, type_.name, concrete)
        }
        return target
    }
    if type_.kind == "constructor" {
        let target = type_.args[0]
        let method = sem_method(sem_types[target].name, "init")
        if method >= 0 { sem_check_call(sem_functions[method].type_id, args) }
        elif len(args) != 0 { sem_error("W2005", "constructor arity") }
        return target
    }
    if type_.kind != "function" { sem_error("W2005", "value is not callable") }
    if len(type_.args) != len(args) + 1 { sem_error("W2005", "call arity") }
    let empty_names: list[str] = []
    let empty_types: list[int] = []
    sem_unify_names = empty_names
    sem_unify_types = empty_types
    for i in 0..len(args) { sem_unify_type(type_.args[i], args[i]) }
    for i in 0..len(args) {
        let expected = sem_substitute_type(type_.args[i], sem_unify_names, sem_unify_types)
        sem_require(args[i], expected, "W2001")
    }
    return sem_substitute_type(type_.args[len(args)], sem_unify_names, sem_unify_types)
}
fn sem_substitute_type(type_id: int, names: list[str], values: list[int]) -> int {
    let type_ = sem_types[type_id]
    if type_.kind == "typeparam" {
        for i in 0..len(names) { if names[i] == type_.name { return values[i] } }
        return type_id
    }
    if len(type_.args) == 0 { return type_id }
    let mut replaced: list[int] = []
    let mut changed = false
    for arg in type_.args {
        let next = sem_substitute_type(arg, names, values)
        replaced.append(next)
        if next != arg { changed = true }
    }
    if not changed { return type_id }
    return sem_intern(type_.kind, type_.name, replaced)
}
fn sem_unify_type(pattern: int, actual: int) -> bool {
    let expected = sem_types[pattern]
    if expected.kind == "typeparam" {
        for i in 0..len(sem_unify_names) {
            if sem_unify_names[i] == expected.name { return sem_unify_types[i] == actual }
        }
        sem_unify_names.append(expected.name)
        sem_unify_types.append(actual)
        return true
    }
    let actual_type = sem_types[actual]
    if expected.kind != actual_type.kind or expected.name != actual_type.name or len(expected.args) != len(actual_type.args) { return false }
    for i in 0..len(expected.args) {
        if not sem_unify_type(expected.args[i], actual_type.args[i]) { return false }
    }
    return true
}
fn sem_field(owner: str, name: str) -> int {
    let mut current = owner
    let mut visits = 0
    while current != "" and visits <= len(sem_classes) {
        for i in 0..len(sem_fields) {
            let field = sem_fields[i]
            if field.owner == current and field.name == name { return i }
        }
        let mut next = ""
        for class_ in sem_classes { if class_.name == current { next = class_.parent } }
        current = next
        visits = visits + 1
    }
    return -1
}
fn sem_member(receiver: SemValue, name: str) -> SemValue {
    let type_ = sem_types[receiver.type_id]
    if type_.kind == "typeparam" {
        let mut constraint = ""
        for i in 0..len(sem_type_params) {
            if sem_type_params[i] == type_.name and i < len(sem_active_constraints) { constraint = sem_active_constraints[i] }
        }
        if constraint != "" {
            let method_index = sem_method(constraint, name)
            if method_index >= 0 {
                let method = sem_functions[method_index]
                return SemValue { type_id: method.type_id, root: "#method", writable: -1, terminates: false }
            }
        }
        sem_error("W3002", "unknown member on generic type parameter: " + name)
    }
    if type_.kind == "enum" {
        for i in 0..len(sem_variants) {
            if sem_variants[i] == name and sem_types[sem_variant_types[i]].name == type_.name {
                if len(sem_variant_payloads[i]) == 0 { return sem_value(receiver.type_id) }
                let mut arguments: list[int] = [receiver.type_id]
                for payload in sem_variant_payloads[i] { arguments.append(payload) }
                return sem_value(sem_intern("enum_ctor", type_.name + "." + name, arguments))
            }
        }
        sem_error("W1001", "unknown enum variant")
    }
    if type_.kind == "optional" and (name == "Some" or name == "None") {
        if name == "None" { return sem_value(sem_none) }
        return sem_value(sem_intern("enum_ctor", "Option.Some", [receiver.type_id, type_.args[0]]))
    }
    if type_.kind == "result" and (name == "Ok" or name == "Err") {
        let mut payload = type_.args[0]
        if name == "Err" { payload = type_.args[1] }
        return sem_value(sem_intern("enum_ctor", "Result." + name, [receiver.type_id, payload]))
    }
    if type_.kind == "list" or type_.kind == "dict" {
        let mut args: list[int] = []
        if name == "append" and type_.kind == "list" {
            sem_mutable(receiver.root)
            args = [type_.args[0], sem_unit]
        } elif name == "pop" and type_.kind == "list" {
            sem_mutable(receiver.root)
            args = [type_.args[0]]
        } elif name == "clear" and type_.kind == "list" {
            sem_mutable(receiver.root)
            args = [sem_unit]
        } elif name == "get" and type_.kind == "dict" { args = [type_.args[0], sem_wrap("optional", type_.args[1])] }
        elif name == "keys" and type_.kind == "dict" { args = [sem_wrap("list", type_.args[0])] }
        elif name == "values" and type_.kind == "dict" { args = [sem_wrap("list", type_.args[1])] }
        else { sem_error("W3002", "unknown collection method") }
        return SemValue { type_id: sem_intern("function", "", args), root: "#collection", writable: -1, terminates: false }
    }
    let field_index = sem_field(type_.name, name)
    if field_index >= 0 {
        let field = sem_fields[field_index]
        if not field.visible and sem_owner != field.owner { sem_error("W3002", "private field") }
        if sem_initializing and receiver.root == "this" and field.owner == sem_owner {
            let mut found = false
            for initialized in sem_initialized { if initialized == name { found = true } }
            if not found and not sem_is("ASSIGN") { sem_error("W3004", "read before initialization") }
        }
        let mut root = receiver.root
        if type_.kind == "class" {
            root = ""
            if sem_initializing and receiver.root == "this" { root = "this:" + name }
        }
        let mut field_type = field.type_id
        let generic = sem_generic_type(type_.name)
        if generic >= 0 and len(type_.args) == len(sem_generic_types[generic].params) {
            field_type = sem_substitute_type(field_type, sem_generic_types[generic].params, type_.args)
        }
        return SemValue { type_id: field_type, root: root, writable: field_type, terminates: false }
    }
    let method_index = sem_method(type_.name, name)
    if method_index >= 0 {
        let method = sem_functions[method_index]
        if not method.visible and method.owner != sem_owner + "." { sem_error("W3002", "private method access") }
        return SemValue { type_id: method.type_id, root: "#method", writable: -1, terminates: false }
    }
    sem_error("W3002", "unknown member: " + name)
    return sem_value(sem_unit)
}
fn sem_prefix(allow_struct: bool, statement: bool) -> SemValue {
    if sem_is("PIPE") { return sem_lambda() }
    if sem_match("INT") { return sem_value(sem_int) }
    if sem_match("FLOAT") { return sem_value(sem_float) }
    if sem_match("STR") { return sem_value(sem_str) }
    if sem_match("TRUE") or sem_match("FALSE") { return sem_value(sem_bool) }
    if sem_match("NONE") { return sem_value(sem_none) }
    if sem_match("MINUS") {
        let value = sem_expression(9, allow_struct)
        if value.type_id != sem_int and value.type_id != sem_float { sem_error("W2001", "numeric negation") }
        return sem_value(value.type_id)
    }
    if sem_match("NOT") {
        sem_require(sem_expression(9, allow_struct).type_id, sem_bool, "W2001")
        return sem_value(sem_bool)
    }
    if sem_match("LPAREN") {
        if sem_match("RPAREN") {
            let empty: list[int] = []
            return sem_value(sem_intern("tuple", "", empty))
        }
        let first = sem_expression(0, true)
        if sem_match("COMMA") {
            let mut types: list[int] = [first.type_id]
            while not sem_is("RPAREN") {
                types.append(sem_expression(0, true).type_id)
                if not sem_match("COMMA") { break }
            }
            sem_expect("RPAREN")
            return sem_value(sem_intern("tuple", "", types))
        }
        sem_expect("RPAREN")
        return first
    }
    if sem_match("LBRACKET") {
        if sem_match("RBRACKET") { return sem_value(sem_simple("empty")) }
        let context = sem_expected
        let mut element = -1
        if context >= 0 and sem_kind(context) == "list" { element = sem_types[context].args[0] }
        sem_expected = element
        let mut first = sem_expression(0, true).type_id
        if element >= 0 { sem_require(first, element, "W2001") first = element }
        while sem_match("COMMA") {
            if sem_is("RBRACKET") { break }
            sem_require(sem_expression(0, true).type_id, first, "W2001")
        }
        sem_expect("RBRACKET")
        sem_expected = context
        return sem_value(sem_wrap("list", first))
    }
    if sem_match("LBRACE") {
        if sem_match("RBRACE") { return sem_value(sem_simple("empty")) }
        let context = sem_expected
        let mut expected_key = -1
        let mut expected_value = -1
        if context >= 0 and sem_kind(context) == "dict" {
            expected_key = sem_types[context].args[0]
            expected_value = sem_types[context].args[1]
        }
        sem_expected = expected_key
        let key = sem_expression(0, true).type_id
        sem_expected = context
        if not sem_key(key) { sem_error("W2010", "invalid dictionary key") }
        if expected_key >= 0 { sem_require(key, expected_key, "W2001") }
        sem_expect("COLON")
        sem_expected = expected_value
        let value = sem_expression(0, true).type_id
        sem_expected = context
        if expected_value >= 0 { sem_require(value, expected_value, "W2001") }
        while sem_match("COMMA") {
            if sem_is("RBRACE") { break }
            sem_expected = expected_key
            let next_key = sem_expression(0, true).type_id
            sem_expected = context
            sem_require(next_key, key, "W2001")
            sem_expect("COLON")
            sem_expected = expected_value
            let next_value = sem_expression(0, true).type_id
            sem_expected = context
            sem_require(next_value, value, "W2001")
        }
        sem_expect("RBRACE")
        if expected_key >= 0 { return sem_value(context) }
        return sem_value(sem_intern("dict", "", [key, value]))
    }
    if sem_is("IF") { return sem_if(statement) }
    if sem_is("MATCH") { return sem_match_expression() }
    if sem_is("THIS") or sem_is("SUPER") {
        if sem_capture_depth >= 0 { sem_error("W2001", "capture receiver through explicit local binding") }
        let is_super = sem_take().kind == "SUPER"
        if sem_owner == "" { sem_error("W1004", "receiver outside method") }
        let mut owner = sem_owner
        if is_super {
            owner = ""
            for class_ in sem_classes { if class_.name == sem_owner { owner = class_.parent } }
            if owner == "" { sem_error("W1004", "super without base class") }
        }
        return SemValue { type_id: sem_named(owner), root: "this", writable: -1, terminates: false }
    }
    sem_match("NEW")
    let name = sem_expect("IDENT").val
    let variable = sem_lookup(name)
    if variable >= 0 {
        let value = sem_variables[variable]
        if sem_capture_depth >= 0 and value.depth < sem_capture_depth and not module_contains(sem_capture_names, name) { sem_capture_names.append(name) }
        return SemValue { type_id: value.type_id, root: name, writable: value.type_id, terminates: false }
    }
    if name == "None" { return sem_value(sem_none) }
    if name == "Option" or name == "Result" {
        sem_expect("DOT")
        let variant = sem_expect("IDENT").val
        if name == "Option" and variant == "None" { return sem_value(sem_none) }
        if name == "Option" and variant == "Some" or name == "Result" and (variant == "Ok" or variant == "Err") {
            let empty: list[int] = []
            return sem_value(sem_intern("enum_ctor", name + "." + variant, empty))
        }
        sem_error("W1001", "unknown built-in enum variant: " + name + "." + variant)
    }
    if sem_builtin(name) {
        let empty: list[int] = []
        return sem_value(sem_intern("builtin", name, empty))
    }
    let function = sem_function(name)
    if function >= 0 {
        let signature = sem_functions[function]
        let mut type_id = signature.type_id
        if len(signature.type_params) > 0 and sem_match("LBRACKET") {
            let mut arguments: list[int] = []
            while not sem_is("RBRACKET") {
                arguments.append(sem_type())
                if not sem_match("COMMA") { break }
            }
            sem_expect("RBRACKET")
            if len(arguments) != len(signature.type_params) { sem_error("W2001", "generic function type arity") }
            let mut substitutions: list[int] = []
            for parameter in signature.type_params {
                let empty: list[int] = []
                substitutions.append(sem_intern("typeparam", parameter, empty))
            }
            let target = sem_types[signature.type_id]
            let mut specialized: list[int] = []
            for part in target.args { specialized.append(sem_substitute_type(part, signature.type_params, arguments)) }
            type_id = sem_intern("function", "", specialized)
        }
        return SemValue { type_id: type_id, root: "fn:" + name, writable: -1, terminates: false }
    }
    let generic_type = sem_generic_type(name)
    let mut selected_type = -1
    if generic_type >= 0 and sem_match("LBRACKET") {
        let mut type_arguments: list[int] = []
        while not sem_is("RBRACKET") {
            type_arguments.append(sem_type())
            if not sem_match("COMMA") { break }
        }
        sem_expect("RBRACKET")
        if len(type_arguments) != len(sem_generic_types[generic_type].params) { sem_error("W2001", "generic type arity: " + name) }
        selected_type = sem_intern(sem_generic_types[generic_type].kind, name, type_arguments)
    } elif sem_expected >= 0 and generic_type >= 0 and sem_same_type_declaration(sem_named(name), sem_expected) {
        selected_type = sem_expected
    }
    let mut named_type = selected_type
    if named_type < 0 {
        for i in 0..len(sem_types) {
            if sem_types[i].name == name and (sem_types[i].kind == "class" or sem_types[i].kind == "struct" or sem_types[i].kind == "enum") {
                if len(sem_types[i].args) == 0 { named_type = i }
            }
        }
    }
    if named_type < 0 {
        let mut variant = -1
        for i in 0..len(sem_variants) {
            if sem_variants[i] == name {
                if variant >= 0 { sem_error("W1001", "ambiguous enum variant") }
                if len(sem_variant_payloads[i]) > 0 { sem_error("W2005", "enum variant requires a payload: " + name) }
                variant = sem_variant_types[i]
            }
        }
        if variant >= 0 { return sem_value(variant) }
        sem_error("W1001", "unknown identifier: " + name)
    }
    if sem_kind(named_type) == "class" { return sem_value(sem_wrap("constructor", named_type)) }
    if sem_kind(named_type) == "struct" {
        if sem_is("LPAREN") {
            let mut target_types: list[int] = []
            if selected_type >= 0 { target_types.append(selected_type) }
            return sem_value(sem_intern("struct_ctor", name, target_types))
        }
        if allow_struct and sem_match("LBRACE") {
            let empty_names: list[str] = []
            let empty_types: list[int] = []
            sem_unify_names = empty_names
            sem_unify_types = empty_types
            if selected_type >= 0 and generic_type >= 0 {
                sem_unify_names = sem_generic_types[generic_type].params
                sem_unify_types = sem_types[selected_type].args
            }
            let mut initialized: list[str] = []
            while not sem_is("RBRACE") {
                let field_name = sem_expect("IDENT").val
                let field = sem_field(name, field_name)
                if field < 0 { sem_error("W3002", "unknown struct field") }
                for previous in initialized { if previous == field_name { sem_error("W2007", "duplicate initializer") } }
                initialized.append(field_name)
                sem_expect("COLON")
                let actual = sem_expression(0, true).type_id
                if generic_type >= 0 and selected_type < 0 { sem_unify_type(sem_fields[field].type_id, actual) }
                let expected = sem_substitute_type(sem_fields[field].type_id, sem_unify_names, sem_unify_types)
                sem_require(actual, expected, "W2001")
                sem_match("COMMA")
            }
            sem_expect("RBRACE")
            for field in sem_fields {
                if field.owner == name {
                    let mut found = false
                    for candidate in initialized { if candidate == field.name { found = true } }
                    if not found { sem_error("W2007", "missing struct field") }
                }
            }
            if generic_type >= 0 and selected_type < 0 {
                let mut concrete_types: list[int] = []
                for parameter in sem_generic_types[generic_type].params {
                    let mut concrete = -1
                    for i in 0..len(sem_unify_names) { if sem_unify_names[i] == parameter { concrete = sem_unify_types[i] } }
                    if concrete < 0 { sem_error("W2001", "cannot infer generic struct type argument: " + parameter) }
                    concrete_types.append(concrete)
                }
                named_type = sem_intern(sem_generic_types[generic_type].kind, name, concrete_types)
            }
            return sem_value(named_type)
        }
        return sem_value(named_type)
    }
    return sem_value(named_type)
}
fn sem_complete_constructor() {
    if sem_initializing {
        for field in sem_fields {
            if field.owner == sem_owner {
                let mut found = false
                for initialized in sem_initialized { if initialized == field.name { found = true } }
                if not found { sem_error("W3004", "uninitialized constructor field: " + field.name) }
            }
        }
    }
}
fn sem_expression(minimum: int, allow_struct: bool) -> SemValue {
    let statement = sem_statement_context
    sem_statement_context = false
    let mut left = sem_prefix(allow_struct, statement)
    while true {
        let call_position = sem_pos + sem_token_offset
        let call_line = sem_at().line
        let call_col = sem_at().col
        if sem_match("LPAREN") {
            if left.root == "#collection" { sem_collection_call_positions.append(call_position) }
            if sem_kind(left.type_id) == "function" and left.root != "#method" and left.root != "#collection" and not (len(left.root) >= 3 and slice(left.root, 0, 3) == "fn:") { sem_indirect_positions.append(call_position) }
            let mut args: list[int] = []
            let signature = sem_types[left.type_id]
            let previous_expected = sem_expected
            while not sem_is("RPAREN") {
                sem_expected = -1
                if signature.kind == "function" and len(args) + 1 < len(signature.args) { sem_expected = signature.args[len(args)] }
                if signature.kind == "enum_ctor" and previous_expected >= 0 {
                    let expected_type = sem_types[previous_expected]
                    if signature.name == "Option.Some" and expected_type.kind == "optional" { sem_expected = expected_type.args[0] }
                    elif signature.name == "Result.Ok" and expected_type.kind == "result" { sem_expected = expected_type.args[0] }
                    elif signature.name == "Result.Err" and expected_type.kind == "result" { sem_expected = expected_type.args[1] }
                }
                let argument_start = sem_pos + sem_token_offset
                let argument_expected = sem_expected
                let argument = sem_expression(0, true)
                sem_mark_result_lift(argument_start, argument.type_id, argument_expected)
                if sem_initializing and argument.root == "this" { sem_complete_constructor() }
                args.append(argument.type_id)
                if not sem_match("COMMA") { break }
            }
            sem_expect("RPAREN")
            sem_expected = previous_expected
            if len(left.root) >= 3 and slice(left.root, 0, 3) == "fn:" {
                let function_index = sem_function(slice(left.root, 3, len(left.root)))
                if function_index >= 0 and len(sem_functions[function_index].type_params) > 0 {
                    sem_check_generic_constraints(function_index, args, call_line, call_col)
                }
            }
            left = sem_value(sem_check_call(left.type_id, args))
        } elif sem_match("DOT") {
            if sem_kind(left.type_id) == "class" { sem_class_projection_positions.append(call_position) }
            let name = sem_expect("IDENT").val
            left = sem_member(left, name)
        } elif sem_match("LBRACKET") {
            let index = sem_expression(0, true).type_id
            sem_expect("RBRACKET")
            let type_ = sem_types[left.type_id]
            if type_.kind == "list" {
                sem_require(index, sem_int, "W2001")
                left = SemValue { type_id: type_.args[0], root: left.root, writable: type_.args[0], terminates: false }
            } elif type_.kind == "dict" {
                # `d[k]` yields V and panics with W4002 when the key is absent; the
                # optional form is `d.get(k)`. See SPEC 10.2.
                sem_require(index, type_.args[0], "W2001")
                left = SemValue { type_id: type_.args[1], root: left.root, writable: type_.args[1], terminates: false }
            } elif left.type_id == sem_str {
                sem_require(index, sem_int, "W2001")
                left = sem_value(sem_str)
            } else { sem_error("W2001", "value cannot be indexed") }
        } elif sem_match("QUESTION") {
            let type_ = sem_types[left.type_id]
            let returned = sem_types[sem_return]
            if type_.kind != "optional" and type_.kind != "result" { sem_error("W2006", "propagation operand") }
            if returned.kind != type_.kind { sem_error("W2006", "propagation return channel") }
            if type_.kind == "result" and not sem_error_channel_assignable(type_.args[1], returned.args[1]) { sem_error("W2006", "propagation error channel") }
            left = sem_value(type_.args[0])
        } elif sem_match("ELSE") {
            let operand = sem_types[left.type_id]
            if operand.kind != "optional" and operand.kind != "result" { sem_error("W2006", "handler operand") }
            let old_variables = sem_variables
            sem_depth = sem_depth + 1
            if sem_is("IDENT") {
                let error_name = sem_take().val
                if operand.kind != "result" { sem_error("W2006", "optional has no error binding") }
                sem_declare(error_name, operand.args[1], false)
            }
            let handler = sem_block(false)
            sem_depth = sem_depth - 1
            sem_variables = old_variables
            if not handler.terminates { sem_require(handler.type_id, operand.args[0], "W2001") }
            left = sem_value(operand.args[0])
        } else {
            let operator = sem_at().kind
            let precedence = op_precedence(operator)
            if precedence <= minimum { break }
            let logical_left = sem_pos - 1
            let mut logical_constant = -1
            if logical_left >= 0 {
                if sem_tokens[logical_left].kind == "FALSE" { logical_constant = 0 }
                elif sem_tokens[logical_left].kind == "TRUE" { logical_constant = 1 }
            }
            sem_take()
            let mut right_minimum = precedence
            if operator == "ASSIGN" or operator == "QQ" { right_minimum = precedence - 1 }
            let previous_expected = sem_expected
            if operator == "ASSIGN" { sem_expected = left.writable }
            let before_right = sem_initialized
            let right = sem_expression(right_minimum, allow_struct)
            let after_right = sem_initialized
            sem_expected = previous_expected
            if operator == "ASSIGN" {
                if left.writable < 0 { sem_error("W2002", "invalid assignment target") }
                sem_mutable(left.root)
                sem_require(right.type_id, left.writable, "W2001")
                if sem_initializing and len(left.root) > 5 and slice(left.root, 0, 5) == "this:" { sem_initialized.append(slice(left.root, 5, len(left.root))) }
                left = sem_value(left.writable)
            } elif operator == "QQ" {
                if left.type_id == sem_none {
                    sem_initialized = after_right
                } else {
                    sem_initialized = sem_intersect(before_right, after_right)
                }
                if left.type_id == sem_none { left = right }
                elif sem_kind(left.type_id) == "optional" {
                    let inner = sem_types[left.type_id].args[0]
                    sem_require(right.type_id, inner, "W2001")
                    left = sem_value(inner)
                } else { sem_error("W2006", "coalesce requires optional") }
            } elif operator == "DOT_DOT" or operator == "DOT_DOT_EQ" {
                sem_require(left.type_id, sem_int, "W2001")
                sem_require(right.type_id, sem_int, "W2001")
                left = sem_value(sem_wrap("list", sem_int))
            } elif operator == "AND" or operator == "OR" {
                sem_require(left.type_id, sem_bool, "W2001")
                sem_require(right.type_id, sem_bool, "W2001")
                let skips_right = (operator == "AND" and logical_constant == 0) or (
                    operator == "OR" and logical_constant == 1
                )
                let runs_right = (operator == "AND" and logical_constant == 1) or (
                    operator == "OR" and logical_constant == 0
                )
                if skips_right { sem_initialized = before_right }
                elif runs_right { sem_initialized = after_right }
                else { sem_initialized = sem_intersect(before_right, after_right) }
                left = sem_value(sem_bool)
            } elif operator == "EQ" or operator == "NEQ" {
                let left_kind = sem_kind(left.type_id)
                let right_kind = sem_kind(right.type_id)
                let result_pair = (left_kind == "ok" or left_kind == "err") and (right_kind == "ok" or right_kind == "err")
                if not result_pair and not sem_assignable(left.type_id, right.type_id) and not sem_assignable(right.type_id, left.type_id) { sem_error("W2001", "equality types") }
                left = sem_value(sem_bool)
            } else {
                if left.type_id != right.type_id { sem_error("W2001", "binary operand types") }
                if left.type_id != sem_int and left.type_id != sem_float and (operator != "PLUS" or left.type_id != sem_str) { sem_error("W2001", "invalid binary operation") }
                if operator == "PERCENT" and left.type_id != sem_int { sem_error("W2001", "modulo requires integers") }
                if operator == "LT" or operator == "LTE" or operator == "GT" or operator == "GTE" { left = sem_value(sem_bool) }
                else { left = sem_value(left.type_id) }
            }
        }
    }
    if left.root == "#method" or left.root == "#collection" or sem_kind(left.type_id) == "builtin" or sem_kind(left.type_id) == "constructor" { sem_error("W2013", "callable syntax requires an explicit lambda adapter") }
    return left
}
fn sem_intersect(left: list[str], right: list[str]) -> list[str] {
    let mut result: list[str] = []
    for value in left { for other in right { if value == other { result.append(value) } } }
    return result
}
fn sem_if(statement: bool) -> SemValue {
    sem_expect("IF")
    sem_require(sem_expression(0, false).type_id, sem_bool, "W2001")
    let initial = sem_initialized
    let first = sem_block(statement)
    let mut initialized = sem_initialized
    let mut all_return = first.terminates
    let mut common = first.type_id
    while sem_match("ELIF") {
        sem_initialized = initial
        sem_require(sem_expression(0, false).type_id, sem_bool, "W2001")
        let branch = sem_block(statement)
        if not branch.terminates and not all_return and branch.type_id != common { if not statement { sem_error("W2001", "incompatible if branches") } common = sem_unit }
        if not branch.terminates {
            if all_return { initialized = sem_initialized } else { initialized = sem_intersect(initialized, sem_initialized) }
            if all_return { common = branch.type_id }
        }
        all_return = all_return and branch.terminates
    }
    sem_initialized = initial
    if sem_match("ELSE") {
        let branch = sem_block(statement)
        if not branch.terminates {
            if not all_return and branch.type_id != common { if not statement { sem_error("W2001", "incompatible if branches") } common = sem_unit }
            if all_return { initialized = sem_initialized } else { initialized = sem_intersect(initialized, sem_initialized) }
            if all_return { common = branch.type_id }
        }
        all_return = all_return and branch.terminates
    } else {
        initialized = sem_intersect(initialized, initial)
        all_return = false
        common = sem_unit
    }
    sem_initialized = initialized
    if statement { common = sem_unit }
    return SemValue { type_id: common, root: "", writable: -1, terminates: all_return }
}
fn sem_pattern(subject: int) -> str {
    if sem_match("ELSE") { return "*" }
    if sem_match("NONE") { return "None" }
    if sem_is("INT") or sem_is("FLOAT") or sem_is("STR") or sem_is("TRUE") or sem_is("FALSE") {
        let token = sem_take()
        let mut type_id = sem_bool
        if token.kind == "INT" { type_id = sem_int }
        elif token.kind == "FLOAT" { type_id = sem_float }
        elif token.kind == "STR" { type_id = sem_str }
        sem_require(type_id, subject, "W2001")
        return "literal:" + token.val
    }
    let pattern_position = sem_pos + sem_token_offset
    let mut owner = ""
    let mut name = sem_expect("IDENT").val
    if name == "_" { return "*" }
    if sem_match("DOT") { owner = name name = sem_expect("IDENT").val }
    let kind = sem_kind(subject)
    if sem_match("LPAREN") {
        if kind == "error_union" {
            if owner != "" { sem_error("W2001", "error type patterns must be unqualified") }
            let mut error_type = -1
            if name == "int" { error_type = sem_int }
            elif name == "float" { error_type = sem_float }
            elif name == "bool" { error_type = sem_bool }
            elif name == "str" { error_type = sem_str }
            else { error_type = sem_named(name) }
            let mut is_alternative = false
            for alternative in sem_types[subject].args { if alternative == error_type { is_alternative = true } }
            if not is_alternative { sem_error("W2001", "error type pattern is not an alternative of this union") }
            if sem_is("RPAREN") { sem_error("W2005", "error type pattern requires exactly one payload binding") }
            if not sem_is("IDENT") { sem_error("W2005", "error type pattern payload must be a binding or wildcard") }
            let child_pattern = sem_pattern(error_type)
            if child_pattern != "*" { sem_error("W2005", "error type pattern payload must be a binding or wildcard") }
            if sem_match("COMMA") { sem_error("W2005", "error type pattern requires exactly one payload binding") }
            sem_expect("RPAREN")
            sem_error_pattern_positions.append(pattern_position)
            sem_error_pattern_kinds.append(sem_kind(error_type))
            sem_error_pattern_names.append(sem_error_type_name(error_type))
            return sem_error_type_name(error_type)
        }
        let mut payload_types: list[int] = []
        let mut valid = false
        if (owner == "" or owner == "Option") and name == "Some" and kind == "optional" {
            payload_types = [sem_types[subject].args[0]]
            valid = true
        } elif (owner == "" or owner == "Result") and name == "Ok" and kind == "result" {
            payload_types = [sem_types[subject].args[0]]
            valid = true
        } elif (owner == "" or owner == "Result") and name == "Err" and kind == "result" {
            payload_types = [sem_types[subject].args[1]]
            valid = true
        } elif kind == "enum" {
            if owner != "" and owner != sem_types[subject].name { sem_error("W2001", "pattern enum identity") }
            let generic = sem_generic_type(sem_types[subject].name)
            for i in 0..len(sem_variants) {
                if sem_variants[i] == name and sem_types[sem_variant_types[i]].name == sem_types[subject].name {
                    payload_types = sem_variant_payloads[i]
                    if generic >= 0 and len(sem_types[subject].args) == len(sem_generic_types[generic].params) {
                        let mut concrete: list[int] = []
                        for payload in payload_types { concrete.append(sem_substitute_type(payload, sem_generic_types[generic].params, sem_types[subject].args)) }
                        payload_types = concrete
                    }
                    valid = true
                }
            }
        }
        if not valid { sem_error("W2001", "payload pattern") }
        let mut count = 0
        if not sem_is("RPAREN") {
            if count >= len(payload_types) { sem_error("W2001", "too many enum pattern bindings") }
            sem_pattern(payload_types[count])
            count = count + 1
            while sem_match("COMMA") {
                if sem_is("RPAREN") { break }
                if count >= len(payload_types) { sem_error("W2001", "too many enum pattern bindings") }
                sem_pattern(payload_types[count])
                count = count + 1
            }
        }
        sem_expect("RPAREN")
        if count != len(payload_types) { sem_error("W2001", "enum pattern arity") }
        return name
    }
    if kind == "enum" {
        if owner != "" and owner != sem_types[subject].name { sem_error("W2001", "pattern enum identity") }
        let mut valid = false
        for i in 0..len(sem_variants) { if sem_variants[i] == name and sem_types[sem_variant_types[i]].name == sem_types[subject].name and len(sem_variant_payloads[i]) == 0 { valid = true } }
        if valid { return name }
        if owner != "" { sem_error("W1001", "unknown enum pattern") }
        sem_declare(name, subject, false)
        return "*"
    }
    if name == "None" and (kind == "optional" or owner == "Option") { return "None" }
    if owner != "" { sem_error("W2001", "qualified enum pattern required") }
    sem_declare(name, subject, false)
    return "*"
}
fn sem_match_expression() -> SemValue {
    sem_expect("MATCH")
    let subject = sem_expression(0, false).type_id
    sem_expect("LBRACE")
    let mut covered: list[str] = []
    let mut all_return = true
    let mut common = -1
    let mut wildcard = false
    let initial = sem_initialized
    let mut initialized = initial
    let mut live_branches = 0
    while not sem_is("RBRACE") {
        let saved_variables = sem_variables
        sem_initialized = initial
        sem_depth = sem_depth + 1
        let pattern = sem_pattern(subject)
        let mut guarded = false
        if sem_match("IF") { guarded = true sem_require(sem_expression(0, false).type_id, sem_bool, "W2001") }
        sem_expect("FAT_ARROW")
        let mut branch = SemFlow { type_id: sem_unit, terminates: false }
        if sem_is("LBRACE") { branch = sem_block(false) }
        else { let value = sem_expression(0, true) branch = SemFlow { type_id: value.type_id, terminates: value.terminates } }
        if not guarded {
            covered.append(pattern)
            if pattern == "*" { wildcard = true }
        }
        if not branch.terminates {
            if live_branches == 0 { initialized = sem_initialized } else { initialized = sem_intersect(initialized, sem_initialized) }
            live_branches = live_branches + 1
            if common >= 0 { sem_require(branch.type_id, common, "W2001") } else { common = branch.type_id }
        }
        all_return = all_return and branch.terminates
        sem_variables = saved_variables
        sem_depth = sem_depth - 1
        sem_match("COMMA")
    }
    sem_expect("RBRACE")
    if not wildcard and sem_kind(subject) == "enum" {
        for i in 0..len(sem_variants) {
            if sem_variant_types[i] == subject {
                let mut found = false
                for variant in covered { if variant == sem_variants[i] { found = true } }
                if not found { sem_error("W2003", "non-exhaustive match") }
            }
        }
    }
    if not wildcard {
        let kind = sem_kind(subject)
        let mut required: list[str] = []
        if kind == "bool" { required = ["literal:true", "literal:false"] }
        elif kind == "optional" { required = ["Some", "None"] }
        elif kind == "result" { required = ["Ok", "Err"] }
        elif kind == "error_union" {
            for alternative in sem_types[subject].args { required.append(sem_error_type_name(alternative)) }
        }
        elif kind != "enum" {
            if common >= 0 and common != sem_unit { sem_error("W2003", "value match requires exhaustive patterns") }
            if sem_expected >= 0 and sem_expected != sem_unit { sem_error("W2003", "value match requires exhaustive patterns") }
            initialized = sem_intersect(initialized, initial)
            all_return = false
        }
        for name in required { if not module_contains(covered, name) { sem_error("W2003", "non-exhaustive match") } }
    }
    sem_initialized = initialized
    if common < 0 { common = sem_unit }
    return SemValue { type_id: common, root: "", writable: -1, terminates: all_return }
}
fn sem_let() {
    sem_expect("LET")
    let mutable = sem_match("MUT")
    let name = sem_expect("IDENT").val
    let mut annotation = -1
    if sem_match("COLON") { annotation = sem_type() }
    sem_expect("ASSIGN")
    let previous = sem_expected
    sem_expected = annotation
    let expression_start = sem_pos + sem_token_offset
    let value = sem_expression(0, true).type_id
    sem_expected = previous
    sem_mark_result_lift(expression_start, value, annotation)
    if sem_kind(value) == "builtin" { sem_error("W2013", "builtin values require an explicit lambda adapter") }
    if annotation < 0 {
        if value == sem_none or sem_kind(value) == "empty" { sem_error("W2001", "initializer needs type context") }
        annotation = value
    } else { sem_require(value, annotation, "W2001") }
    sem_declare(name, annotation, mutable)
}
fn sem_block(statement: bool) -> SemFlow {
    sem_expect("LBRACE")
    let saved_variables = sem_variables
    sem_depth = sem_depth + 1
    let mut tail = sem_unit
    let mut terminates = false
    while not sem_is("RBRACE") and not sem_is("EOF") {
        if sem_is("LET") { sem_let() tail = sem_unit }
        elif sem_match("RETURN") {
            let previous = sem_expected
            sem_expected = sem_return
            let mut value = sem_unit
            if not sem_is("RBRACE") and sem_at().line == sem_tokens[sem_pos - 1].line {
                let expression_start = sem_pos + sem_token_offset
                value = sem_expression(0, true).type_id
                sem_mark_result_lift(expression_start, value, sem_return)
            }
            sem_expected = previous
            sem_require(value, sem_return, "W2004")
            sem_complete_constructor()
            terminates = true
            tail = sem_unit
        } elif sem_match("WHILE") {
            sem_require(sem_expression(0, false).type_id, sem_bool, "W2001")
            sem_loop = sem_loop + 1
            let initialized = sem_initialized
            sem_block(true)
            sem_initialized = initialized
            sem_loop = sem_loop - 1
            tail = sem_unit
        } elif sem_match("FOR") {
            let mut bindings: list[str] = [sem_expect("IDENT").val]
            while sem_match("COMMA") { bindings.append(sem_expect("IDENT").val) }
            sem_expect("IN")
            let iterable = sem_expression(0, false).type_id
            if sem_kind(iterable) != "list" { sem_error("W2001", "for requires list or range") }
            let element = sem_types[iterable].args[0]
            let variables = sem_variables
            sem_depth = sem_depth + 1
            if len(bindings) == 1 { sem_declare(bindings[0], element, false) }
            else {
                if sem_kind(element) != "tuple" or len(sem_types[element].args) != len(bindings) { sem_error("W2001", "for destructuring") }
                for i in 0..len(bindings) { sem_declare(bindings[i], sem_types[element].args[i], false) }
            }
            sem_loop = sem_loop + 1
            let initialized = sem_initialized
            sem_block(true)
            sem_initialized = initialized
            sem_loop = sem_loop - 1
            sem_depth = sem_depth - 1
            sem_variables = variables
            tail = sem_unit
        } elif sem_match("BREAK") or sem_match("CONTINUE") {
            if sem_loop == 0 { sem_error("W1004", "loop transfer outside loop") }
            tail = sem_unit
        } else {
            sem_statement_context = statement or not sem_tail_expression()
            let expression = sem_expression(0, true)
            tail = expression.type_id
            terminates = terminates or expression.terminates
        }
    }
    sem_expect("RBRACE")
    sem_depth = sem_depth - 1
    sem_variables = saved_variables
    return SemFlow { type_id: tail, terminates: terminates }
}
fn sem_check_function(function: SemFunction) {
    if function.body < 0 { return }
    let previous_position = sem_pos
    let variables = sem_variables
    let owner = sem_owner
    let returned = sem_return
    let current_function = sem_current_function
    let initial = sem_initializing
    let initialized = sem_initialized
    let depth = sem_depth
    let previous_type_params = sem_type_params
    let previous_constraints = sem_active_constraints
    sem_owner = function.owner
    sem_current_function = function.name
    sem_type_params = function.type_params
    sem_active_constraints = function.constraints
    if len(sem_owner) > 0 { sem_owner = slice(sem_owner, 0, len(sem_owner) - 1) }
    sem_pos = function.body
    sem_depth = 1
    let signature = sem_types[function.type_id].args
    sem_return = signature[len(signature) - 1]
    sem_initializing = sem_owner != "" and function.name == sem_owner + ".init"
    let empty: list[str] = []
    sem_initialized = empty
    for i in 0..len(function.params) { sem_declare(function.params[i], signature[i], false) }
    if sem_owner != "" { sem_declare("self", sem_named(sem_owner), false) }
    if sem_initializing {
        if sem_return != sem_unit { sem_error("W3004", "constructor must return unit") }
        let mut parent = ""
        for class_ in sem_classes { if class_.name == sem_owner { parent = class_.parent } }
        if parent != "" and sem_method(parent, "init") >= 0 {
            if sem_tokens[sem_pos + 1].kind != "SUPER" or sem_tokens[sem_pos + 2].kind != "DOT" or sem_tokens[sem_pos + 3].val != "init" { sem_error("W3004", "super.init must be first") }
        }
    }
    let flow = sem_block(sem_return == sem_unit)
    if sem_return != sem_unit and not flow.terminates { sem_require(flow.type_id, sem_return, "W2004") }
    sem_complete_constructor()
    sem_pos = previous_position
    sem_variables = variables
    sem_owner = owner
    sem_return = returned
    sem_current_function = current_function
    sem_initializing = initial
    sem_initialized = initialized
    sem_depth = depth
    sem_type_params = previous_type_params
    sem_active_constraints = previous_constraints
}
fn sem_check_generic_constraints(function_index: int, args: list[int], line: int, col: int) {
    let function = sem_functions[function_index]
    let signature = sem_types[function.type_id]
    let empty_names: list[str] = []
    let empty_types: list[int] = []
    sem_unify_names = empty_names
    sem_unify_types = empty_types
    for i in 0..len(args) { sem_unify_type(signature.args[i], args[i]) }
    if function.name == sem_current_function {
        for parameter in function.type_params {
            for i in 0..len(sem_unify_names) {
                if sem_unify_names[i] == parameter and sem_kind(sem_unify_types[i]) != "typeparam" and sem_contains_type_parameter(sem_unify_types[i], parameter) {
                    report_error("W2011", line, col, "structural generic expansion cycle detected: " + function.name)
                }
            }
        }
    }
    for i in 0..len(function.type_params) {
        let constraint = function.constraints[i]
        if constraint != "" {
            let mut concrete = -1
            for j in 0..len(sem_unify_names) { if sem_unify_names[j] == function.type_params[i] { concrete = sem_unify_types[j] } }
            if concrete < 0 or not sem_assignable(concrete, sem_named(constraint)) { report_error("W2001", line, col, "generic constraint not satisfied: " + constraint) }
        }
    }
}
fn sem_contains_type_parameter(type_id: int, name: str) -> bool {
    let type_ = sem_types[type_id]
    if type_.kind == "typeparam" { return type_.name == name }
    for argument in type_.args { if sem_contains_type_parameter(argument, name) { return true } }
    return false
}
fn sem_struct_reaches(current: str, target: str) -> bool {
    if current == target { return true }
    for seen in sem_layout_seen { if seen == current { return false } }
    sem_layout_seen.append(current)
    for field in sem_fields {
        if field.owner == current and sem_kind(field.type_id) == "struct" {
            if sem_struct_reaches(sem_types[field.type_id].name, target) { return true }
        }
    }
    return false
}
fn sem_validate_layout_cycles() {
    for field in sem_fields {
        let empty_seen: list[str] = []
        sem_layout_seen = empty_seen
        if sem_kind(field.type_id) == "struct" and sem_struct_reaches(sem_types[field.type_id].name, field.owner) {
            sem_error("W2011", "recursive inline struct layout detected: " + field.owner + " -> " + sem_types[field.type_id].name)
        }
    }
}
fn sem_reset(tokens: list[Token]) {
    sem_tokens = tokens
    sem_pos = 0
    sem_token_offset = 0
    sem_depth = 0
    sem_owner = ""
    sem_current_function = ""
    sem_loop = 0
    let empty_types: list[SemType] = []
    let empty_variables: list[SemVar] = []
    let empty_functions: list[SemFunction] = []
    let empty_fields: list[SemField] = []
    let empty_classes: list[SemClass] = []
    let empty_generic_types: list[SemGenericType] = []
    let empty_names: list[str] = []
    let empty_ids: list[int] = []
    sem_types = empty_types
    sem_type_params = empty_names
    sem_active_constraints = empty_names
    sem_layout_seen = empty_names
    sem_variables = empty_variables
    sem_functions = empty_functions
    sem_fields = empty_fields
    sem_classes = empty_classes
    sem_generic_types = empty_generic_types
    sem_variants = empty_names
    sem_variant_types = empty_ids
    let empty_payloads: list[list[int]] = []
    sem_variant_payloads = empty_payloads
    sem_indirect_positions = empty_ids
    sem_class_projection_positions = empty_ids
    sem_collection_call_positions = empty_ids
    sem_result_lift_positions = empty_ids
    sem_error_pattern_positions = empty_ids
    let empty_error_pattern_kinds: list[str] = []
    let empty_error_pattern_names: list[str] = []
    sem_error_pattern_kinds = empty_error_pattern_kinds
    sem_error_pattern_names = empty_error_pattern_names
    let empty_lambdas: list[SemLambda] = []
    sem_lambdas = empty_lambdas
    sem_capture_names = empty_names
    sem_capture_depth = -1
    sem_initializing = false
    sem_initialized = empty_names
    sem_int = sem_simple("int")
    sem_float = sem_simple("float")
    sem_bool = sem_simple("bool")
    sem_str = sem_simple("str")
    sem_unit = sem_simple("unit")
    sem_none = sem_simple("none")
    sem_simple("empty")
    sem_return = sem_unit
    let empty: list[int] = []
    sem_intern("struct", "IoError", empty)
    sem_intern("struct", "NetError", empty)
    sem_intern("opaque", "opaque", empty)
    sem_fields.append(SemField { owner: "IoError", name: "message", type_id: sem_str, visible: true })
    sem_fields.append(SemField { owner: "NetError", name: "message", type_id: sem_str, visible: true })
    for i in 0..len(tokens) - 1 {
        let kind = tokens[i].kind
        if kind == "STRUCT" or kind == "CLASS" or kind == "INTERFACE" or kind == "ENUM" {
            let name = tokens[i + 1].val
            let mut tag = "struct"
            if kind == "CLASS" { tag = "class" }
            if kind == "INTERFACE" { tag = "interface" }
            if kind == "ENUM" { tag = "enum" }
            for type_ in sem_types { if type_.name == name { report_error("W1002", tokens[i + 1].line, tokens[i + 1].col, "duplicate type") } }
            sem_intern(tag, name, empty)
            if tokens[i + 2].kind == "LBRACKET" {
                let mut params: list[str] = []
                let mut position = i + 3
                while position < len(tokens) and tokens[position].kind != "RBRACKET" {
                    let parameter = tokens[position]
                    if parameter.kind != "IDENT" { report_error("W0006", parameter.line, parameter.col, "expected generic type parameter") }
                    params.append(parameter.val)
                    position = position + 1
                    if position < len(tokens) and tokens[position].kind == "COLON" {
                        position = position + 1
                        if position >= len(tokens) or tokens[position].kind != "IDENT" { report_error("W0006", tokens[position - 1].line, tokens[position - 1].col, "expected generic constraint") }
                        position = position + 1
                    }
                    if position < len(tokens) and tokens[position].kind == "COMMA" { position = position + 1 }
                    elif position < len(tokens) and tokens[position].kind != "RBRACKET" { report_error("W0006", tokens[position].line, tokens[position].col, "expected ',' in generic parameters") }
                }
                if len(params) == 0 { report_error("W2001", tokens[i + 2].line, tokens[i + 2].col, "generic declaration requires a type parameter") }
                sem_generic_types.append(SemGenericType { name: name, kind: tag, params: params })
            }
        }
    }
}
fn sem_validate(tokens: list[Token]) {
    let mut surrounded: list[Token] = [Token { kind: "LBRACE", val: "{", line: 1, col: 1 }]
    for token in tokens {
        if token.kind != "EOF" { surrounded.append(token) }
    }
    surrounded.append(Token { kind: "RBRACE", val: "}", line: 1, col: 1 })
    surrounded.append(Token { kind: "EOF", val: "", line: 1, col: 1 })
    sem_reset(surrounded)
    sem_pos = 1
    while not sem_is("EOF") {
        sem_match("PUB")
        if sem_match("EXTERN") {
            if sem_expect("STR").val != "C" { sem_error("W2013", "only C ABI is supported") }
            sem_collect_function("", true)
            let signature = sem_types[sem_functions[len(sem_functions) - 1].type_id].args
            for i in 0..len(signature) {
                let kind = sem_kind(signature[i])
                if kind != "int" and kind != "float" and kind != "bool" and kind != "opaque" and not (i == len(signature) - 1 and kind == "unit") { sem_error("W2001", "FFI accepts only scalars and opaque handles") }
            }
        }
        elif sem_is("FN") and sem_tokens[sem_pos + 1].kind == "IDENT" { sem_collect_function("", true) }
        elif sem_is("STRUCT") { sem_collect_record("struct") }
        elif sem_is("CLASS") { sem_collect_record("class") }
        elif sem_is("INTERFACE") { sem_collect_record("interface") }
        elif sem_is("ENUM") { sem_collect_record("enum") }
        else { sem_take() }
    }
    sem_validate_inheritance()
    sem_validate_layout_cycles()
    sem_pos = 1
    while not sem_is("RBRACE") and not sem_is("EOF") {
        sem_match("PUB")
        let mut declaration = false
        for function in sem_functions {
            if function.body >= 0 and sem_pos < function.body and sem_is("FN") and sem_tokens[sem_pos + 1].val == function.name {
                sem_check_function(function)
                sem_pos = function.end
                declaration = true
                break
            }
        }
        if not declaration {
            if sem_match("EXTERN") {
                sem_expect("STR")
                sem_expect("FN")
                let name = sem_expect("IDENT").val
                let index = sem_function(name)
                sem_pos = sem_functions[index].end
            }
            elif sem_is("STRUCT") or sem_is("CLASS") or sem_is("INTERFACE") or sem_is("ENUM") {
                sem_take()
                while not sem_is("LBRACE") and not sem_is("EOF") { sem_take() }
                sem_skip_block()
            } elif sem_is("LET") { sem_let() }
            elif sem_is("FOR") or sem_is("WHILE") {
                let beginning = sem_pos
                while not sem_is("LBRACE") and not sem_is("EOF") { sem_take() }
                let end = sem_skip_block()
                let saved_tokens = sem_tokens
                let mut block: list[Token] = [Token { kind: "LBRACE", val: "{", line: sem_tokens[beginning].line, col: 1 }]
                for i in beginning..end { block.append(sem_tokens[i]) }
                block.append(Token { kind: "RBRACE", val: "}", line: 1, col: 1 })
                block.append(Token { kind: "EOF", val: "", line: 1, col: 1 })
                let previous_offset = sem_token_offset
                sem_token_offset = sem_token_offset + beginning - 1
                sem_tokens = block
                sem_pos = 0
                sem_block(true)
                sem_tokens = saved_tokens
                sem_token_offset = previous_offset
                sem_pos = end
            }
            elif sem_is("IMPORT") {
                # Checked-module identity and dependency linking remain an explicit capability boundary.
                sem_take()
                sem_expect("STR")
            } else { sem_statement_context = true sem_expression(0, true) }
        }
    }
    for function in sem_functions {
        if function.owner != "" { sem_check_function(function) }
    }
}

fn sem_lambda() -> SemValue {
    let position = sem_pos + sem_token_offset
    let token = sem_expect("PIPE")
    let expected = sem_expected
    let previous_variables = sem_variables
    let previous_depth = sem_depth
    let previous_return = sem_return
    let previous_loop = sem_loop
    let previous_captures = sem_capture_names
    let previous_capture_depth = sem_capture_depth
    sem_depth = sem_depth + 1
    sem_capture_depth = sem_depth
    let empty_names: list[str] = []
    sem_capture_names = empty_names
    let mut params: list[str] = []
    let mut types: list[int] = []
    while not sem_is("PIPE") {
        let name = sem_expect("IDENT").val
        let mut type_id = -1
        if sem_match("COLON") { type_id = sem_type() }
        elif expected >= 0 and sem_kind(expected) == "function" and len(params) + 1 < len(sem_types[expected].args) { type_id = sem_types[expected].args[len(params)] }
        else { sem_error("W2001", "lambda parameter needs type context") }
        params.append(name)
        types.append(type_id)
        sem_declare(name, type_id, false)
        if not sem_match("COMMA") { break }
    }
    sem_expect("PIPE")
    let mut returned = -1
    if sem_match("ARROW") { returned = sem_type() }
    elif expected >= 0 and sem_kind(expected) == "function" { returned = sem_types[expected].args[len(sem_types[expected].args) - 1] }
    sem_return = returned
    sem_loop = 0
    if sem_match("FAT_ARROW") {
        sem_expected = returned
        let actual = sem_expression(0, true).type_id
        if returned < 0 { returned = actual } else { sem_require(actual, returned, "W2004") }
    } else {
        if returned < 0 { sem_error("W2001", "block lambda needs return type context") }
        let flow = sem_block(sem_return == sem_unit)
        if returned != sem_unit and not flow.terminates { sem_require(flow.type_id, returned, "W2004") }
    }
    types.append(returned)
    let signature = sem_intern("function", "", types)
    if expected >= 0 { sem_require(signature, expected, "W2001") }
    let captures = sem_capture_names
    sem_lambdas.append(SemLambda { position: position, line: token.line, col: token.col, params: params, captures: captures, type_id: signature })
    sem_variables = previous_variables
    sem_depth = previous_depth
    sem_return = previous_return
    sem_loop = previous_loop
    sem_expected = expected
    sem_capture_names = previous_captures
    sem_capture_depth = previous_capture_depth
    for name in captures {
        let variable = sem_lookup(name)
        if variable >= 0 and sem_capture_depth >= 0 and sem_variables[variable].depth < sem_capture_depth and not module_contains(sem_capture_names, name) { sem_capture_names.append(name) }
    }
    return sem_value(signature)
}

fn sem_tail_expression() -> bool {
    let mut position = sem_pos
    let mut depth = 0
    while position < len(sem_tokens) {
        let kind = sem_tokens[position].kind
        if kind == "LBRACE" { depth = depth + 1 }
        elif kind == "RBRACE" {
            if depth == 0 { return true }
            depth = depth - 1
            if depth == 0 {
                let next = sem_tokens[position + 1].kind
                if next != "ELSE" and next != "ELIF" { return next == "RBRACE" }
            }
        }
        if depth == 0 and (kind == "LET" or kind == "RETURN") and position > sem_pos { return false }
        position = position + 1
    }
    return false
}
fn sem_compatible_override(actual: int, expected: int) -> bool {
    let a = sem_types[actual].args
    let b = sem_types[expected].args
    if len(a) != len(b) { return false }
    for i in 0..len(a) - 1 { if a[i] != b[i] { return false } }
    return sem_assignable(a[len(a) - 1], b[len(b) - 1])
}
fn sem_validate_inheritance() {
    for class_ in sem_classes {
        let mut current = class_.parent
        let mut visited: list[str] = [class_.name]
        while current != "" {
            if module_contains(visited, current) { sem_error("W3003", "inheritance cycle") }
            visited.append(current)
            if sem_kind(sem_named(current)) != "class" { sem_error("W3003", "base must be a class") }
            let mut next = ""
            for parent in sem_classes { if parent.name == current { next = parent.parent } }
            current = next
        }
        for field in sem_fields {
            if field.owner == class_.name and sem_field(class_.parent, field.name) >= 0 { sem_error("W3003", "inherited field cannot be redeclared") }
        }
        for method in sem_functions {
            if method.owner == class_.name + "." and method.name != class_.name + ".init" {
                let name = slice(method.name, len(method.owner), len(method.name))
                let inherited = sem_method(class_.parent, name)
                if inherited >= 0 {
                    let parent = sem_functions[inherited]
                    if not parent.visible or not method.visible { sem_error("W3002", "invalid override visibility") }
                    if not sem_compatible_override(method.type_id, parent.type_id) { sem_error("W3003", "incompatible override") }
                }
            }
        }
        for interface_ in class_.interfaces {
            if sem_kind(sem_named(interface_)) != "interface" { sem_error("W3003", "implements requires interface") }
            for requirement in sem_functions {
                if requirement.owner == interface_ + "." {
                    let name = slice(requirement.name, len(requirement.owner), len(requirement.name))
                    let implementation = sem_method(class_.name, name)
                    if implementation < 0 { sem_error("W3003", "missing interface method") }
                    let method = sem_functions[implementation]
                    if not method.visible or not sem_compatible_override(method.type_id, requirement.type_id) { sem_error("W3003", "incompatible interface implementation") }
                }
            }
        }
    }
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
    eprint("[W4003] W1 I/O error:", err.message)
    exit(1)
}
