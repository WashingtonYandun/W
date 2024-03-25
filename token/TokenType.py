from enum import Enum
from common.Utils import iota


class TokenType(Enum):
    """
    Enum class representing the different types of tokens in a programming language.
    """
    # Data types
    NUMBERS = iota()
    STRINGS = iota()
    BOOLEANS = iota()
    LISTS = iota()
    TUPLES = iota()
    NONE = iota()
    COLON = iota()

    # Reserved keywords for datatypes
    CONST_DATA = iota()
    DATATYPE_NUM = iota()
    DATATYPE_STR = iota()
    DATATYPE_BOOL = iota()

    # Identifiers
    IDENTIFIER = iota()
    ASSIGNMENT_OPERATOR = iota()

    # Control flow
    IF = iota()
    ELSE = iota()
    ELIF = iota()
    DEF = iota()

    # Loops
    FOR = iota()
    WHILE = iota()

    # Grouping & Operators
    BINARY_OPERATOR = iota()
    EQUALS = iota()

    # Syntax
    LEFT_PR = iota()
    RIGHT_PR = iota()

    LEFT_BR = iota()
    RIGHT_BR = iota()

    LEFT_CBR = iota()
    RIGHT_CBR = iota()

    # End of file
    EOF = iota()

    # New line
    NEW_LINE = iota()
    