from token.TokenType import TokenType


class Token:
    def __init__(self, value: object = None, type_: TokenType = None):
        self.value = value
        self.type = type_

    def __str__(self) -> str:
        return f"Token({self.value}, {self.type})"

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other) -> bool:
        return self.value == other.value and self.type == other.type

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)
