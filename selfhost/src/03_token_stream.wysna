
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

fn expression_starter(kind: str) -> bool {
    return kind == "INT" or kind == "FLOAT" or kind == "STR" or kind == "TRUE" or kind == "FALSE" or kind == "NONE" or kind == "IDENT" or kind == "THIS" or kind == "SUPER" or kind == "NEW" or kind == "MINUS" or kind == "NOT" or kind == "LPAREN" or kind == "LBRACKET" or kind == "LBRACE" or kind == "PIPE" or kind == "IF" or kind == "MATCH"
}

