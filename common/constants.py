from enum import Enum
from token.TokenType import TokenType

OPERATORS = ["+", "-", "*", "/", "%"]
KEYWORDS = {
    "def": TokenType.DEF,
    "None": TokenType.NONE,
    "True": TokenType.BOOLEANS,
    "False": TokenType.BOOLEANS,
    "else": TokenType.ELSE,
    "elif": TokenType.ELIF,
    "for": TokenType.FOR,
    "while": TokenType.WHILE,
    "if": TokenType.IF,
}
