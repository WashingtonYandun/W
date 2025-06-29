from typing import Literal, Union

ValueType = Literal["None", "number", "string", "boolean", "function", "native-fn", "list", "dict"]


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


class DictVal(RuntimeVal):
    def __init__(self, pairs: dict = None):
        self.type = "dict"
        self.pairs = pairs if pairs is not None else {}
        
    def get(self, key):
        """Get value by key"""
        if hasattr(key, 'value'):
            key = key.value
        return self.pairs.get(key, None)
    
    def set(self, key, value):
        """Set key-value pair"""
        if hasattr(key, 'value'):
            key = key.value
        self.pairs[key] = value
    
    def keys(self):
        """Get all keys as a list"""
        return list(self.pairs.keys())
    
    def values(self):
        """Get all values as a list"""
        return list(self.pairs.values())
    
    def items(self):
        """Get all key-value pairs as a list of tuples"""
        return list(self.pairs.items())
    
    def clear(self):
        """Clear all pairs"""
        self.pairs.clear()
    
    def update(self, other_dict):
        """Update with another dictionary"""
        if isinstance(other_dict, DictVal):
            self.pairs.update(other_dict.pairs)
        elif isinstance(other_dict, dict):
            self.pairs.update(other_dict)