from runtime.Types import StringVal


def eval_string_binary_expr(lhs: StringVal, rhs: StringVal, operator: str) -> StringVal:
    if operator == "+":
        result = str(lhs.value) + str(rhs.value)
    else:
        raise Exception(f"Unsupported operator for strings: {operator}")

    return StringVal(value=result)