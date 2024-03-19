from typing import Union

# Possible node types
NodeType = Union["Program", "NumericLiteral", "Identifier", "BinaryExpr"]


class Statement:
    def __init__(self, kind: NodeType):
        self.kind = kind

    # method to show the data of the node
    def __repr__(self):
        return f"{self.__dict__}"


class Program(Statement):
    def __init__(self, body: list[Statement] = []):
        super().__init__("Program")

        self.kind = "Program"
        self.body = body


class Expr(Statement):
    pass

class BinaryExpr(Expr):
    def __init__(self, left: Expr, right: Expr, operator: str):
        super().__init__("BinaryExpr")

        self.kind = "BinaryExpr"
        self.left = left
        self.right = right
        self.operator = operator


class Identifier(Expr):
    def __init__(self, symbol: str):
        super().__init__("Identifier")

        self.kind = "Identifier"
        self.symbol = symbol


class NumericLiteral(Expr):
    def __init__(self, value: float):
        super().__init__("NumericLiteral")

        self.kind = "NumericLiteral"
        self.value = value
