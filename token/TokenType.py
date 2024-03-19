from enum import Enum
from common.utils import iota


class TokenType(Enum):
    """
    Enum class representing the different types of tokens in a programming language.
    """

    # Keywords
    NUM_DATA_TYPE = iota()
    STR_DATA_TYPE = iota()
    BOOL_DATA_TYPE = iota()
    NULL_DATA_TYPE = iota()
    LIST_DATA_TYPE = iota()

    NUMBERS = iota()
    STRINGS = iota()
    BOOLEANS = iota()
    NULL = iota()

    # Identifiers
    LET = iota()
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