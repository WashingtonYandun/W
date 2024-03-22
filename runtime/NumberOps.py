from runtime.Types import NumberVal


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