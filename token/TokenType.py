from enum import Enum, auto

class TokenType(Enum):
    # 22 Reserved Keywords (SPEC v0.1)
    FN = auto()
    LET = auto()
    MUT = auto()
    STRUCT = auto()
    ENUM = auto()
    IMPORT = auto()

    IF = auto()
    ELIF = auto()
    ELSE = auto()
    FOR = auto()
    WHILE = auto()
    IN = auto()
    MATCH = auto()
    RETURN = auto()
    BREAK = auto()
    CONTINUE = auto()

    TRUE = auto()
    FALSE = auto()
    NONE = auto()

    AND = auto()
    OR = auto()
    NOT = auto()

    # Literals
    INT = auto()
    FLOAT = auto()
    STR = auto()
    IDENTIFIER = auto()

    # Arithmetic Operators
    PLUS = auto()              # +
    MINUS = auto()             # -
    STAR = auto()              # *
    SLASH = auto()             # /
    PERCENT = auto()           # %

    # Relational & Equality Operators
    ASSIGN = auto()            # =
    EQ = auto()                # ==
    NOT_EQ = auto()            # !=
    LT = auto()                # <
    LTE = auto()               # <=
    GT = auto()                # >
    GTE = auto()               # >=

    # Arrows
    ARROW = auto()             # ->
    FAT_ARROW = auto()         # =>

    # Ranges
    DOT_DOT = auto()           # ..
    DOT_DOT_EQ = auto()        # ..=

    # Optionals & Error Propagation
    QUESTION = auto()          # ?
    QUESTION_QUESTION = auto() # ??
    EXCLAMATION = auto()       # !

    # Punctuation & Delimiters
    DOT = auto()               # .
    COLON = auto()             # :
    COMMA = auto()             # ,
    LPAREN = auto()            # (
    RPAREN = auto()            # )
    LBRACE = auto()            # {
    RBRACE = auto()            # }
    LBRACKET = auto()          # [
    RBRACKET = auto()          # ]

    # Stream End
    EOF = auto()

    # Backward compatibility aliases for legacy parser (will be phased out)
    INTEGERS = INT
    FLOATS = FLOAT
    STRINGS = STR
    BOOLEANS = TRUE
    FUNC = FN
    CONST = LET
    LEFT_PR = LPAREN
    RIGHT_PR = RPAREN
    LEFT_BR = LBRACKET
    RIGHT_BR = RBRACKET
    LEFT_CBR = LBRACE
    RIGHT_CBR = RBRACE
    BINARY_OPERATOR = PLUS
    COMPARISON_OPERATOR = EQ
    ASSIGNMENT_OPERATOR = ASSIGN
    NEW_LINE = auto()
    DATATYPE_INT = IDENTIFIER
    DATATYPE_FLOAT = IDENTIFIER
    DATATYPE_STR = IDENTIFIER
    DATATYPE_BOOL = IDENTIFIER
    DATATYPE_LIST = IDENTIFIER
    DATATYPE_DICT = IDENTIFIER
    IS = EQ