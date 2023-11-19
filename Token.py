from TokenType import TokenType


class Token:
    def __init__(self, value: object = None, type_: TokenType = None):
        self.value = value
        self.type = type_

    def __str__(self):
        return f"Token({self.value}, {self.type})"

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self.value == other.value and self.type == other.type

    def __ne__(self, other):
        return not self.__eq__(other)
