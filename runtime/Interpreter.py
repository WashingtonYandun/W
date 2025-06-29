from node.NodeType import BinaryExpr, Identifier, Program, Statement, AssignmentExpr
from runtime.NumberOps import eval_numeric_binary_expr
from runtime.StringOps import eval_string_binary_expr
from runtime.Types import BooleanVal, NoneVal, RuntimeVal, NumberVal, StringVal, FunctionVal, NativeFunctionVal, ListVal
from runtime.Environment import Environment

class ReturnValue(Exception):
    def __init__(self, value: RuntimeVal):
        self.value = value

def eval_program(program: Program, env: Environment) -> RuntimeVal:
    last_evaluated: RuntimeVal = NoneVal()
    for statement in program.body:
        last_evaluated = evaluate(statement, env)
    return last_evaluated


def eval_binary_expr(binary_op: BinaryExpr, env: Environment) -> RuntimeVal:
    lhs = evaluate(binary_op.left, env)
    rhs = evaluate(binary_op.right, env)

    if binary_op.operator in ['==', '!=', '<', '>', '<=', '>=']:
        return eval_comparison_expr(lhs, rhs, binary_op.operator)

    if isinstance(lhs, StringVal) and isinstance(rhs, StringVal):
        return eval_string_binary_expr(lhs, rhs, binary_op.operator)
    
    if isinstance(lhs, NumberVal) and isinstance(rhs, NumberVal):
        return eval_numeric_binary_expr(lhs, rhs, binary_op.operator)

    return NoneVal()


def eval_comparison_expr(lhs: RuntimeVal, rhs: RuntimeVal, operator: str) -> BooleanVal:
    if operator == '==':
        return BooleanVal(lhs.value == rhs.value)
    elif operator == '!=':
        return BooleanVal(lhs.value != rhs.value)
    
    if isinstance(lhs, NumberVal) and isinstance(rhs, NumberVal):
        if operator == '<':
            return BooleanVal(lhs.value < rhs.value)
        elif operator == '>':
            return BooleanVal(lhs.value > rhs.value)
        elif operator == '<=':
            return BooleanVal(lhs.value <= rhs.value)
        elif operator == '>=':
            return BooleanVal(lhs.value >= rhs.value)
    
    return BooleanVal(False)


def eval_indentifier(ast_node: Identifier, env: Environment) -> RuntimeVal:
    return env.lookup_var(ast_node.symbol)

def eval_if_statement(if_stmt, env: Environment) -> RuntimeVal:
    condition = evaluate(if_stmt.condition, env)
    
    is_truthy = False
    if isinstance(condition, BooleanVal):
        is_truthy = condition.value
    elif isinstance(condition, NumberVal):
        is_truthy = condition.value != 0
    elif isinstance(condition, StringVal):
        is_truthy = len(condition.value) > 0
    
    if is_truthy:
        last_evaluated = NoneVal()
        for stmt in if_stmt.then_body:
            last_evaluated = evaluate(stmt, env)
        return last_evaluated
    else:
        last_evaluated = NoneVal()
        for stmt in if_stmt.else_body:
            last_evaluated = evaluate(stmt, env)
        return last_evaluated


def eval_while_statement(while_stmt, env: Environment) -> RuntimeVal:
    last_evaluated = NoneVal()
    
    while True:
        condition = evaluate(while_stmt.condition, env)
        
        is_truthy = False
        if isinstance(condition, BooleanVal):
            is_truthy = condition.value
        elif isinstance(condition, NumberVal):
            is_truthy = condition.value != 0
        elif isinstance(condition, StringVal):
            is_truthy = len(condition.value) > 0
        
        if not is_truthy:
            break
        
        for stmt in while_stmt.body:
            last_evaluated = evaluate(stmt, env)
    
    return last_evaluated


def eval_function_declaration(func_decl, env: Environment) -> RuntimeVal:
    param_names = [param[0] for param in func_decl.parameters]
    function = FunctionVal(func_decl.name, param_names, func_decl.body, env)
    return env.declare_var(func_decl.name, function)


def eval_call_expr(call_expr, env: Environment) -> RuntimeVal:
    func = evaluate(call_expr.callee, env)
    
    if isinstance(func, NativeFunctionVal):
        args = []
        for arg in call_expr.arguments:
            args.append(evaluate(arg, env))
        return func.call(args, env)
    
    if not isinstance(func, FunctionVal):
        print(f"Cannot call non-function value: {func}")
        return NoneVal()
    
    args = []
    for arg in call_expr.arguments:
        args.append(evaluate(arg, env))
    
    if len(args) != len(func.parameters):
        print(f"Function {func.name} expects {len(func.parameters)} arguments, got {len(args)}")
        return NoneVal()
    
    func_env = Environment(func.closure_env)
    
    for i, param in enumerate(func.parameters):
        func_env.declare_var(param, args[i])
    
    last_evaluated = NoneVal()
    try:
        for stmt in func.body:
            last_evaluated = evaluate(stmt, func_env)
    except ReturnValue as ret:
        return ret.value
    
    return last_evaluated

def eval_assignment_expr(assignment: 'AssignmentExpr', env: Environment) -> RuntimeVal:
    value = evaluate(assignment.value, env)
    return env.assign_var(assignment.assignee.symbol, value)

def eval_for_statement(for_stmt, env: Environment) -> RuntimeVal:
    iterable = evaluate(for_stmt.iterable, env)
    
    if not isinstance(iterable, ListVal):
        print(f"Cannot iterate over non-list value: {iterable}")
        return NoneVal()
    
    last_evaluated = NoneVal()
    
    # Create a new scope for the for loop
    loop_env = Environment(env)
    
    for element in iterable.elements:
        loop_env.declare_var(for_stmt.variable, element)
        
        for stmt in for_stmt.body:
            last_evaluated = evaluate(stmt, loop_env)
    
    return last_evaluated

def eval_list_literal(list_node, env: Environment) -> ListVal:
    """Evaluate list literals like [1, 2, 3]"""
    elements = []
    for element_node in list_node.elements:
        elements.append(evaluate(element_node, env))
    return ListVal(elements)

def eval_return_statement(return_stmt, env: Environment) -> RuntimeVal:
    """Evaluate return statements"""
    if return_stmt.value:
        value = evaluate(return_stmt.value, env)
        raise ReturnValue(value)
    else:
        raise ReturnValue(NoneVal())

def eval_index_expr(index_node, env: Environment) -> RuntimeVal:
    """Evaluate index expressions like arr[i]"""
    obj = evaluate(index_node.object, env)
    index = evaluate(index_node.index, env)
    
    if not isinstance(obj, ListVal):
        print(f"Cannot index non-list value: {obj}")
        return NoneVal()
    
    if not isinstance(index, NumberVal):
        print(f"List indices must be integers, not {type(index).__name__}")
        return NoneVal()
    
    idx = int(index.value)
    if idx < 0 or idx >= len(obj.elements):
        print(f"List index out of range: {idx}")
        return NoneVal()
    
    return obj.elements[idx]


def eval_method_call_expr(method_call, env: Environment) -> RuntimeVal:
    """Evaluate method calls like list.append(value), list.pop(), etc."""
    obj = evaluate(method_call.object, env)
    
    if not isinstance(obj, ListVal):
        print(f"Cannot call method on non-list value: {obj}")
        return NoneVal()
    
    method_name = method_call.method
    args = [evaluate(arg, env) for arg in method_call.arguments]
    
    # Implement list methods
    if method_name == "append":
        if len(args) != 1:
            print(f"append() takes exactly 1 argument ({len(args)} given)")
            return NoneVal()
        obj.elements.append(args[0])
        return NoneVal()
    
    elif method_name == "insert":
        if len(args) != 2:
            print(f"insert() takes exactly 2 arguments ({len(args)} given)")
            return NoneVal()
        if not isinstance(args[0], NumberVal):
            print("insert() index must be an integer")
            return NoneVal()
        idx = int(args[0].value)
        if idx < 0:
            idx = 0
        elif idx > len(obj.elements):
            idx = len(obj.elements)
        obj.elements.insert(idx, args[1])
        return NoneVal()
    
    elif method_name == "remove":
        if len(args) != 1:
            print(f"remove() takes exactly 1 argument ({len(args)} given)")
            return NoneVal()
        try:
            for i, element in enumerate(obj.elements):
                if elements_equal(element, args[0]):
                    obj.elements.pop(i)
                    return NoneVal()
            print(f"list.remove(x): x not in list")
            return NoneVal()
        except:
            print(f"list.remove(x): x not in list")
            return NoneVal()
    
    elif method_name == "pop":
        if len(args) > 1:
            print(f"pop() takes at most 1 argument ({len(args)} given)")
            return NoneVal()
        if len(obj.elements) == 0:
            print("pop from empty list")
            return NoneVal()
        
        if len(args) == 0:
            return obj.elements.pop()
        else:
            if not isinstance(args[0], NumberVal):
                print("pop() index must be an integer")
                return NoneVal()
            idx = int(args[0].value)
            if idx < 0 or idx >= len(obj.elements):
                print(f"pop index out of range")
                return NoneVal()
            return obj.elements.pop(idx)
    
    elif method_name == "clear":
        if len(args) != 0:
            print(f"clear() takes no arguments ({len(args)} given)")
            return NoneVal()
        obj.elements.clear()
        return NoneVal()
    
    elif method_name == "index":
        if len(args) != 1:
            print(f"index() takes exactly 1 argument ({len(args)} given)")
            return NoneVal()
        for i, element in enumerate(obj.elements):
            if elements_equal(element, args[0]):
                return NumberVal(i)
        print(f"x is not in list")
        return NoneVal()
    
    elif method_name == "count":
        if len(args) != 1:
            print(f"count() takes exactly 1 argument ({len(args)} given)")
            return NoneVal()
        count = 0
        for element in obj.elements:
            if elements_equal(element, args[0]):
                count += 1
        return NumberVal(count)
    
    elif method_name == "sort":
        if len(args) != 0:
            print(f"sort() takes no arguments ({len(args)} given)")
            return NoneVal()
        try:
            obj.elements.sort(key=lambda x: x.value if hasattr(x, 'value') else 0)
        except:
            print("sort() requires comparable elements")
        return NoneVal()
    
    elif method_name == "reverse":
        if len(args) != 0:
            print(f"reverse() takes no arguments ({len(args)} given)")
            return NoneVal()
        obj.elements.reverse()
        return NoneVal()
    
    elif method_name == "extend":
        if len(args) != 1:
            print(f"extend() takes exactly 1 argument ({len(args)} given)")
            return NoneVal()
        if not isinstance(args[0], ListVal):
            print("extend() argument must be a list")
            return NoneVal()
        obj.elements.extend(args[0].elements)
        return NoneVal()
    
    else:
        print(f"Unknown list method: {method_name}")
        return NoneVal()


def elements_equal(a: RuntimeVal, b: RuntimeVal) -> bool:
    """Helper function to compare two runtime values for equality"""
    if type(a) != type(b):
        return False
    
    if isinstance(a, NumberVal):
        return a.value == b.value
    elif isinstance(a, StringVal):
        return a.value == b.value
    elif isinstance(a, BooleanVal):
        return a.value == b.value
    elif isinstance(a, NoneVal):
        return True
    else:
        return False
def evaluate(ast_node: Statement, env: Environment) -> RuntimeVal:
    if ast_node.kind == "NumericLiteral":
        return NumberVal(ast_node.value)
    
    if ast_node.kind == "NoneLiteral":
        return NoneVal()
    
    if ast_node.kind == "StringLiteral":
        return StringVal(ast_node.value)
    
    if ast_node.kind == "BooleanLiteral":
        return BooleanVal(ast_node.value)
    
    if ast_node.kind == "ListLiteral":
        return eval_list_literal(ast_node, env)
    
    if ast_node.kind == "IndexExpr":
        return eval_index_expr(ast_node, env)
    
    if ast_node.kind == "MethodCallExpr":
        return eval_method_call_expr(ast_node, env)

    if ast_node.kind == "VarDeclaration":
        return env.declare_var(ast_node.identifier.symbol, evaluate(ast_node.initializer, env))
    
    if ast_node.kind == "Identifier":
        return eval_indentifier(ast_node, env)
    
    if ast_node.kind == "BinaryExpr":
        return eval_binary_expr(ast_node, env)
    
    if ast_node.kind == "IfStatement":
        return eval_if_statement(ast_node, env)
    
    if ast_node.kind == "WhileStatement":
        return eval_while_statement(ast_node, env)
    
    if ast_node.kind == "ForStatement":
        return eval_for_statement(ast_node, env)
    
    if ast_node.kind == "FunctionDeclaration":
        return eval_function_declaration(ast_node, env)
    
    if ast_node.kind == "CallExpr":
        return eval_call_expr(ast_node, env)
    
    if ast_node.kind == "AssignmentExpr":
        return eval_assignment_expr(ast_node, env)
    
    if ast_node.kind == "ReturnStatement":
        return eval_return_statement(ast_node, env)
    
    if ast_node.kind == "Program":
        return eval_program(ast_node, env)

    if ast_node.kind == "AssignmentExpr":
        return eval_assignment_expr(ast_node, env)

    if ast_node.kind == "ForStatement":
        return eval_for_statement(ast_node, env)

    print("This AST Node has not yet been set up for interpretation.", ast_node)
    exit(0)