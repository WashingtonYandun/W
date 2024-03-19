from parser.Parser import Parser


def main() -> None:
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

        ast = parser.produceAST(text)
        print(ast.body)


if __name__ == '__main__':
    main()

