from enum import Enum
from token.TokenType import TokenType

OPERATORS = ["+", "-", "*", "/", "%"]
KEYWORDS = {
    "def": TokenType.DEF,
    "None": TokenType.NONE,
    "True": TokenType.BOOLEANS,
    "False": TokenType.BOOLEANS,

    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "elif": TokenType.ELIF,
    "for": TokenType.FOR,
    "while": TokenType.WHILE,

    "num": TokenType.DATATYPE_NUM,
    "str": TokenType.DATATYPE_STR,
    "bool": TokenType.DATATYPE_BOOL,
    "const": TokenType.CONST_DATA,

    "=": TokenType.ASSIGNMENT_OPERATOR,
    
    ":": TokenType.COLON,
    "\n": TokenType.NEW_LINE,
}
