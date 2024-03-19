from common.constants import OPERATORS, KEYWORDS
from common.utils import is_skippable
from token.Token import Token
from token.TokenType import TokenType
from common.Error import Error
    

class LexerError(Error):
    def __init__(self, details: str) -> None:
        super().__init__("Lexer Error", details)


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
                raise Exception(f"Illegal char '{self.current_char}'")

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
    

    def tokenize(self) -> list[Token]:
        tokens = []

        while self.current_char is not None:
            if is_skippable(self.current_char):
                self.advance()

            elif self.current_char.isdigit() or (self.current_char == '.' and self.code[self.position + 1].isdigit()):
                tokens.append(self.gen_number())

            elif self.current_char == "(":
                tokens.append(Token(self.current_char, TokenType.LEFT_PR))
                self.advance()
            elif self.current_char == ")":
                tokens.append(Token(self.current_char, TokenType.RIGHT_PR))
                self.advance()
            elif self.current_char == "[":
                tokens.append(Token(self.current_char, TokenType.LEFT_BR))
                self.advance()
            elif self.current_char == "]":
                tokens.append(Token(self.current_char, TokenType.RIGHT_BR))
                self.advance()
            elif self.current_char == "{":
                tokens.append(Token(self.current_char, TokenType.LEFT_CBR))
                self.advance()
            elif self.current_char == "}":
                tokens.append(Token(self.current_char, TokenType.RIGHT_CBR))
                self.advance()

            elif self.current_char in OPERATORS:
                tokens.append(Token(self.current_char, TokenType.BINARY_OPERATOR))
                self.advance()

            elif self.current_char == "=":
                if self.code[self.position + 1] == "=":
                    tokens.append(Token("==", TokenType.EQUALS))
                    self.advance()
                    self.advance()
                else:
                    tokens.append(Token(self.current_char, TokenType.ASSIGNMENT_OPERATOR))
                    self.advance()
                
            elif self.current_char == '"':
                tokens.append(self.gen_string())

            elif self.current_char.isalpha():
                ident = ""
                while self.current_char is not None and self.current_char.isalnum():
                    ident += self.current_char
                    self.advance()

                reserved = KEYWORDS.get(ident)
                tokens.append(Token(ident, reserved) if reserved else Token(ident, TokenType.IDENTIFIER))
            else:
                raise LexerError(f"Invalid character '{self.current_char}'")

        tokens.append(Token(None, TokenType.EOF))
        return tokens
