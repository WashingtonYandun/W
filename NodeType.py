from typing import Union

# Possible node types
NodeType = Union["Program", "NumericLiteral", "Identifier", "BinaryExpr"]


# (Statements)
class Statements:
    def __init__(self, kind: NodeType):
        self.kind = kind


class Program(Statements):
    def __init__(self, body: list[Statements]):
        super().__init__("Program")
        self.body = body


# Define la interfaz para expresiones
class Expr(Statements):
    pass


# Define la interfaz para expresiones binarias
class BinaryExpr(Expr):
    def __init__(self, left: Expr, right: Expr, operator: str):
        super().__init__("BinaryExpr")
        self.left = left
        self.right = right
        self.operator = operator


# Define los tipos de expresiones literales/primarias
class Identifier(Expr):
    def __init__(self, symbol: str):
        super().__init__("Identifier")
        self.symbol = symbol


class NumericLiteral(Expr):
    def __init__(self, value: float):
        super().__init__("NumericLiteral")
        self.value = value
