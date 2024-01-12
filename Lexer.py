from Constants import CONSTANTS
from Token import Token
from TokenType import TokenType
from Utils import is_skippable

# Constant lookup for keywords and known identifiers , datatypes and symbols.
KEYWORDS = {
    'num': TokenType.NUM_DATA_TYPE,
    'str': TokenType.STR_DATA_TYPE,
    'bool': TokenType.BOOL_DATA_TYPE,
    'null': TokenType.NULL_DATA_TYPE,

    'true': TokenType.BOOLEANS,
    'false': TokenType.BOOLEANS,
}


class Lexer:
    def __init__(self, code):
        self.code = code
        self.position = -1  # Inicializamos en -1 para que el primer avance coloque el índice en 0
        self.current_char = None
        self.advance()

    def advance(self):
        self.position += 1
        self.current_char = self.code[self.position] if self.position < len(self.code) else None

    def gen_number(self):
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

    def tokenize(self):
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

            elif self.current_char in CONSTANTS.OPERATORS.value:
                tokens.append(Token(self.current_char, TokenType.BINARY_OPERATOR))
                self.advance()

            elif self.current_char == "=":
                tokens.append(Token(self.current_char, TokenType.ASSIGNMENT_OPERATOR))
                self.advance()

            elif self.current_char.isalpha():
                ident = ""
                while self.current_char is not None and self.current_char.isalnum():
                    ident += self.current_char
                    self.advance()

                reserved = KEYWORDS.get(ident)
                tokens.append(Token(ident, reserved) if reserved else Token(ident, TokenType.IDENTIFIER))
            else:
                print(f"Unrecognized character found in source: {ord(self.current_char)}, {self.current_char}")
                raise ValueError("Tokenization error")

        tokens.append(Token(None, TokenType.EOF))

        return tokens
