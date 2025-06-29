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
    CONST = iota()
    FUNC = iota()
    RETURN = iota()
    DATATYPE_INT = iota()
    DATATYPE_STR = iota()
    DATATYPE_BOOL = iota()
    DATATYPE_LIST = iota()

    # Identifiers
    IDENTIFIER = iota()
    ASSIGNMENT_OPERATOR = iota()

    # Control flow
    IF = iota()
    ELSE = iota()
    ELIF = iota()

    # Loops
    FOR = iota()
    WHILE = iota()
    IN = iota()

    # Grouping & Operators
    BINARY_OPERATOR = iota()
    COMPARISON_OPERATOR = iota()
    EQUALS = iota()

    # Syntax
    LEFT_PR = iota()
    RIGHT_PR = iota()
    LEFT_BR = iota()
    RIGHT_BR = iota()
    LEFT_CBR = iota()
    RIGHT_CBR = iota()
    
    # Arrow for function return types
    ARROW = iota()            # ->

    # End of file
    EOF = iota()
    NEW_LINE = iota()
    
    # Comma
    COMMA = iota()
    
    # Dot operator for method calls
    DOT = iota()
    
    # List methods
    APPEND = iota()
    INSERT = iota()
    REMOVE = iota()
    POP = iota()
    CLEAR = iota()
    INDEX = iota()
    COUNT = iota()
    SORT = iota()
    REVERSE = iota()
    EXTEND = iota()
    