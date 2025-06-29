from runtime.Types import NumberVal, IntVal, FloatVal, RuntimeVal


def eval_numeric_binary_expr(lhs: RuntimeVal, rhs: RuntimeVal, operator: str) -> RuntimeVal:
    # Extract numeric values and determine types
    lhs_value = lhs.value
    rhs_value = rhs.value
    
    # Type promotion rules:
    # int + int = int
    # int + float = float  
    # float + int = float
    # float + float = float
    is_float_result = (lhs.type == "float" or rhs.type == "float")
    
    # For division, always return float to avoid integer division issues
    if operator == "/":
        is_float_result = True
    
    if operator == "+":
        result = lhs_value + rhs_value
    elif operator == "-":
        result = lhs_value - rhs_value
    elif operator == "*":
        result = lhs_value * rhs_value
    elif operator == "/":
        if rhs_value == 0:
            raise Exception("Division by zero")
        result = lhs_value / rhs_value
    elif operator == "%":
        if rhs_value == 0:
            raise Exception("Modulo by zero")
        result = lhs_value % rhs_value
    elif operator == "**":
        result = lhs_value ** rhs_value
        # Power operation can produce floats even with integers (e.g., 2**-1)
        if not isinstance(result, int):
            is_float_result = True
    else:
        raise Exception(f"Unrecognized binary operator: {operator}")

    # Return appropriate type
    if is_float_result:
        return FloatVal(float(result))
    else:
        # Check if result is actually an integer
        if isinstance(result, float) and result.is_integer():
            return IntVal(int(result))
        elif isinstance(result, int):
            return IntVal(result)
        else:
            return FloatVal(result)