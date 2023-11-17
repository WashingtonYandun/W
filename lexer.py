# Returns a token of a given type and value
from Token import Token


def create_token(value: object = None, _type: object = None) -> Token:
    return Token(value, _type)


def is_skippable(char: str) -> bool:
    return char == " " or char == "\n" or char == "\t"


def is_int(char: str) -> bool:
    return char.isdigit()


def is_alpha(src: str) -> bool:
    return src.upper() != src.lower()
