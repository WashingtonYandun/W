import os
from typing import List, Optional
from token.Token import Token
from token.TokenType import TokenType
from lexer.Lexer import Lexer
from error.Error import ParserError
from node.NodeType import (
    Node, Program, Stmt, Expr, TypeNode, Pattern, Block,
    NamedType, OptionalType, ListType, DictType, TupleType, ResultType,
    IdentifierPattern, TuplePattern, EnumPattern, LiteralPattern, WildcardPattern,
    FnDecl, Param, StructDecl, StructField, EnumDecl,
    InterfaceDecl, InterfaceMethod, ClassDecl, ClassField, MethodDecl,
    ImportDecl, LetDecl,
    WhileStmt, ForStmt, ReturnStmt, BreakStmt, ContinueStmt, ExprStmt,
    IntLiteral, FloatLiteral, StringLiteral, BoolLiteral, NoneLiteral,
    IdentExpr, ThisExpr, SuperExpr, NewExpr,
    UnaryExpr, BinaryExpr, CoalesceExpr, RangeExpr, PostfixTryExpr, ElseErrExpr,
    CallExpr, MemberExpr, IndexExpr, AssignmentExpr,
    StructInitExpr, FieldInit, ListExpr, DictExpr, DictEntry, TupleExpr,
    IfExpr, ElifBranch, MatchExpr, MatchArm
)


# Infix Precedence Binding Power (higher = binds tighter)
PRECEDENCE = {
    TokenType.ASSIGN: 1,             # '=' (right-associative)
    TokenType.QUESTION_QUESTION: 2,  # '??' (right-associative)
    TokenType.OR: 3,                 # 'or'
    TokenType.AND: 4,                # 'and'
    TokenType.EQ: 5,                 # '=='
    TokenType.NOT_EQ: 5,             # '!='
    TokenType.LT: 6,                 # '<'
    TokenType.LTE: 6,                # '<='
    TokenType.GT: 6,                 # '>'
    TokenType.GTE: 6,                # '>='
    TokenType.DOT_DOT: 7,            # '..'
    TokenType.DOT_DOT_EQ: 7,         # '..='
    TokenType.PLUS: 8,               # '+'
    TokenType.MINUS: 8,              # '-'
    TokenType.STAR: 9,               # '*'
    TokenType.SLASH: 9,              # '/'
    TokenType.PERCENT: 9,            # '%'
}

class Parser:
    """
    Recursive Descent + Pratt Parser for W Language v0.1.
    Never calls exit(); raises ParserError with exact diagnostic codes and positions.
    """
    def __init__(self, file: str = "<stdin>") -> None:
        self.file = file
        self.tokens: List[Token] = []
        self.pos = 0

    def parse(self, source: str, show_tokens: bool = False) -> Program:
        lexer = Lexer(source, file=self.file)
        self.tokens = lexer.tokenize()
        self.pos = 0
        if show_tokens:
            print("Tokens:", self.tokens)
        try:
            return self.produce_ast()
        except RecursionError:
            raise ParserError(
                message="Maximum syntax nesting depth exceeded",
                line=self.at().line,
                col=self.at().col,
                file=self.file,
                code="W0006",
            )

    def produce_ast(self) -> Program:
        start_line = self.at().line
        start_col = self.at().col
        body: List[Stmt] = []

        while not self.is_at_end():
            stmt = self.parse_stmt(allow_top_level=True)
            if stmt is not None:
                body.append(stmt)

        return Program(body=body, line=start_line, col=start_col)

    # ==========================================
    # Stream Navigation Helpers
    # ==========================================

    def at(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]

    def peek(self, offset: int = 1) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]

    def advance(self) -> Token:
        curr = self.at()
        if not self.is_at_end():
            self.pos += 1
        return curr

    def is_at_end(self) -> bool:
        return self.at().type == TokenType.EOF

    def check(self, type_: TokenType) -> bool:
        if self.is_at_end():
            return False
        return self.at().type == type_

    def match(self, *types: TokenType) -> bool:
        for t in types:
            if self.check(t):
                self.advance()
                return True
        return False

    def expect(self, type_: TokenType, code: str = "P002", msg: str = None) -> Token:
        if self.check(type_):
            return self.advance()
        token = self.at()
        err_msg = msg if msg else f"Expected token '{type_.name}', found '{token.type.name}'"
        raise ParserError(message=err_msg, line=token.line, col=token.col, file=self.file, code=code)

    # ==========================================
    # Type Annotation Parsing
    # ==========================================

    def parse_type(self) -> TypeNode:
        token = self.at()
        if not self.check(TokenType.IDENTIFIER):
            raise ParserError(
                message=f"Expected type name, found '{token.type.name}'",
                line=token.line,
                col=token.col,
                file=self.file,
                code="P006"
            )

        name_tok = self.advance()
        name = name_tok.value
        line = name_tok.line
        col = name_tok.col

        inner_type: TypeNode
        if self.match(TokenType.LBRACKET):
            if name == "list":
                elem_type = self.parse_type()
                self.expect(TokenType.RBRACKET, code="P006", msg="Expected ']' after list type")
                inner_type = ListType(element_type=elem_type, line=line, col=col)
            elif name == "dict":
                key_type = self.parse_type()
                self.expect(TokenType.COMMA, code="P006", msg="Expected ',' between dict key and value types")
                val_type = self.parse_type()
                self.expect(TokenType.RBRACKET, code="P006", msg="Expected ']' after dict types")
                inner_type = DictType(key_type=key_type, value_type=val_type, line=line, col=col)
            elif name == "tuple":
                elem_types: List[TypeNode] = []
                if not self.check(TokenType.RBRACKET):
                    elem_types.append(self.parse_type())
                    while self.match(TokenType.COMMA):
                        if self.check(TokenType.RBRACKET):
                            break
                        elem_types.append(self.parse_type())
                self.expect(TokenType.RBRACKET, code="P006", msg="Expected ']' after tuple types")
                inner_type = TupleType(element_types=elem_types, line=line, col=col)
            else:
                # Generic custom type
                generic_arg = self.parse_type()
                self.expect(TokenType.RBRACKET, code="P006", msg="Expected ']' after generic type")
                inner_type = NamedType(name=f"{name}[{generic_arg}]", line=line, col=col)
        else:
            inner_type = NamedType(name=name, line=line, col=col)

        # Check for optional postfix '?'
        if self.match(TokenType.QUESTION):
            inner_type = OptionalType(inner=inner_type, line=line, col=col)

        # Check for fallible return type '!'
        if self.match(TokenType.EXCLAMATION):
            err_type = self.parse_type()
            inner_type = ResultType(ok_type=inner_type, err_type=err_type, line=line, col=col)

        return inner_type

    # ==========================================
    # Pattern Parsing
    # ==========================================

    def parse_pattern(self) -> Pattern:
        token = self.at()

        if self.match(TokenType.IDENTIFIER):
            first_name = token.value
            # Check for EnumPattern: EnumName.Variant
            if self.match(TokenType.DOT):
                variant_tok = self.expect(TokenType.IDENTIFIER, code="P002", msg="Expected enum variant name after '.'")
                return EnumPattern(enum_name=first_name, variant=variant_tok.value, line=token.line, col=token.col)

            # Check for TuplePattern: a, b
            if self.check(TokenType.COMMA):
                elements: List[Pattern] = [IdentifierPattern(first_name, line=token.line, col=token.col)]
                while self.match(TokenType.COMMA):
                    next_tok = self.expect(TokenType.IDENTIFIER, code="P002", msg="Expected identifier in tuple pattern")
                    elements.append(IdentifierPattern(next_tok.value, line=next_tok.line, col=next_tok.col))
                return TuplePattern(elements=elements, line=token.line, col=token.col)

            return IdentifierPattern(name=first_name, line=token.line, col=token.col)

        if self.match(TokenType.INT):
            lit = IntLiteral(token.value, line=token.line, col=token.col)
            return LiteralPattern(literal=lit, line=token.line, col=token.col)

        if self.match(TokenType.STR):
            lit = StringLiteral(token.value, line=token.line, col=token.col)
            return LiteralPattern(literal=lit, line=token.line, col=token.col)

        if self.match(TokenType.TRUE, TokenType.FALSE):
            lit = BoolLiteral(token.value, line=token.line, col=token.col)
            return LiteralPattern(literal=lit, line=token.line, col=token.col)

        raise ParserError(
            message=f"Invalid pattern syntax, found '{token.type.name}'",
            line=token.line,
            col=token.col,
            file=self.file,
            code="P003"
        )

    # ==========================================
    # Statement & Declaration Parsing
    # ==========================================

    def parse_stmt(self, allow_top_level: bool = False) -> Stmt:
        if self.check(TokenType.FN) or self.check(TokenType.STRUCT) or self.check(TokenType.ENUM) or self.check(TokenType.INTERFACE) or self.check(TokenType.CLASS) or self.check(TokenType.IMPORT):
            if not allow_top_level:
                tok = self.at()
                raise ParserError(
                    message=f"Top-level declaration '{tok.value}' is not allowed inside a block",
                    line=tok.line,
                    col=tok.col,
                    file=self.file,
                    code="W0006",
                )
        if self.check(TokenType.FN):
            return self.parse_fn_decl()
        if self.check(TokenType.LET):
            return self.parse_let_decl()
        if self.check(TokenType.STRUCT):
            return self.parse_struct_decl()
        if self.check(TokenType.ENUM):
            return self.parse_enum_decl()
        if self.check(TokenType.INTERFACE):
            return self.parse_interface_decl()
        if self.check(TokenType.CLASS):
            return self.parse_class_decl()
        if self.check(TokenType.IMPORT):
            return self.parse_import_decl()
        if self.check(TokenType.WHILE):
            return self.parse_while_stmt()
        if self.check(TokenType.FOR):
            return self.parse_for_stmt()
        if self.check(TokenType.RETURN):
            return self.parse_return_stmt()
        if self.check(TokenType.BREAK):
            tok = self.advance()
            return BreakStmt(line=tok.line, col=tok.col)
        if self.check(TokenType.CONTINUE):
            tok = self.advance()
            return ContinueStmt(line=tok.line, col=tok.col)

        # Expression statement (including if/match used as statement)
        expr = self.parse_expr()
        return ExprStmt(expr=expr, line=expr.line, col=expr.col)

    def _parse_param_list(self, allow_receiver: bool = False) -> List[Param]:
        params: List[Param] = []
        if not self.check(TokenType.RPAREN):
            first = True
            while True:
                if first and allow_receiver and (
                    self.check(TokenType.THIS)
                    or (self.check(TokenType.IDENTIFIER) and self.at().value == "self" and self.peek(1).type != TokenType.COLON)
                ):
                    self.advance()
                    first = False
                    if self.match(TokenType.COMMA):
                        if self.check(TokenType.RPAREN):
                            break
                        continue
                    else:
                        break
                first = False
                p_name = self.expect(TokenType.IDENTIFIER, code="P002", msg="Expected parameter name")
                self.expect(TokenType.COLON, code="P002", msg="Expected ':' after parameter name")
                p_type = self.parse_type()
                params.append(Param(p_name.value, p_type, line=p_name.line, col=p_name.col))
                if not self.match(TokenType.COMMA) or self.check(TokenType.RPAREN):
                    break
        return params

    def parse_fn_decl(self) -> FnDecl:
        start_tok = self.expect(TokenType.FN, code="P004", msg="Expected 'fn'")
        name_tok = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected function name after 'fn'")
        self.expect(TokenType.LPAREN, code="P002", msg="Expected '(' after function name")
        params = self._parse_param_list(allow_receiver=False)
        self.expect(TokenType.RPAREN, code="P002", msg="Expected ')' after parameters")

        # Return type: defaults to unit if omitted
        return_type = NamedType("unit", line=name_tok.line, col=name_tok.col)
        if self.match(TokenType.ARROW):
            return_type = self.parse_type()

        body = self.parse_block()
        return FnDecl(name=name_tok.value, params=params, return_type=return_type, body=body, line=start_tok.line, col=start_tok.col)

    def parse_interface_decl(self) -> InterfaceDecl:
        start_tok = self.expect(TokenType.INTERFACE, code="P004", msg="Expected 'interface'")
        name_tok = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected interface name")
        self.expect(TokenType.LBRACE, code="P002", msg="Expected '{' to start interface body")

        methods: List[InterfaceMethod] = []
        while not self.check(TokenType.RBRACE) and not self.is_at_end():
            self.match(TokenType.PUBLIC)
            fn_tok = self.expect(TokenType.FN, code="P004", msg="Expected 'fn' in interface method declaration")
            m_name = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected method name after 'fn'")
            self.expect(TokenType.LPAREN, code="P002", msg="Expected '(' after interface method name")
            params = self._parse_param_list(allow_receiver=True)
            self.expect(TokenType.RPAREN, code="P002", msg="Expected ')' after interface method parameters")
            ret_type = NamedType("unit", line=m_name.line, col=m_name.col)
            if self.match(TokenType.ARROW):
                ret_type = self.parse_type()
            methods.append(InterfaceMethod(name=m_name.value, params=params, return_type=ret_type, line=fn_tok.line, col=fn_tok.col))

        self.expect(TokenType.RBRACE, code="P007", msg="Unterminated interface body, expected '}'")
        return InterfaceDecl(name=name_tok.value, methods=methods, line=start_tok.line, col=start_tok.col)

    def parse_class_decl(self) -> ClassDecl:
        start_tok = self.expect(TokenType.CLASS, code="P004", msg="Expected 'class'")
        name_tok = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected class name")

        superclass: Optional[str] = None
        if self.match(TokenType.EXTENDS):
            sup_tok = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected superclass name after 'extends'")
            superclass = sup_tok.value

        interfaces: List[str] = []
        if self.match(TokenType.IMPLEMENTS):
            first_intf = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected interface name after 'implements'")
            interfaces.append(first_intf.value)
            while self.match(TokenType.COMMA):
                next_intf = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected interface name after ','")
                interfaces.append(next_intf.value)

        self.expect(TokenType.LBRACE, code="P002", msg="Expected '{' to start class body")

        fields: List[ClassField] = []
        methods: List[MethodDecl] = []

        while not self.check(TokenType.RBRACE) and not self.is_at_end():
            is_public = True
            if self.match(TokenType.PUBLIC):
                is_public = True
            elif self.match(TokenType.PRIVATE):
                is_public = False

            if self.check(TokenType.FN):
                fn_tok = self.advance()
                m_name = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected method name after 'fn'")
                self.expect(TokenType.LPAREN, code="P002", msg="Expected '(' after method name")
                params = self._parse_param_list(allow_receiver=True)
                self.expect(TokenType.RPAREN, code="P002", msg="Expected ')' after method parameters")
                ret_type = NamedType("unit", line=m_name.line, col=m_name.col)
                if self.match(TokenType.ARROW):
                    ret_type = self.parse_type()
                body = self.parse_block()
                methods.append(
                    MethodDecl(
                        name=m_name.value,
                        params=params,
                        return_type=ret_type,
                        body=body,
                        is_public=is_public,
                        line=fn_tok.line,
                        col=fn_tok.col,
                    )
                )
            else:
                f_name = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected class field or method declaration")
                self.expect(TokenType.COLON, code="P004", msg="Expected ':' after class field name")
                f_type = self.parse_type()
                fields.append(ClassField(name=f_name.value, type_ann=f_type, is_public=is_public, line=f_name.line, col=f_name.col))
                self.match(TokenType.COMMA)

        self.expect(TokenType.RBRACE, code="P007", msg="Unterminated class body, expected '}'")
        return ClassDecl(
            name=name_tok.value,
            superclass=superclass,
            interfaces=interfaces,
            fields=fields,
            methods=methods,
            line=start_tok.line,
            col=start_tok.col,
        )

    def parse_let_decl(self) -> LetDecl:
        start_tok = self.expect(TokenType.LET, code="P004", msg="Expected 'let'")
        is_mut = self.match(TokenType.MUT)

        name_tok = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected variable name after 'let'")
        type_ann: Optional[TypeNode] = None
        if self.match(TokenType.COLON):
            type_ann = self.parse_type()

        self.expect(TokenType.ASSIGN, code="P004", msg="Expected '=' after variable declaration")
        initializer = self.parse_expr()

        return LetDecl(name=name_tok.value, is_mut=is_mut, type_ann=type_ann, initializer=initializer, line=start_tok.line, col=start_tok.col)

    def parse_struct_decl(self) -> StructDecl:
        start_tok = self.expect(TokenType.STRUCT, code="P004", msg="Expected 'struct'")
        name_tok = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected struct name")
        self.expect(TokenType.LBRACE, code="P002", msg="Expected '{' to start struct body")

        fields: List[StructField] = []
        while not self.check(TokenType.RBRACE) and not self.is_at_end():
            f_name = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected struct field name")
            self.expect(TokenType.COLON, code="P004", msg="Expected ':' after struct field name")
            f_type = self.parse_type()
            fields.append(StructField(f_name.value, f_type, line=f_name.line, col=f_name.col))
            self.match(TokenType.COMMA)

        self.expect(TokenType.RBRACE, code="P007", msg="Unterminated struct body, expected '}'")
        return StructDecl(name=name_tok.value, fields=fields, line=start_tok.line, col=start_tok.col)

    def parse_enum_decl(self) -> EnumDecl:
        start_tok = self.expect(TokenType.ENUM, code="P004", msg="Expected 'enum'")
        name_tok = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected enum name")
        self.expect(TokenType.LBRACE, code="P002", msg="Expected '{' to start enum body")

        variants: List[str] = []
        while not self.check(TokenType.RBRACE) and not self.is_at_end():
            v_tok = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected enum variant identifier")
            variants.append(v_tok.value)
            self.match(TokenType.COMMA)

        self.expect(TokenType.RBRACE, code="P007", msg="Unterminated enum body, expected '}'")
        return EnumDecl(name=name_tok.value, variants=variants, line=start_tok.line, col=start_tok.col)

    def parse_import_decl(self) -> ImportDecl:
        start_tok = self.expect(TokenType.IMPORT, code="P004", msg="Expected 'import'")
        path_tok = self.expect(TokenType.STR, code="P004", msg="Expected string path for import")

        # Derive namespace from filename (e.g. "lexer.w" -> "lexer")
        raw_path = str(path_tok.value)
        base = os.path.basename(raw_path)
        namespace = base.split(".")[0] if "." in base else base

        return ImportDecl(path=raw_path, namespace=namespace, line=start_tok.line, col=start_tok.col)

    def parse_while_stmt(self) -> WhileStmt:
        start_tok = self.expect(TokenType.WHILE, code="P004", msg="Expected 'while'")
        condition = self.parse_expr(allow_struct_init=False)
        body = self.parse_block()
        return WhileStmt(condition=condition, body=body, line=start_tok.line, col=start_tok.col)

    def parse_for_stmt(self) -> ForStmt:
        start_tok = self.expect(TokenType.FOR, code="P004", msg="Expected 'for'")
        pattern = self.parse_pattern()
        if not isinstance(pattern, (IdentifierPattern, TuplePattern)):
            raise ParserError(
                message="For loop binding must be an identifier or tuple pattern",
                line=pattern.line,
                col=pattern.col,
                file=self.file,
                code="W0006",
            )
        self.expect(TokenType.IN, code="P004", msg="Expected 'in' after for loop pattern")
        iterable = self.parse_expr(allow_struct_init=False)
        body = self.parse_block()
        return ForStmt(pattern=pattern, iterable=iterable, body=body, line=start_tok.line, col=start_tok.col)

    def parse_return_stmt(self) -> ReturnStmt:
        start_tok = self.expect(TokenType.RETURN, code="P004", msg="Expected 'return'")
        if self.check(TokenType.RBRACE) or self.is_at_end():
            return ReturnStmt(value=None, line=start_tok.line, col=start_tok.col)
        val = self.parse_expr()
        return ReturnStmt(value=val, line=start_tok.line, col=start_tok.col)

    def parse_block(self) -> Block:
        start_tok = self.expect(TokenType.LBRACE, code="P002", msg="Expected '{' to start block")
        statements: List[Stmt] = []
        tail_expr: Optional[Expr] = None

        while not self.check(TokenType.RBRACE) and not self.is_at_end():
            stmt = self.parse_stmt()
            statements.append(stmt)

        self.expect(TokenType.RBRACE, code="P007", msg="Unterminated block, expected '}'")

        # If the last statement is an ExprStmt, it serves as the tail expression of the block
        if statements and isinstance(statements[-1], ExprStmt):
            tail_expr = statements.pop().expr

        return Block(statements=statements, tail_expr=tail_expr, line=start_tok.line, col=start_tok.col)


    # ==========================================
    # Expression Parsing (Pratt Parser)
    # ==========================================

    def parse_expr(self, min_prec: int = 0, allow_struct_init: bool = True) -> Expr:
        left = self.parse_prefix_expr(allow_struct_init=allow_struct_init)

        # Postfix and Infix loop
        while True:
            # 1. Postfix operators (Calls, Member access, Indexing, Postfix '?')
            while True:
                if self.check(TokenType.LPAREN):
                    # Call expression
                    paren = self.advance()
                    args: List[Expr] = []
                    if not self.check(TokenType.RPAREN):
                        args.append(self.parse_expr())
                        while self.match(TokenType.COMMA):
                            if self.check(TokenType.RPAREN):
                                break
                            args.append(self.parse_expr())
                    self.expect(TokenType.RPAREN, code="P002", msg="Expected ')' after call arguments")
                    left = CallExpr(callee=left, args=args, line=paren.line, col=paren.col)

                elif self.check(TokenType.DOT):
                    # Member access
                    dot = self.advance()
                    prop_tok = self.expect(TokenType.IDENTIFIER, code="P002", msg="Expected property name after '.'")
                    left = MemberExpr(object=left, property=prop_tok.value, line=dot.line, col=dot.col)

                elif self.check(TokenType.LBRACKET):
                    # Indexing
                    bracket = self.advance()
                    index_expr = self.parse_expr()
                    self.expect(TokenType.RBRACKET, code="P002", msg="Expected ']' after index")
                    left = IndexExpr(object=left, index=index_expr, line=bracket.line, col=bracket.col)

                elif self.check(TokenType.QUESTION):
                    # Postfix try / unwrap
                    q_tok = self.advance()
                    left = PostfixTryExpr(operand=left, line=q_tok.line, col=q_tok.col)

                elif self.check(TokenType.ELSE):
                    # In-place error/optional handling: expr else err { ... } or expr else { ... }
                    else_tok = self.advance()
                    err_name: Optional[str] = None
                    if self.check(TokenType.IDENTIFIER):
                        err_tok = self.advance()
                        err_name = err_tok.value
                    handler_block = self.parse_block()
                    left = ElseErrExpr(operand=left, err_name=err_name, handler=handler_block, line=else_tok.line, col=else_tok.col)

                else:
                    break


            # 2. Infix operators check
            op_tok = self.at()
            prec = PRECEDENCE.get(op_tok.type, 0)
            if prec <= min_prec:
                break

            self.advance()  # consume operator token

            # Right associativity for assignment (=) and coalesce (??)
            next_min_prec = prec - 1 if op_tok.type in (TokenType.ASSIGN, TokenType.QUESTION_QUESTION) else prec
            right = self.parse_expr(min_prec=next_min_prec, allow_struct_init=allow_struct_init)


            if op_tok.type == TokenType.ASSIGN:
                # Target validation
                if not isinstance(left, (IdentExpr, IndexExpr, MemberExpr)):
                    raise ParserError(
                        message=f"Invalid assignment target '{left.__class__.__name__}'",
                        line=op_tok.line,
                        col=op_tok.col,
                        file=self.file,
                        code="P005"
                    )
                left = AssignmentExpr(target=left, value=right, line=op_tok.line, col=op_tok.col)

            elif op_tok.type == TokenType.QUESTION_QUESTION:
                left = CoalesceExpr(left=left, right=right, line=op_tok.line, col=op_tok.col)

            elif op_tok.type in (TokenType.DOT_DOT, TokenType.DOT_DOT_EQ):
                inclusive = (op_tok.type == TokenType.DOT_DOT_EQ)
                left = RangeExpr(start=left, end=right, inclusive=inclusive, line=op_tok.line, col=op_tok.col)

            else:
                left = BinaryExpr(left=left, op=op_tok.value, right=right, line=op_tok.line, col=op_tok.col)

        return left

    def parse_prefix_expr(self, allow_struct_init: bool = True) -> Expr:
        token = self.at()

        # Literals
        if self.match(TokenType.INT):
            return IntLiteral(value=token.value, line=token.line, col=token.col)

        if self.match(TokenType.FLOAT):
            return FloatLiteral(value=token.value, line=token.line, col=token.col)

        if self.match(TokenType.STR):
            return StringLiteral(value=token.value, line=token.line, col=token.col)

        if self.match(TokenType.TRUE):
            return BoolLiteral(value=True, line=token.line, col=token.col)

        if self.match(TokenType.FALSE):
            return BoolLiteral(value=False, line=token.line, col=token.col)

        if self.match(TokenType.NONE):
            return NoneLiteral(line=token.line, col=token.col)

        if self.match(TokenType.THIS):
            return ThisExpr(line=token.line, col=token.col)

        if self.match(TokenType.SUPER):
            return SuperExpr(line=token.line, col=token.col)

        if self.match(TokenType.NEW):
            cls_tok = self.expect(TokenType.IDENTIFIER, code="P004", msg="Expected class name after 'new'")
            self.expect(TokenType.LPAREN, code="P002", msg="Expected '(' after class name in 'new' expression")
            args: List[Expr] = []
            if not self.check(TokenType.RPAREN):
                args.append(self.parse_expr())
                while self.match(TokenType.COMMA):
                    if self.check(TokenType.RPAREN):
                        break
                    args.append(self.parse_expr())
            self.expect(TokenType.RPAREN, code="P002", msg="Expected ')' after 'new' arguments")
            return NewExpr(class_name=cls_tok.value, args=args, line=token.line, col=token.col)

        # Identifiers & Named Struct Initializations
        if self.match(TokenType.IDENTIFIER):
            ident_name = token.value

            # Check if this is a Struct Initialization: Identifier { field: val, ... }
            if allow_struct_init and self.check(TokenType.LBRACE):
                # Disambiguate struct init from block: next must be IDENTIFIER followed by COLON, or empty RBRACE
                if self.peek(1).type == TokenType.RBRACE or (self.peek(1).type == TokenType.IDENTIFIER and self.peek(2).type == TokenType.COLON):
                    self.advance()  # consume '{'
                    fields: List[FieldInit] = []
                    while not self.check(TokenType.RBRACE) and not self.is_at_end():
                        f_tok = self.expect(TokenType.IDENTIFIER, code="P002", msg="Expected struct field name")
                        self.expect(TokenType.COLON, code="P002", msg="Expected ':' after struct field name")
                        f_val = self.parse_expr()
                        fields.append(FieldInit(name=f_tok.value, value=f_val, line=f_tok.line, col=f_tok.col))
                        self.match(TokenType.COMMA)
                    self.expect(TokenType.RBRACE, code="P007", msg="Unterminated struct initializer, expected '}'")
                    return StructInitExpr(struct_name=ident_name, fields=fields, line=token.line, col=token.col)

            return IdentExpr(name=ident_name, line=token.line, col=token.col)

        # Unary operations: '-' and 'not'
        if self.match(TokenType.MINUS, TokenType.NOT):
            operand = self.parse_expr(min_prec=8, allow_struct_init=allow_struct_init)
            return UnaryExpr(op=token.value, operand=operand, line=token.line, col=token.col)

        # Parenthesized expressions & Tuples
        if self.match(TokenType.LPAREN):
            if self.match(TokenType.RPAREN):
                return TupleExpr(elements=[], line=token.line, col=token.col)

            first_expr = self.parse_expr()
            if self.match(TokenType.COMMA):
                elements: List[Expr] = [first_expr]
                if not self.check(TokenType.RPAREN):
                    elements.append(self.parse_expr())
                    while self.match(TokenType.COMMA):
                        if self.check(TokenType.RPAREN):
                            break
                        elements.append(self.parse_expr())
                self.expect(TokenType.RPAREN, code="P002", msg="Expected ')' after tuple elements")
                return TupleExpr(elements=elements, line=token.line, col=token.col)

            self.expect(TokenType.RPAREN, code="P002", msg="Expected ')' after expression")
            return first_expr

        # List Literals
        if self.match(TokenType.LBRACKET):
            elements: List[Expr] = []
            if not self.check(TokenType.RBRACKET):
                elements.append(self.parse_expr())
                while self.match(TokenType.COMMA):
                    if self.check(TokenType.RBRACKET):
                        break
                    elements.append(self.parse_expr())
            self.expect(TokenType.RBRACKET, code="P002", msg="Expected ']' after list elements")
            return ListExpr(elements=elements, line=token.line, col=token.col)

        # Dict Literals: { key: value, ... }
        if self.match(TokenType.LBRACE):
            entries: List[DictEntry] = []
            if not self.check(TokenType.RBRACE):
                k = self.parse_expr()
                self.expect(TokenType.COLON, code="P002", msg="Expected ':' after dict key")
                v = self.parse_expr()
                entries.append(DictEntry(key=k, value=v, line=k.line, col=k.col))
                while self.match(TokenType.COMMA):
                    if self.check(TokenType.RBRACE):
                        break
                    k = self.parse_expr()
                    self.expect(TokenType.COLON, code="P002", msg="Expected ':' after dict key")
                    v = self.parse_expr()
                    entries.append(DictEntry(key=k, value=v, line=k.line, col=k.col))
            self.expect(TokenType.RBRACE, code="P007", msg="Unterminated dict literal, expected '}'")
            return DictExpr(entries=entries, line=token.line, col=token.col)


        # Control flow expressions: 'if' and 'match'
        if self.check(TokenType.IF):
            return self.parse_if_expr()

        if self.check(TokenType.MATCH):
            return self.parse_match_expr()

        raise ParserError(
            message=f"Unexpected token '{token.type.name}' in expression",
            line=token.line,
            col=token.col,
            file=self.file,
            code="P001"
        )

    def parse_if_expr(self) -> IfExpr:
        start_tok = self.expect(TokenType.IF, code="P004", msg="Expected 'if'")
        condition = self.parse_expr(allow_struct_init=False)
        then_branch = self.parse_block()

        elif_branches: List[ElifBranch] = []
        while self.match(TokenType.ELIF):
            e_tok = self.tokens[self.pos - 1]
            elif_cond = self.parse_expr(allow_struct_init=False)
            elif_body = self.parse_block()
            elif_branches.append(ElifBranch(condition=elif_cond, body=elif_body, line=e_tok.line, col=e_tok.col))

        else_branch: Optional[Block] = None
        if self.match(TokenType.ELSE):
            else_branch = self.parse_block()

        return IfExpr(
            condition=condition,
            then_branch=then_branch,
            elif_branches=elif_branches,
            else_branch=else_branch,
            line=start_tok.line,
            col=start_tok.col
        )

    def parse_match_expr(self) -> MatchExpr:
        start_tok = self.expect(TokenType.MATCH, code="P004", msg="Expected 'match'")
        subject = self.parse_expr(allow_struct_init=False)
        self.expect(TokenType.LBRACE, code="P002", msg="Expected '{' after match subject")

        arms: List[MatchArm] = []
        while not self.check(TokenType.RBRACE) and not self.is_at_end():
            arm_tok = self.at()
            pattern: Pattern
            if self.match(TokenType.ELSE):
                pattern = WildcardPattern(line=arm_tok.line, col=arm_tok.col)
            else:
                pattern = self.parse_pattern()

            self.expect(TokenType.FAT_ARROW, code="P002", msg="Expected '=>' after match pattern")

            body: Block
            if self.check(TokenType.LBRACE):
                body = self.parse_block()
            else:
                # Single expression arm
                expr = self.parse_expr()
                body = Block(statements=[], tail_expr=expr, line=expr.line, col=expr.col)

            self.match(TokenType.COMMA)
            arms.append(MatchArm(pattern=pattern, body=body, line=arm_tok.line, col=arm_tok.col))

        self.expect(TokenType.RBRACE, code="P007", msg="Unterminated match body, expected '}'")
        return MatchExpr(subject=subject, arms=arms, line=start_tok.line, col=start_tok.col)