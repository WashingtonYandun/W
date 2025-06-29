from lexer.Lexer import Lexer
from node.NodeType import BooleanLiteral, NoneLiteral, NumericLiteral, Program, Statement, Expr, BinaryExpr, Identifier, StringLiteral, VarDeclaration, IfStatement, WhileStatement, ForStatement, FunctionDeclaration, CallExpr, AssignmentExpr, ListLiteral, ReturnStatement, IndexExpr, MethodCallExpr
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

    def produce_ast(self, sourceCode: str, show_tokens: bool = False) -> Program:
        lexer = Lexer(sourceCode)
        self.tokens = lexer.tokenize()
        if show_tokens:
            print("Tokens:", self.tokens)
        program = Program()
        while self.not_eof():
            if self.at().type == TokenType.NEW_LINE:
                self.eat()
                continue
            program.body.append(self.parse_stmt())
        return program

    def parse_stmt(self) -> Statement:
        if self.at().type == TokenType.CONST:
            return self.parse_var_declaration()
        elif self.at().type == TokenType.IF:
            return self.parse_if_statement()
        elif self.at().type == TokenType.FOR:
            return self.parse_for_statement()
        elif self.at().type == TokenType.WHILE:
            return self.parse_while_statement()
        elif self.at().type == TokenType.FUNC:
            return self.parse_function_declaration()
        elif self.at().type == TokenType.RETURN:
            return self.parse_return_statement()
        elif self.at().type == TokenType.IDENTIFIER:
            if self.peek().type == TokenType.COLON:
                return self.parse_var_declaration()
            elif self.peek().type == TokenType.ASSIGNMENT_OPERATOR:
                return self.parse_assignment_expr()
            else:
                return self.parse_expr()
        else:
            return self.parse_expr()
            
    def parse_var_declaration(self) -> VarDeclaration:
        const = False

        if self.at().type == TokenType.CONST:
            const = True
            self.eat()

        identifier_token = self.expect(TokenType.IDENTIFIER, "Expected identifier")
        identifier = Identifier(identifier_token.value)

        self.expect(TokenType.COLON, "Expected ':' after identifier")

        datatype = self.parse_type()

        self.expect(TokenType.ASSIGNMENT_OPERATOR, "Expected '=' after datatype")

        value = self.parse_expr()

        if self.at().type == TokenType.NEW_LINE:
            self.eat()

        return VarDeclaration(identifier, value, const, datatype)

    def parse_type(self) -> str:
        """Parse type annotations like 'int', 'str', 'list[int]', etc."""
        if self.at().type in [TokenType.DATATYPE_INT, TokenType.DATATYPE_STR, TokenType.DATATYPE_BOOL]:
            type_token = self.eat()
            return type_token.value
        elif self.at().type == TokenType.NONE:
            self.eat()
            return "None"
        elif self.at().type == TokenType.DATATYPE_LIST:
            self.eat()
            self.expect(TokenType.LEFT_BR, "Expected '[' after 'list'")
            inner_type = self.parse_type()
            self.expect(TokenType.RIGHT_BR, "Expected ']' after list type")
            return f"list[{inner_type}]"
        else:
            print(f"Unsupported datatype: {self.at().value}")
            exit(1)



    def parse_expr(self) -> Expr:
        return self.parse_comparison_expr()

    def parse_comparison_expr(self) -> Expr:
        left = self.parse_additive_expr()

        while self.at().type == TokenType.COMPARISON_OPERATOR:
            operator = self.eat().value
            right = self.parse_additive_expr()
            left = BinaryExpr(left=left, right=right, operator=operator)

        return left

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
                ident = Identifier(self.eat().value)
                if self.at().type == TokenType.DOT:
                    return self.parse_method_call(ident)
                elif self.at().type == TokenType.LEFT_PR:
                    return self.parse_call_expr(ident)
                elif self.at().type == TokenType.LEFT_BR:
                    return self.parse_index_expr(ident)
                return ident
            case TokenType.NUMBERS:
                return NumericLiteral(self.eat().value)
            case TokenType.STRINGS:
                return StringLiteral(str(self.eat().value))
            case TokenType.BOOLEANS:
                return BooleanLiteral(self.eat().value)
            case TokenType.BINARY_OPERATOR if self.at().value == "-":
                self.eat()
                if self.at().type == TokenType.NUMBERS:
                    num = self.eat().value
                    return NumericLiteral(-num)
                else:
                    expr = self.parse_primary_expr()
                    return BinaryExpr(left=NumericLiteral(0), right=expr, operator="-")
            case TokenType.LEFT_PR:
                self.eat()
                expr = self.parse_expr()
                self.expect(TokenType.RIGHT_PR, "Expected closing parenthesis")
                return expr
            case TokenType.LEFT_BR:
                return self.parse_list_literal()
            case TokenType.NONE:
                self.eat()
                return NoneLiteral()
            case TokenType.NEW_LINE:
                self.eat()
                return self.parse_expr()
            case _:
                print("Unexpected token found during parsing!", self.at())
                exit(1)

    def parse_call_expr(self, callee: Expr) -> CallExpr:
        self.expect(TokenType.LEFT_PR, "Expected '('")
        
        arguments = []
        if self.at().type != TokenType.RIGHT_PR:
            arguments.append(self.parse_expr())
            while self.at().type == TokenType.COMMA:
                self.eat()
                arguments.append(self.parse_expr())
        
        self.expect(TokenType.RIGHT_PR, "Expected ')' after arguments")
        return CallExpr(callee, arguments)

    def parse(self, sourceCode: str, show_tokens: bool = False) -> Program:
        return self.produce_ast(sourceCode, show_tokens)
    
    def parse_if_statement(self) -> IfStatement:
        self.expect(TokenType.IF, "Expected 'if'")
        condition = self.parse_expr()
        self.expect(TokenType.LEFT_CBR, "Expected '{' after if condition")
        
        if self.at().type == TokenType.NEW_LINE:
            self.eat()
        
        then_body = []
        while self.not_eof() and self.at().type != TokenType.RIGHT_CBR:
            if self.at().type == TokenType.NEW_LINE:
                self.eat()
                continue
            then_body.append(self.parse_stmt())
        
        self.expect(TokenType.RIGHT_CBR, "Expected '}' to close if body")
        
        else_body = []
        if self.at().type == TokenType.ELSE:
            self.eat()
            self.expect(TokenType.LEFT_CBR, "Expected '{' after 'else'")
            
            if self.at().type == TokenType.NEW_LINE:
                self.eat()
            
            while self.not_eof() and self.at().type != TokenType.RIGHT_CBR:
                if self.at().type == TokenType.NEW_LINE:
                    self.eat()
                    continue
                else_body.append(self.parse_stmt())
            
            self.expect(TokenType.RIGHT_CBR, "Expected '}' to close else body")
        
        if self.at().type == TokenType.NEW_LINE:
            self.eat()
        
        return IfStatement(condition, then_body, else_body)

    def parse_while_statement(self) -> WhileStatement:
        self.expect(TokenType.WHILE, "Expected 'while'")
        condition = self.parse_expr()
        self.expect(TokenType.LEFT_CBR, "Expected '{' after while condition")
        
        if self.at().type == TokenType.NEW_LINE:
            self.eat()
        
        body = []
        while self.not_eof() and self.at().type != TokenType.RIGHT_CBR:
            if self.at().type == TokenType.NEW_LINE:
                self.eat()
                continue
            body.append(self.parse_stmt())
        
        self.expect(TokenType.RIGHT_CBR, "Expected '}' to close while body")
        
        if self.at().type == TokenType.NEW_LINE:
            self.eat()
        
        return WhileStatement(condition, body)

    def parse_function_declaration(self) -> FunctionDeclaration:
        self.expect(TokenType.FUNC, "Expected 'func'")
        
        name_token = self.expect(TokenType.IDENTIFIER, "Expected function name")
        name = name_token.value
        
        self.expect(TokenType.LEFT_PR, "Expected '(' after function name")
        
        # Parse parameters with types: param: type
        parameters = []
        if self.at().type != TokenType.RIGHT_PR:
            # Parse first parameter
            param_name = self.expect(TokenType.IDENTIFIER, "Expected parameter name").value
            self.expect(TokenType.COLON, "Expected ':' after parameter name")
            param_type = self.parse_type()
            parameters.append((param_name, param_type))
            
            # Parse additional parameters
            while self.at().type == TokenType.COMMA:
                self.eat()  # consume comma
                param_name = self.expect(TokenType.IDENTIFIER, "Expected parameter name").value
                self.expect(TokenType.COLON, "Expected ':' after parameter name")
                param_type = self.parse_type()
                parameters.append((param_name, param_type))
        
        self.expect(TokenType.RIGHT_PR, "Expected ')' after parameters")
        
        # Parse return type annotation: -> type
        return_type = "None"
        if self.at().type == TokenType.ARROW:
            self.eat()
            return_type = self.parse_type()
        
        self.expect(TokenType.LEFT_CBR, "Expected '{' to start function body")
        
        if self.at().type == TokenType.NEW_LINE:
            self.eat()
        
        body = []
        while self.not_eof() and self.at().type != TokenType.RIGHT_CBR:
            if self.at().type == TokenType.NEW_LINE:
                self.eat()
                continue
            body.append(self.parse_stmt())
        
        self.expect(TokenType.RIGHT_CBR, "Expected '}' to end function body")
        
        if self.at().type == TokenType.NEW_LINE:
            self.eat()
        
        return FunctionDeclaration(name, parameters, body, return_type)
    
    def parse_assignment_expr(self) -> AssignmentExpr:
        assignee_token = self.expect(TokenType.IDENTIFIER, "Expected identifier")
        assignee = Identifier(assignee_token.value)
        
        self.expect(TokenType.ASSIGNMENT_OPERATOR, "Expected '='")
        
        value = self.parse_expr()
        
        if self.at().type == TokenType.NEW_LINE:
            self.eat()
        
        return AssignmentExpr(assignee, value)

    def parse_for_statement(self) -> ForStatement:
        self.expect(TokenType.FOR, "Expected 'for'")
        
        var_token = self.expect(TokenType.IDENTIFIER, "Expected variable name")
        variable = var_token.value
        
        self.expect(TokenType.IN, "Expected 'in' after for variable")
        
        iterable = self.parse_expr()
        
        self.expect(TokenType.LEFT_CBR, "Expected '{' after for iterable")
        
        if self.at().type == TokenType.NEW_LINE:
            self.eat()
        
        body = []
        while self.not_eof() and self.at().type != TokenType.RIGHT_CBR:
            if self.at().type == TokenType.NEW_LINE:
                self.eat()
                continue
            body.append(self.parse_stmt())
        
        self.expect(TokenType.RIGHT_CBR, "Expected '}' to close for body")
        
        if self.at().type == TokenType.NEW_LINE:
            self.eat()
        
        return ForStatement(variable, iterable, body)

    def parse_list_literal(self) -> ListLiteral:
        self.expect(TokenType.LEFT_BR, "Expected '['")
        
        elements = []
        if self.at().type != TokenType.RIGHT_BR:
            elements.append(self.parse_expr())
            while self.at().type == TokenType.COMMA:
                self.eat()  # consume comma
                if self.at().type == TokenType.RIGHT_BR:
                    break  # trailing comma
                elements.append(self.parse_expr())
        
        self.expect(TokenType.RIGHT_BR, "Expected ']' after list elements")
        return ListLiteral(elements)

    def parse_return_statement(self) -> ReturnStatement:
        self.expect(TokenType.RETURN, "Expected 'return'")
        
        if (self.at().type in [TokenType.NEW_LINE, TokenType.RIGHT_CBR] or 
            self.at().type == TokenType.EOF):
            return ReturnStatement()
        
        value = self.parse_expr()
        
        if self.at().type == TokenType.NEW_LINE:
            self.eat()
            
        return ReturnStatement(value)

    def parse_index_expr(self, object: Expr) -> IndexExpr:
        self.expect(TokenType.LEFT_BR, "Expected '['")
        index = self.parse_expr()
        self.expect(TokenType.RIGHT_BR, "Expected ']' after index")
        return IndexExpr(object, index)

    def parse_method_call(self, object: Expr) -> MethodCallExpr:
        self.expect(TokenType.DOT, "Expected '.'")
        
        if self.at().type not in [TokenType.APPEND, TokenType.INSERT, TokenType.REMOVE, 
                                 TokenType.POP, TokenType.CLEAR, TokenType.INDEX, 
                                 TokenType.COUNT, TokenType.SORT, TokenType.REVERSE, TokenType.EXTEND]:
            print(f"Unknown method: {self.at().value}")
            exit(1)
            
        method_name = self.eat().value
        
        arguments = []
        if self.at().type == TokenType.LEFT_PR:
            self.eat()
            
            if self.at().type != TokenType.RIGHT_PR:
                arguments.append(self.parse_expr())
                
                while self.at().type == TokenType.COMMA:
                    self.eat()  # consume ','
                    arguments.append(self.parse_expr())
            
            self.expect(TokenType.RIGHT_PR, "Expected ')' after method arguments")
        
        return MethodCallExpr(object, method_name, arguments)