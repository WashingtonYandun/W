from typing import Literal, Union

ValueType = Literal["None", "number", "string", "boolean", "function", "native-fn", "list"]


class RuntimeVal:
    """
    Represents a runtime value. This is the base class for all runtime values which can be stored in the environment.

    Attributes:
        type (ValueType): The type of the value.
        value (Union[None, float]): The actual value.
    """

    type: ValueType
    value: Union[None, float]

    def __repr__(self):
        return f"{self.__dict__}"


class NoneVal(RuntimeVal):
    def __init__(self):
        self.type = "None"
        self.value = None


class NumberVal(RuntimeVal):
    def __init__(self, value: float):
        self.type = "number"
        self.value = value


class StringVal(RuntimeVal):
    def __init__(self, value: str):
        self.type = "string"
        self.value = value


class BooleanVal(RuntimeVal):
    def __init__(self, value: bool):
        self.type = "boolean"
        self.value = value


class FunctionVal(RuntimeVal):
    def __init__(self, name: str, parameters: list[str], body: list, env):
        self.type = "function"
        self.name = name
        self.parameters = parameters
        self.body = body
        self.closure_env = env


class NativeFunctionVal(RuntimeVal):
    def __init__(self, name: str, call_fn):
        self.type = "native-fn"
        self.name = name
        self.call = call_fn


class ListVal(RuntimeVal):
    def __init__(self, elements: list):
        self.type = "list"
        self.elements = elements