from Lexer import Lexer

if __name__ == '__main__':
    # TODO: Handle strings properly, handle booleans, handle null
    # TODO: Handle comments
    # TODO: Handle operators
    # TODO: Handle keywords
    # TODO: Handle errors

    code = """
    let num x = 45
    let str y = Hola
    let bool z = true
    let null w = null
    """

    lexer = Lexer(code)
    tokens = lexer.tokenize()
    print(tokens)
