from Lexer import Lexer
from Parser import Parser

if __name__ == '__main__':
    parser = Parser()

    print(">> W (V 0.1 ) -> ")

    while True:
        try:
            text = input(">> ")
        except EOFError:
            break

        if not text:
            continue

        ast = parser.produceAST(text)
        print(ast.body)

