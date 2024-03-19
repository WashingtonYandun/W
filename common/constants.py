from enum import Enum
from token.TokenType import TokenType

OPERATORS = ["+", "-", "*", "/", "%"]
KEYWORDS = {
    "def": TokenType.DEF,
    "None": TokenType.NONE,
    "true": TokenType.BOOLEANS,
    "false": TokenType.BOOLEANS,
    "else": TokenType.ELSE,
    "elif": TokenType.ELIF,
    "for": TokenType.FOR,
    "while": TokenType.WHILE,
    "if": TokenType.IF,
}
