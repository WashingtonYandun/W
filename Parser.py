from Lexer import Lexer
from NodeType import Program, Statement, Expr, BinaryExpr, Identifier, NumericLiteral
from Token import Token
from TokenType import TokenType


class Parser:
    def __init__(self):
        self.tokens = []

    def not_eof(self) -> bool:
        return self.tokens[0].type != TokenType.EOF

    def at(self) -> Token:
        return self.tokens[0]

    def eat(self) -> Token:
        prev = self.tokens.pop(0)
        return prev

    def expect(self, type_: str, err: any) -> Token:
        prev = self.tokens.pop(0)
        if not prev or prev.type != type_:
            print("Parser Error:\n", err, prev, " - Expecting: ", type_)
            exit(1)

        return prev

    def produceAST(self, sourceCode: str) -> Program:
        lexer = Lexer(sourceCode)
        self.tokens = lexer.tokenize()
        program = Program()
        program.body = []

        while self.not_eof():
            program.body.append(self.parse_stmt())

        return program

    def parse_stmt(self) -> Statement:
        return self.parse_expr()

    def parse_expr(self) -> Expr:
        return self.parse_additive_expr()

    def parse_additive_expr(self) -> Expr:
        left = self.parse_multiplicative_expr()

        while self.at().value in ["+", "-"]:
            operator = self.eat().value
            right = self.parse_multiplicative_expr()
            left = BinaryExpr(left, right, operator)

        return left

    def parse_multiplicative_expr(self) -> Expr:
        left = self.parse_primary_expr()

        while self.at().value in ["/", "*", "%"]:
            operator = self.eat().value
            right = self.parse_primary_expr()
            left = BinaryExpr(left, right, operator)

        return left

    def parse_primary_expr(self) -> Expr:
        tk = self.at().type

        if tk == TokenType.IDENTIFIER:
            return Identifier(self.eat().value)

        elif tk == TokenType.NUMBERS:
            return NumericLiteral(float(self.eat().value))

        elif tk == TokenType.LEFT_PR:
            self.eat()
            value = self.parse_expr()
            self.expect(TokenType.RIGHT_PR,
                        "Unexpected token found inside parenthesized expression. Expected closing parenthesis.")
            return value
        
        elif tk == TokenType.ASSIGNMENT_OPERATOR:
            self.eat()
            value = self.parse_expr()
            return value

        else:
            print("Unexpected token found during parsing!", self.at())
            exit(1)

# Ejemplo de uso:
parser = Parser()
ast = parser.produceAST("hola = 45.67")
# Puedes acceder a la estructura del árbol AST a través de 'ast'