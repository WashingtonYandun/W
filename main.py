from parser.Parser import Parser
from runtime.Interpreter import evaluate

def console()->None:
    parser = Parser()
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
        
        res = evaluate(program)

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

