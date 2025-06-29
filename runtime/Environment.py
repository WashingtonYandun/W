from runtime.Types import NoneVal, RuntimeVal, NativeFunctionVal, NumberVal, ListVal, NativeFunctionVal, NumberVal, ListVal

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

def create_global_env() -> 'Environment':
    env = Environment()
    
    # Add built-in functions
    def print_fn(args, env):
        if len(args) == 0:
            print()
        else:
            for i, arg in enumerate(args):
                if i > 0:
                    print(" ", end="")
                
                # Handle different types of values for printing
                if hasattr(arg, 'value'):
                    print(arg.value, end="")
                elif isinstance(arg, ListVal):
                    # Print list
                    print("[", end="")
                    for j, elem in enumerate(arg.elements):
                        if j > 0:
                            print(", ", end="")
                        if hasattr(elem, 'value'):
                            if isinstance(elem.value, float) and elem.value.is_integer():
                                print(int(elem.value), end="")
                            else:
                                print(elem.value, end="")
                        else:
                            print(elem, end="")
                    print("]", end="")
                else:
                    print(arg, end="")
            print()
        return NoneVal()
    
    def range_fn(args, env):
        if len(args) == 1:
            stop = int(args[0].value)
            start = 0
            step = 1
        elif len(args) == 2:
            start = int(args[0].value)
            stop = int(args[1].value)
            step = 1
        elif len(args) == 3:
            start = int(args[0].value)
            stop = int(args[1].value)
            step = int(args[2].value)
        else:
            print("range() takes 1 to 3 arguments")
            return NoneVal()
        
        numbers = []
        current = start
        if step > 0:
            while current < stop:
                numbers.append(NumberVal(float(current)))
                current += step
        elif step < 0:
            while current > stop:
                numbers.append(NumberVal(float(current)))
                current += step
        else:
            print("range() step cannot be zero")
            return NoneVal()
        
        return ListVal(numbers)
    
    def len_fn(args, env):
        if len(args) != 1:
            print("len() takes exactly one argument")
            return NoneVal()
        
        arg = args[0]
        if isinstance(arg, ListVal):
            return NumberVal(float(len(arg.elements)))
        else:
            print(f"object of type '{type(arg).__name__}' has no len()")
            return NoneVal()
    
    env.declare_var("print", NativeFunctionVal("print", print_fn))
    env.declare_var("range", NativeFunctionVal("range", range_fn))
    env.declare_var("len", NativeFunctionVal("len", len_fn))
    return env
