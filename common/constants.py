from enum import Enum
from token.TokenType import TokenType

OPERATORS = ["+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">="]

KEYWORDS = {
    "func": TokenType.FUNC,
    "return": TokenType.RETURN,
    "None": TokenType.NONE,
    "True": TokenType.BOOLEANS,
    "False": TokenType.BOOLEANS,

    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "elif": TokenType.ELIF,
    "for": TokenType.FOR,
    "in": TokenType.IN,
    "while": TokenType.WHILE,

    "int": TokenType.DATATYPE_INT,
    "str": TokenType.DATATYPE_STR,
    "bool": TokenType.DATATYPE_BOOL,
    "list": TokenType.DATATYPE_LIST,
    "const": TokenType.CONST,

    "=": TokenType.ASSIGNMENT_OPERATOR,
    
    ":": TokenType.COLON,
    "\n": TokenType.NEW_LINE,
    
    # List methods
    "append": TokenType.APPEND,
    "insert": TokenType.INSERT,
    "remove": TokenType.REMOVE,
    "pop": TokenType.POP,
    "clear": TokenType.CLEAR,
    "index": TokenType.INDEX,
    "count": TokenType.COUNT,
    "sort": TokenType.SORT,
    "reverse": TokenType.REVERSE,
    "extend": TokenType.EXTEND,
}
