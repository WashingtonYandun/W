from node.NodeType import BinaryExpr, Identifier, Program, Statement
from runtime.NumberOps import eval_numeric_binary_expr
from runtime.StringOps import eval_string_binary_expr
from runtime.Types import NoneVal, RuntimeVal, NumberVal, StringVal
from runtime.Environment import Environment

def eval_program(program: Program, env: Environment) -> RuntimeVal:
    last_evaluated: RuntimeVal = NoneVal()
    for statement in program.body:
        last_evaluated = evaluate(statement, env)
    return last_evaluated


def eval_binary_expr(binary_op: BinaryExpr, env: Environment) -> RuntimeVal:
    lhs = evaluate(binary_op.left, env)
    rhs = evaluate(binary_op.right, env)

    if isinstance(lhs, StringVal) and isinstance(rhs, StringVal):
        return eval_string_binary_expr(lhs, rhs, binary_op.operator)
    
    if isinstance(lhs, NumberVal) and isinstance(rhs, NumberVal):
        return eval_numeric_binary_expr(lhs, rhs, binary_op.operator)

    return NoneVal()


def eval_indentifier(ast_node: Identifier, env: Environment) -> RuntimeVal:
    return env.lookup_var(ast_node.symbol)

def evaluate(ast_node: Statement, env: Environment) -> RuntimeVal:
    if ast_node.kind == "NumericLiteral":
        return NumberVal(ast_node.value)
    
    if ast_node.kind == "NoneLiteral":
        return NoneVal()
    
    if ast_node.kind == "StringLiteral":
        return StringVal(ast_node.value)
    
    if ast_node.kind == "Identifier":
        return eval_indentifier(ast_node, env)
    
    if ast_node.kind == "BinaryExpr":
        return eval_binary_expr(ast_node, env)
    
    if ast_node.kind == "Program":
        return eval_program(ast_node, env)

    print("This AST Node has not yet been set up for interpretation.", ast_node)
    exit(0)