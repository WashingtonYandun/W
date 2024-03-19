from parser.Parser import Parser

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

        ast = parser.parse(text)
        print(ast)


def main() -> None:
    sourceCode = ""
    
    with open("test.w", "r") as file:
        sourceCode = file.read()

    parser = Parser()
    program = parser.parse(sourceCode)
    print(program)

if __name__ == '__main__':
    main()

