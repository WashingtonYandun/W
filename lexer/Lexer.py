from tokens.Token import Token
from tokens.TokenType import TokenType
from common.constants import KEYWORDS
from error.Error import LexerError
from typing import List, Optional

# Tokens that can end an expression. A '-' immediately after one of these is
# binary subtraction; anywhere else it is prefix negation.
_VALUE_END_TOKENS = frozenset({
    TokenType.INT, TokenType.FLOAT, TokenType.STR,
    TokenType.TRUE, TokenType.FALSE, TokenType.NONE,
    TokenType.IDENTIFIER, TokenType.THIS, TokenType.SUPER,
    TokenType.RPAREN, TokenType.RBRACKET, TokenType.RBRACE,
})

class Lexer:
    """
    Lexical analyzer for Wysna conforming to SPEC.md v0.1.
    
    Transforms UTF-8 source text into a stream of typed tokens with 1-based line/col positions.
    Never calls exit(); raises LexerError with structured location diagnostics.
    """
    def __init__(self, source: str, file: str = "<stdin>") -> None:
        self.source = source
        self.file = file
        self.length = len(source)
        self.pos = 0
        self.line = 1
        self.col = 1

    def peek(self, offset: int = 0) -> Optional[str]:
        idx = self.pos + offset
        if idx < self.length:
            return self.source[idx]
        return None

    def advance(self) -> Optional[str]:
        if self.pos >= self.length:
            return None
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []

        while self.pos < self.length:
            ch = self.peek()

            # Whitespace handling
            if ch in (' ', '\t', '\r', '\n'):
                self.advance()
                continue

            # Comments: skip until newline or EOF
            if ch == '#':
                while self.peek() is not None and self.peek() != '\n':
                    self.advance()
                continue

            token_start = self.pos
            start_line = self.line
            start_col = self.col

            # Reject leading dot float, e.g. '.5'
            if ch == '.' and self.peek(1) is not None and self.peek(1).isascii() and self.peek(1).isdigit():
                raise LexerError(
                    message="Float literals must have leading digits before decimal point",
                    line=start_line,
                    col=start_col,
                    file=self.file,
                    code="W0002"
                )

            # Negative integer literals. `-9223372036854775808` is representable as
            # int64 but its magnitude is not, so the sign has to be part of the
            # literal when the minus is in prefix position. Deciding on the previous
            # token (rather than on a later parser look-back) keeps this correct for
            # binary subtraction: in `0 - 9223372036854775808` the minus follows a
            # value, so the literal is rejected as out of range.
            if (ch == '-' and self._minus_is_prefix(tokens)
                    and self.peek(1) is not None and self.peek(1).isascii() and self.peek(1).isdigit()):
                self.advance()  # consume '-'
                tokens.append(self._lex_number(start_line, start_col, negated=True))
                tokens[-1].value = -tokens[-1].value
                tokens[-1].start_offset = token_start
                self._stamp(tokens[-1], token_start)
                continue

            # Numbers (Integers & Floats)
            if ch.isascii() and ch.isdigit():
                tokens.append(self._lex_number(start_line, start_col))
                self._stamp(tokens[-1], token_start)
                continue

            # Strings
            if ch == '"':
                tokens.append(self._lex_string(start_line, start_col))
                self._stamp(tokens[-1], token_start)
                continue

            # Identifiers and Keywords
            if (ch.isascii() and ch.isalpha()) or ch == '_':
                tokens.append(self._lex_identifier(start_line, start_col))
                self._stamp(tokens[-1], token_start)
                continue

            # Multi-character & single-character operators
            tokens.append(self._lex_operator(start_line, start_col))
            self._stamp(tokens[-1], token_start)

        # Append EOF token
        tokens.append(Token(value=None, type=TokenType.EOF, line=self.line, col=self.col))
        return tokens

    def _minus_is_prefix(self, tokens: List[Token]) -> bool:
        """True when a '-' at the current position negates rather than subtracts.

        A minus is prefix when nothing can end an expression precedes it: the start
        of the file, or any token that is not a literal, identifier, `)` or `]`.
        """
        if not tokens:
            return True
        return tokens[-1].type not in _VALUE_END_TOKENS

    def _stamp(self, token, start):
        token.start_offset = start
        token.end_offset = self.pos
        token.end_line = self.line
        token.end_col = self.col

    def _lex_number(self, start_line: int, start_col: int, negated: bool = False) -> Token:
        num_str = ""
        is_float = False
        prev_was_underscore = False

        while self.peek() is not None:
            c = self.peek()

            if c.isascii() and c.isdigit():
                num_str += c
                self.advance()
                prev_was_underscore = False

            elif c == '_':
                if prev_was_underscore:
                    raise LexerError(
                        message="Consecutive underscores in numeric literal are not allowed",
                        line=self.line,
                        col=self.col,
                        file=self.file,
                        code="W0002"
                    )
                # Next char must be digit or '.'
                nxt = self.peek(1)
                if nxt is None or not ((nxt.isascii() and nxt.isdigit()) or nxt == '.'):
                    raise LexerError(
                        message="Invalid numeric separator placement",
                        line=self.line,
                        col=self.col,
                        file=self.file,
                        code="W0002"
                    )
                num_str += c
                self.advance()
                prev_was_underscore = True

            elif c == '.':
                # Range check: if '..' or '..=', this is a range operator, not a float point
                if self.peek(1) == '.':
                    break

                # If we already have a decimal point, stop or error
                if is_float:
                    break

                # Must be followed by a digit: e.g. '12.34'
                nxt = self.peek(1)
                if nxt is None or not (nxt.isascii() and nxt.isdigit()):
                    raise LexerError(
                        message="Trailing decimal point in float literal is not allowed",
                        line=self.line,
                        col=self.col,
                        file=self.file,
                        code="W0002"
                    )

                if prev_was_underscore:
                    raise LexerError(
                        message="Numeric separator cannot precede decimal point",
                        line=self.line,
                        col=self.col,
                        file=self.file,
                        code="W0002"
                    )

                is_float = True
                num_str += c
                self.advance()
                prev_was_underscore = False

            else:
                break

        if prev_was_underscore:
            raise LexerError(
                message="Trailing underscore in numeric literal is not allowed",
                line=start_line,
                col=start_col,
                file=self.file,
                code="W0002"
            )

        clean_str = num_str.replace("_", "")

        # A literal immediately followed by an identifier character is malformed:
        # W has no hex, binary, octal or exponent notation, so `0x10` and `1e5` used
        # to lex as `0`/`1` plus the identifiers `x10`/`e5`, which surfaced later as a
        # bogus "unknown identifier" instead of a numeric-literal error.
        trailing = self.peek()
        if trailing is not None and ((trailing.isascii() and trailing.isalnum()) or trailing == '_'):
            raise LexerError(
                message=f"Malformed numeric literal '{num_str}{trailing}'",
                line=start_line,
                col=start_col,
                file=self.file,
                code="W0002",
            )
        try:
            if is_float:
                value = float(clean_str)
                if value in (float("inf"), float("-inf")) and "inf" not in clean_str.lower():
                    raise ValueError("Floating-point literal overflows binary64")
                return Token(value=value, type=TokenType.FLOAT, line=start_line, col=start_col)
            else:
                if len(clean_str) > 20:
                    raise ValueError("Integer literal exceeds 64-bit range")
                ival = int(clean_str)
                # A negated literal may reach 2^63, which int64 can represent as
                # INT64_MIN even though its magnitude is not representable.
                limit = 9223372036854775808 if negated else 9223372036854775807
                if ival > limit:
                    raise ValueError("Integer literal exceeds 64-bit range")
                return Token(value=ival, type=TokenType.INT, line=start_line, col=start_col)
        except (ValueError, OverflowError):
            raise LexerError(
                message=f"Malformed or out-of-range numeric literal '{num_str}'",
                line=start_line,
                col=start_col,
                file=self.file,
                code="W0002",
            )

    def _lex_string(self, start_line: int, start_col: int) -> Token:
        # Consume opening quote
        self.advance()
        val = ""

        while True:
            ch = self.peek()

            if ch is None:
                raise LexerError(
                    message="Unterminated string literal at end of file",
                    line=start_line,
                    col=start_col,
                    file=self.file,
                    code="W0003"
                )

            if ch == '\n':
                raise LexerError(
                    message="Unterminated string literal (newline in single-line string)",
                    line=start_line,
                    col=start_col,
                    file=self.file,
                    code="W0003"
                )

            if ch == '"':
                # Consume closing quote
                self.advance()
                break

            if ch == '\\':
                self.advance()  # consume '\'
                esc = self.peek()
                if esc is None:
                    raise LexerError(
                        message="Unterminated string escape at end of file",
                        line=start_line,
                        col=start_col,
                        file=self.file,
                        code="W0004"
                    )

                if esc == 'n':
                    val += '\n'
                    self.advance()
                elif esc == 'r':
                    val += '\r'
                    self.advance()
                elif esc == 't':
                    val += '\t'
                    self.advance()
                elif esc == '\\':
                    val += '\\'
                    self.advance()
                elif esc == '"':
                    val += '"'
                    self.advance()
                elif esc == '0':
                    val += '\0'
                    self.advance()
                elif esc == 'u':
                    self.advance()  # consume 'u'
                    val += self._lex_unicode_escape(start_line, start_col)
                else:
                    raise LexerError(
                        message=f"Invalid escape sequence '\\{esc}'",
                        line=self.line,
                        col=self.col,
                        file=self.file,
                        code="W0004"
                    )
            else:
                val += ch
                self.advance()

        return Token(value=val, type=TokenType.STR, line=start_line, col=start_col)

    def _lex_unicode_escape(self, start_line: int, start_col: int) -> str:
        if self.peek() != '{':
            raise LexerError(
                message="Expected '{' after '\\u'",
                line=self.line,
                col=self.col,
                file=self.file,
                code="W0005"
            )
        self.advance()  # consume '{'

        hex_str = ""
        while self.peek() is not None and self.peek() != '}':
            ch = self.peek()
            if ch in "0123456789abcdefABCDEF":
                hex_str += ch
                self.advance()
            else:
                raise LexerError(
                    message=f"Invalid character '{ch}' in Unicode escape sequence",
                    line=self.line,
                    col=self.col,
                    file=self.file,
                    code="W0005"
                )

        if self.peek() != '}':
            raise LexerError(
                message="Unterminated Unicode escape sequence, expected '}'",
                line=self.line,
                col=self.col,
                file=self.file,
                code="W0005"
            )
        self.advance()  # consume '}'

        if len(hex_str) == 0 or len(hex_str) > 6:
            raise LexerError(
                message="Unicode escape sequence must contain between 1 and 6 hex digits",
                line=start_line,
                col=start_col,
                file=self.file,
                code="W0005"
            )

        code_point = int(hex_str, 16)
        # Valid Unicode scalar values: 0x0 to 0x10FFFF excluding surrogates (0xD800 to 0xDFFF)
        if code_point > 0x10FFFF or (0xD800 <= code_point <= 0xDFFF):
            raise LexerError(
                message=f"Invalid Unicode code point '0x{hex_str}'",
                line=start_line,
                col=start_col,
                file=self.file,
                code="W0005"
            )

        return chr(code_point)

    def _lex_identifier(self, start_line: int, start_col: int) -> Token:
        ident = ""
        while self.peek() is not None and ((self.peek().isascii() and self.peek().isalnum()) or self.peek() == '_'):
            ident += self.peek()
            self.advance()

        # Check if keyword
        if ident in KEYWORDS:
            kw_type = KEYWORDS[ident]
            if kw_type == TokenType.TRUE:
                return Token(value=True, type=TokenType.TRUE, line=start_line, col=start_col)
            elif kw_type == TokenType.FALSE:
                return Token(value=False, type=TokenType.FALSE, line=start_line, col=start_col)
            elif kw_type == TokenType.NONE:
                return Token(value=None, type=TokenType.NONE, line=start_line, col=start_col)
            else:
                return Token(value=ident, type=kw_type, line=start_line, col=start_col)

        return Token(value=ident, type=TokenType.IDENTIFIER, line=start_line, col=start_col)

    def _lex_operator(self, start_line: int, start_col: int) -> Token:
        ch = self.peek()

        # Check two / three character sequences first
        if ch == '?':
            self.advance()
            if self.peek() == '?':
                self.advance()
                return Token(value="??", type=TokenType.QUESTION_QUESTION, line=start_line, col=start_col)
            return Token(value="?", type=TokenType.QUESTION, line=start_line, col=start_col)

        if ch == '.':
            self.advance()
            if self.peek() == '.':
                self.advance()
                if self.peek() == '=':
                    self.advance()
                    return Token(value="..=", type=TokenType.DOT_DOT_EQ, line=start_line, col=start_col)
                return Token(value="..", type=TokenType.DOT_DOT, line=start_line, col=start_col)
            return Token(value=".", type=TokenType.DOT, line=start_line, col=start_col)

        if ch == '=':
            self.advance()
            if self.peek() == '=':
                self.advance()
                return Token(value="==", type=TokenType.EQ, line=start_line, col=start_col)
            if self.peek() == '>':
                self.advance()
                return Token(value="=>", type=TokenType.FAT_ARROW, line=start_line, col=start_col)
            return Token(value="=", type=TokenType.ASSIGN, line=start_line, col=start_col)

        if ch == '!':
            self.advance()
            if self.peek() == '=':
                self.advance()
                return Token(value="!=", type=TokenType.NOT_EQ, line=start_line, col=start_col)
            return Token(value="!", type=TokenType.EXCLAMATION, line=start_line, col=start_col)

        if ch == '<':
            self.advance()
            if self.peek() == '=':
                self.advance()
                return Token(value="<=", type=TokenType.LTE, line=start_line, col=start_col)
            return Token(value="<", type=TokenType.LT, line=start_line, col=start_col)

        if ch == '>':
            self.advance()
            if self.peek() == '=':
                self.advance()
                return Token(value=">=", type=TokenType.GTE, line=start_line, col=start_col)
            return Token(value=">", type=TokenType.GT, line=start_line, col=start_col)

        if ch == '-':
            self.advance()
            if self.peek() == '>':
                self.advance()
                return Token(value="->", type=TokenType.ARROW, line=start_line, col=start_col)
            return Token(value="-", type=TokenType.MINUS, line=start_line, col=start_col)

        # Single character operators & delimiters
        single_ops = {
            '|': TokenType.PIPE,
            '+': TokenType.PLUS,
            '*': TokenType.STAR,
            '/': TokenType.SLASH,
            '%': TokenType.PERCENT,
            ':': TokenType.COLON,
            ',': TokenType.COMMA,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            '{': TokenType.LBRACE,
            '}': TokenType.RBRACE,
            '[': TokenType.LBRACKET,
            ']': TokenType.RBRACKET,
        }

        if ch in single_ops:
            op_type = single_ops[ch]
            self.advance()
            return Token(value=ch, type=op_type, line=start_line, col=start_col)

        # Unrecognized character
        self.advance()
        raise LexerError(
            message=f"Unexpected character '{ch}'",
            line=start_line,
            col=start_col,
            file=self.file,
            code="W0001"
        )