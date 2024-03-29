from lexer.Lexer import Lexer
from node.NodeType import BooleanLiteral, NoneLiteral, NumericLiteral, Program, Statement, Expr, BinaryExpr, Identifier, StringLiteral, VarDeclaration
from token.Token import Token
from token.TokenType import TokenType


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
    
    def peek(self) -> Token:
        if len(self.tokens) > 1:
            return self.tokens[1]
        return Token(None, TokenType.EOF)

    def produce_ast(self, sourceCode: str) -> Program:
        lexer = Lexer(sourceCode)
        self.tokens = lexer.tokenize()
        print(self.tokens)
        program = Program()
        while self.not_eof():
            program.body.append(self.parse_stmt())
        return program

    def parse_stmt(self) -> Statement:
        if self.at().type == TokenType.CONST_DATA:
            return self.parse_var_declaration()
        elif self.at().type == TokenType.IDENTIFIER:
            if self.peek().type == TokenType.COLON:
                return self.parse_var_declaration()
            else:
                return self.parse_expr()
        else:
            return self.parse_expr()
            
    # (const | None) ident :data = value
    def parse_var_declaration(self) -> VarDeclaration:
        const = False
        identifier = None
        datatype = None

        if self.at().type == TokenType.CONST_DATA:
            const = True
            self.eat()

        identifier_token = self.expect(TokenType.IDENTIFIER, "Expected identifier")
        identifier = Identifier(identifier_token.value)

        self.expect(TokenType.COLON, "Expected ':' after identifier")

        datatype_token = self.eat()
        if datatype_token.value not in ["num", "str", "bool"]:
            print("Unsupported datatype:", datatype_token.value)
            exit(1)

        self.expect(TokenType.ASSIGNMENT_OPERATOR, "Expected '=' after datatype")

        value = self.parse_expr()

        if self.at().type == TokenType.NEW_LINE:
            self.eat()

        return VarDeclaration(identifier, value, const, datatype_token.value)



    def parse_expr(self) -> Expr:
        return self.parse_additive_expr()

    def parse_additive_expr(self) -> Expr:
        left = self.parse_multiplicative_expr()

        while self.at().value in ["+", "-"]:
            operator = self.eat().value
            right = self.parse_multiplicative_expr()
            left = BinaryExpr(left=left, right=right, operator=operator)

        return left

    def parse_multiplicative_expr(self) -> Expr:
        left = self.parse_primary_expr()

        while self.at().value in ["/", "*", "%"]:
            operator = self.eat().value
            right = self.parse_primary_expr()
            left = BinaryExpr(left=left, right=right, operator=operator)

        return left


    def parse_primary_expr(self) -> Expr:
        tk = self.at().type

        match tk:
            case TokenType.IDENTIFIER:
                return Identifier(self.eat().value)
            case TokenType.NUMBERS:
                return NumericLiteral(self.eat().value)
            case TokenType.STRINGS:
                return StringLiteral(str(self.eat().value))
            case TokenType.BOOLEANS:
                return BooleanLiteral(self.eat().value)
            case TokenType.LEFT_PR:
                self.eat()
                expr = self.parse_expr()
                self.expect(TokenType.RIGHT_PR, "Expected closing parenthesis")
                return expr
            case TokenType.NONE:
                self.eat()
                return NoneLiteral()
            case TokenType.NEW_LINE:
                self.eat()
                return self.parse_expr()
            case _:
                
                print("Unexpected token found during parsing!", self.at())
                exit(1)

    def parse(self, sourceCode: str) -> Program:
        return self.produce_ast(sourceCode)
    
    def __repr__(self):
        return f"{self.__dict__}"