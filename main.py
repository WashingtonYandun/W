from parser.Parser import Parser
from runtime.Environment import Environment
from runtime.Interpreter import evaluate
from runtime.Types import NoneVal, NumberVal, StringVal

def console()->None:
    parser = Parser()
    env  = Environment()

    env.declare_var("x", NoneVal())
    env.declare_var("y", NumberVal(20))
    env.declare_var("z", StringVal("Hello, World!"))

    env.declare_var("a", NumberVal(10))
    env.declare_var("b", NumberVal(20))
    env.declare_var("c", StringVal("Hello, World!"))

    env.assign_var("a", NumberVal(100))
    env.assign_var("b", NumberVal(200))
    env.assign_var("c", StringVal("Hello, World!"))
    env.assign_var("x", NumberVal(1000))

    print(">> W (V 0.1 ) -> ")

    while True:
        try:
            text = input(">> ")
        except EOFError:
            break

        if not text:
            continue
        elif text == "exit":
            break

        program = parser.parse(text)
        
        res = evaluate(program, env)

        print(res)


def main() -> None:
    # sourceCode = ""
    
    # with open("test.w", "r") as file:
    #     sourceCode = file.read()

    # parser = Parser()
    # program = parser.parse(sourceCode)
    # print(program)

    console()

if __name__ == '__main__':
    main()

