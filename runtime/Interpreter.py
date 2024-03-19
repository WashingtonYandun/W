from node.NodeType import BinaryExpr, Program, Statement
from runtime.NumberOps import eval_numeric_binary_expr
from runtime.StringOps import eval_string_binary_expr
from runtime.Types import NoneVal, RuntimeVal, NumberVal, StringVal

def eval_binary_expr(binary_op: BinaryExpr) -> RuntimeVal:
    lhs = evaluate(binary_op.left)
    rhs = evaluate(binary_op.right)

    if isinstance(lhs, StringVal) and isinstance(rhs, StringVal):
        return eval_string_binary_expr(lhs, rhs, binary_op.operator)
    
    elif isinstance(lhs, NumberVal) and isinstance(rhs, NumberVal):
        return eval_numeric_binary_expr(lhs, rhs, binary_op.operator)

    return NoneVal()


def eval_program(program: Program) -> RuntimeVal:
    last_evaluated: RuntimeVal = NoneVal()

    for statement in program.body:
        last_evaluated = evaluate(statement)

    return last_evaluated


def eval_binary_expr(binary_op: BinaryExpr) -> RuntimeVal:
    lhs = evaluate(binary_op.left)
    rhs = evaluate(binary_op.right)

    if isinstance(lhs, NumberVal) and isinstance(rhs, NumberVal):
        return eval_numeric_binary_expr(lhs, rhs, binary_op.operator)
    
    elif isinstance(lhs, StringVal) and isinstance(rhs, StringVal):
        return eval_string_binary_expr(lhs, rhs, binary_op.operator)

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