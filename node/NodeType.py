from typing import Union

NodeType = Union[
    "Program", 
    "Statement",
    "Expr", 
    "Identifier", 
    "VarDeclaration",
    "NumericLiteral", 
    "NoneLiteral",
    "StringLiteral", 
    "BooleanLiteral",
    "ListLiteral",
    "IndexExpr",
    "BinaryExpr",
    "IfStatement",
    "WhileStatement",
    "ForStatement",
    "FunctionDeclaration",
    "CallExpr",
    "AssignmentExpr",
    "ReturnStatement",
    "MethodCallExpr"
    ]


class Statement:
    def __init__(self, kind: NodeType):
        self.kind = kind

    def __repr__(self):
        return f"{self.__dict__}"


class Program(Statement):
    def __init__(self, body: list[Statement] = None):
        super().__init__("Program")

        self.kind = "Program"
        self.body = body if body is not None else []


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


class VarDeclaration(Statement):
    def __init__(self, identifier: Identifier, value: Expr, const: bool, datatype: str):
        super().__init__("VarDeclaration")

        self.kind = "VarDeclaration"
        self.constant = const
        self.identifier = identifier
        self.datatype = datatype
        self.initializer = value


class NumericLiteral(Expr):
    def __init__(self, value: float):
        super().__init__("NumericLiteral")

        self.kind = "NumericLiteral"
        self.value = value


class NoneLiteral(Expr):
    def __init__(self):
        super().__init__("NoneLiteral")

        self.kind = "NoneLiteral"
        self.value = "None"
    

class StringLiteral(Expr):
    def __init__(self, value: str):
        super().__init__("StringLiteral")

        self.kind = "StringLiteral"
        self.value = value


class BooleanLiteral(Expr):
    def __init__(self, value: bool):
        super().__init__("BooleanLiteral")

        self.kind = "BooleanLiteral"
        self.value = value


class IfStatement(Statement):
    def __init__(self, condition: Expr, then_body: list[Statement], else_body: list[Statement] = None):
        super().__init__("IfStatement")
        
        self.kind = "IfStatement"
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body if else_body is not None else []


class WhileStatement(Statement):
    def __init__(self, condition: Expr, body: list[Statement]):
        super().__init__("WhileStatement")
        
        self.kind = "WhileStatement"
        self.condition = condition
        self.body = body


class ForStatement(Statement):
    def __init__(self, variable: str, iterable: Expr, body: list[Statement]):
        super().__init__("ForStatement")
        
        self.kind = "ForStatement"
        self.variable = variable
        self.iterable = iterable
        self.body = body


class FunctionDeclaration(Statement):
    def __init__(self, name: str, parameters: list[tuple[str, str]], body: list[Statement], return_type: str = "None"):
        super().__init__("FunctionDeclaration")
        
        self.kind = "FunctionDeclaration"
        self.name = name
        self.parameters = parameters  # List of (param_name, param_type) tuples
        self.body = body
        self.return_type = return_type


class CallExpr(Expr):
    def __init__(self, callee: Expr, arguments: list[Expr]):
        super().__init__("CallExpr")
        
        self.kind = "CallExpr"
        self.callee = callee
        self.arguments = arguments


class AssignmentExpr(Expr):
    def __init__(self, assignee: Identifier, value: Expr):
        super().__init__("AssignmentExpr")
        
        self.kind = "AssignmentExpr"
        self.assignee = assignee
        self.value = value


class ListLiteral(Expr):
    def __init__(self, elements: list[Expr]):
        super().__init__("ListLiteral")
        
        self.kind = "ListLiteral"
        self.elements = elements


class ReturnStatement(Statement):
    def __init__(self, value: Expr = None):
        super().__init__("ReturnStatement")
        
        self.kind = "ReturnStatement"
        self.value = value


class IndexExpr(Expr):
    def __init__(self, object: Expr, index: Expr):
        super().__init__("IndexExpr")
        
        self.kind = "IndexExpr"
        self.object = object
        self.index = index


class MethodCallExpr(Expr):
    def __init__(self, object: Expr, method: str, arguments: list[Expr] = None):
        super().__init__("MethodCallExpr")
        
        self.kind = "MethodCallExpr"
        self.object = object
        self.method = method
        self.arguments = arguments if arguments is not None else []