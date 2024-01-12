from Lexer import Lexer

if __name__ == '__main__':
    # TODO: Handle strings properly, handle booleans, handle null
    # TODO: Handle comments
    # TODO: Handle operators
    # TODO: Handle keywords
    # TODO: Handle errors

    code = """
    x = 45
    y = Hola
    """

    lexer = Lexer(code)
    tokens = lexer.tokenize()
    print(tokens)
