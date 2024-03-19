from typing import Literal, Union

ValueType = Literal["None", "number", "string"]


class RuntimeVal:
    type: ValueType
    value: Union[None, float]

    def __repr__(self):
        return f"{self.__dict__}"


class NoneVal(RuntimeVal):
    def __init__(self):
        self.type = "None"
        self.value = "None"


class NumberVal(RuntimeVal):
    def __init__(self, value: float):
        self.type = "number"
        self.value = value


class StringVal(RuntimeVal):
    def __init__(self, value: str):
        self.type = "string"
        self.value = value