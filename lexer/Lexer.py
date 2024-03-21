from common.constants import OPERATORS, KEYWORDS
from common.Utils import is_skippable
from token.Token import Token
from token.TokenType import TokenType
from error.Error import LexerError

class Lexer():
    def __init__(self, code: str) -> None:
        self.code = code
        self.position = -1
        self.current_char = None
        self.advance()

    def advance(self) -> None:
        self.position += 1
        self.current_char = self.code[self.position] if self.position < len(self.code) else None

    def gen_number(self) -> Token:
        decimal_counter = 0
        num_str = self.current_char

        self.advance()

        while self.current_char is not None and (self.current_char == '.' or self.current_char.isdigit()):
            if decimal_counter > 1:
                raise LexerError(f"Illegal character '{self.current_char}'")

            if self.current_char == '.':
                decimal_counter += 1

            num_str += self.current_char
            self.advance()

        if num_str.startswith("."):
            num_str = "0" + num_str

        if num_str.endswith("."):
            num_str += "0"

        return Token(value=float(num_str), type_=TokenType.NUMBERS)

    def gen_string(self) -> Token:
        string = ""
        self.advance()

        while self.current_char is not None and self.current_char != '"':
            string += str(self.current_char)
            self.advance()
        self.advance()

        return Token(value=string, type_=TokenType.STRINGS)
    
    def gen_identifier(self) -> Token:
        ident = ""
        while self.current_char is not None and self.current_char.isalnum():
            ident += self.current_char
            self.advance()

        reserved = KEYWORDS.get(ident)
        return Token(ident, reserved) if reserved else Token(ident, TokenType.IDENTIFIER)

    def handle_equals(self) -> Token:
        if self.code[self.position + 1] == '=':
            self.advance()
            return Token("==", TokenType.EQUALS)
        else:
            return Token(self.current_char, TokenType.ASSIGNMENT_OPERATOR)

    def handle_brackets(self) -> Token:
        bracket_type = {
            '(': TokenType.LEFT_PR,
            ')': TokenType.RIGHT_PR,
            '[': TokenType.LEFT_BR,
            ']': TokenType.RIGHT_BR,
            '{': TokenType.LEFT_CBR,
            '}': TokenType.RIGHT_CBR
        }
        token_type = bracket_type[self.current_char]
        self.advance()
        return Token(self.current_char, token_type)

    def tokenize(self) -> list[Token]:
        tokens = []

        while self.current_char is not None:
            if is_skippable(self.current_char):
                self.advance()
            elif self.current_char.isdigit() or (self.current_char == '.' and self.code[self.position + 1].isdigit()):
                tokens.append(self.gen_number())
            elif self.current_char == '"':
                tokens.append(self.gen_string())
            elif self.current_char in OPERATORS:
                tokens.append(Token(self.current_char, TokenType.BINARY_OPERATOR))
                self.advance()
            elif self.current_char.isalpha():
                tokens.append(self.gen_identifier())
            elif self.current_char == '=':
                tokens.append(self.handle_equals())
            elif self.current_char in '()[]{}':
                tokens.append(self.handle_brackets())
            else:
                raise LexerError(f"Invalid character '{self.current_char}'")

        tokens.append(Token(None, TokenType.EOF))
        return tokens