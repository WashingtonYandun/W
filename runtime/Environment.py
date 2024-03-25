from runtime.Types import NoneVal, RuntimeVal

class Environment:
    def __init__(self, parent_env: 'Environment' = None) -> None:
        self.parent = parent_env
        self.variables = {}
        self.constants = {}

    def declare_var(self, varname: str, value: RuntimeVal) -> RuntimeVal:
        self.variables[varname] = value
        return value

    def assign_var(self, varname: str, value: any) -> RuntimeVal:
        env = self.resolve(varname)
        last_val = env.variables[varname]

        new_val = None
        if isinstance(last_val, type(value)) or isinstance(last_val, NoneVal):
            new_val = value
            env.variables[varname] = value
            return new_val
        else:
            raise EnvironmentError(f"Cannot assign value of type {type(value)} to variable {varname} of type {type(last_val)}")

    def lookup_var(self, varname: str) -> RuntimeVal:
        env = self.resolve(varname)
        return env.variables[varname]

    def resolve(self, varname: str) -> 'Environment':
        if varname in self.variables:
            return self
        
        if self.parent is None:
            raise Exception(f"Cannot resolve '{varname}' as it does not exist.")
        
        return self.parent.resolve(varname)
