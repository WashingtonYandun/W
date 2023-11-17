from enum import Enum
from Utils import iota


class Token(Enum):
    NUMBERS = iota()
    DATATYPE = iota()
    IDENTIFIER = iota()

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
