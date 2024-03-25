from typing import Literal, Union

ValueType = Literal["None", "number", "string", "boolean"]


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