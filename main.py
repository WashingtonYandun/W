from Lexer import Lexer
from Parser import Parser

if __name__ == '__main__':
    # TODO: Handle strings properly, handle booleans, handle null
    # TODO: Handle comments
    # TODO: Handle operators
    # TODO: Handle keywords
    # TODO: Handle errors

    code = """
    x = 45
    """

    # parser test

    lexer = Lexer(code)
    tokens = lexer.tokenize()
    print(tokens)

    print(12)

    parser = Parser()
    ast = parser.produceAST(code)
    print(ast.body)

