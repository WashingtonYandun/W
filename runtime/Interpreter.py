from node.NodeType import BinaryExpr, Program, Statement
from runtime.Types import NoneVal, RuntimeVal, NumberVal, StringVal

def eval_string_binary_expr(lhs: StringVal, rhs: StringVal, operator: str) -> StringVal:
    if operator == "+":
        result = str(lhs.value) + str(rhs.value)
    else:
        raise Exception(f"Unsupported operator for strings: {operator}")

    return StringVal(value=result)

def eval_binary_expr(binop: BinaryExpr) -> RuntimeVal:
    lhs = evaluate(binop.left)
    rhs = evaluate(binop.right)

    if isinstance(lhs, StringVal) and isinstance(rhs, StringVal):
        return eval_string_binary_expr(lhs, rhs, binop.operator)
    elif isinstance(lhs, NumberVal) and isinstance(rhs, NumberVal):
        return eval_numeric_binary_expr(lhs, rhs, binop.operator)

    return NoneVal()


def eval_program(program: Program) -> RuntimeVal:
    last_evaluated: RuntimeVal = NoneVal()

    for statement in program.body:
        last_evaluated = evaluate(statement)

    return last_evaluated


def eval_numeric_binary_expr(lhs: NumberVal, rhs: NumberVal, operator: str) -> NumberVal:
    if operator == "+":
        result = lhs.value + rhs.value
    elif operator == "-":
        result = lhs.value - rhs.value
    elif operator == "*":
        result = lhs.value * rhs.value
    elif operator == "/":
        result = lhs.value / rhs.value
    elif operator == "%":
        result = lhs.value % rhs.value
    elif operator == "**":
        result = lhs.value ** rhs.value
    else:
        raise Exception(f"Unrecognized binary operator: {operator}")

    return NumberVal(value=result)


def eval_binary_expr(binop: BinaryExpr) -> RuntimeVal:
    lhs = evaluate(binop.left)
    rhs = evaluate(binop.right)

    if isinstance(lhs, NumberVal) and isinstance(rhs, NumberVal):
        return eval_numeric_binary_expr(lhs, rhs, binop.operator)
    elif isinstance(lhs, StringVal) and isinstance(rhs, StringVal):
        return eval_string_binary_expr(lhs, rhs, binop.operator)

    return NoneVal()


def evaluate(ast_node: Statement) -> RuntimeVal:
    if ast_node.kind == "NumericLiteral":
        return NumberVal(ast_node.value)
    
    elif ast_node.kind == "NoneLiteral":
        return NoneVal()
    
    elif ast_node.kind == "StringLiteral":
        return StringVal(ast_node.value)
    
    elif ast_node.kind == "BinaryExpr":
        return eval_binary_expr(ast_node)
    
    elif ast_node.kind == "Program":
        return eval_program(ast_node)

    print("This AST Node has not yet been set up for interpretation.", ast_node)
    exit(0)