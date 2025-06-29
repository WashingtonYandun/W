from enum import Enum
from token.TokenType import TokenType

OPERATORS = ["+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">=", "and", "or", "not", "is"]

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
    "dict": TokenType.DATATYPE_DICT,
    "const": TokenType.CONST,
    
    # Logical operators
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "is": TokenType.IS,

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
    
    # Dict methods
    "get": TokenType.GET,
    "keys": TokenType.KEYS,
    "values": TokenType.VALUES,
    "items": TokenType.ITEMS,
    "update": TokenType.UPDATE,
}
