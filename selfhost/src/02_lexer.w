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
