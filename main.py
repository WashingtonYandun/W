from parser.Parser import Parser
from runtime.Environment import Environment
from runtime.Interpreter import evaluate
from runtime.Types import NoneVal, NumberVal, StringVal

def console()->None:
    parser = Parser()
    env  = Environment()

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


def from_file(file:str)->None:
    with open(file, "r") as f:
        text = f.read()

    parser = Parser()
    env = Environment()

    program = parser.parse(text)
    res = evaluate(program, env)

    print(res)


def main() -> None:
    import sys
    if len(sys.argv) > 1:
        from_file(sys.argv[1])
    else:
        console()

if __name__ == '__main__':
    main()

