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
