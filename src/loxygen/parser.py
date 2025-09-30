from __future__ import annotations

from loxygen import nodes
from loxygen.exceptions import LoxParseError
from loxygen.token import Token
from loxygen.token import TokenType

MAXIMUM_ARGS_NUMBER = 255


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.current = 0
        self.errors: list[tuple[Token, str]] = []

    def parse(self) -> list[nodes.Stmt]:
        statements: list[nodes.Stmt] = []
        while not self.is_at_end():
            if (declaration := self.declaration()) is not None:
                statements.append(declaration)
        return statements

    def expression(self) -> nodes.Expr:
        return self.assignment()

    def declaration(self) -> nodes.Stmt | None:
        try:
            if self.match(TokenType.CLASS):
                return self.class_declaration()
            if self.match(TokenType.FUN):
                return self.function("function")
            if self.match(TokenType.VAR):
                return self.var_declaration()
            return self.statement()
        except LoxParseError:
            self.synchronize()
            return None

    def class_declaration(self) -> nodes.Class:
        name = self.consume(TokenType.IDENTIFIER, "Expect class name.")

        superclass = None
        if self.match(TokenType.LESS):
            self.consume(TokenType.IDENTIFIER, "Expect superclass name.")
            superclass = nodes.Variable(self.previous())

        self.consume(TokenType.LEFT_BRACE, "Expect '{' before class body.")

        methods: list[nodes.Function] = []
        while not (self.check(TokenType.RIGHT_BRACE) or self.is_at_end()):
            methods.append(self.function("method"))

        self.consume(TokenType.RIGHT_BRACE, "Expect '}' after class body.")

        return nodes.Class(name, superclass, methods)

    def statement(self) -> nodes.Stmt:
        if self.match(TokenType.FOR):
            return self.for_statement()
        if self.match(TokenType.IF):
            return self.if_statement()
        if self.match(TokenType.PRINT):
            return self.print_statement()
        if self.match(TokenType.RETURN):
            return self.return_statement()
        if self.match(TokenType.WHILE):
            return self.while_statement()
        if self.match(TokenType.LEFT_BRACE):
            return nodes.Block(self.block())

        return self.expression_statement()

    def for_statement(self) -> nodes.Stmt:
        self.consume(TokenType.LEFT_PAREN, "Expect '(' after if.")

        initializer: nodes.Stmt | None
        if self.match(TokenType.SEMICOLON):
            initializer = None
        elif self.match(TokenType.VAR):
            initializer = self.var_declaration()
        else:
            initializer = self.expression_statement()

        condition = None if self.check(TokenType.SEMICOLON) else self.expression()
        self.consume(TokenType.SEMICOLON, "Expect ';' after loop condition.")

        increment = None if self.check(TokenType.RIGHT_PAREN) else self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expect ')' after for clauses.")

        body = self.statement()

        if increment is not None:
            body = nodes.Block([body, nodes.Expression(increment)])

        if condition is None:
            condition = nodes.Literal(True)
        body = nodes.While(condition, body)

        if initializer is not None:
            body = nodes.Block([initializer, body])

        return body

    def if_statement(self) -> nodes.If:
        self.consume(TokenType.LEFT_PAREN, "Expect '(' after if.")
        condition = self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expect ')' after if condition.")

        then_branch = self.statement()
        else_branch = self.statement() if self.match(TokenType.ELSE) else None

        return nodes.If(condition, then_branch, else_branch)

    def print_statement(self) -> nodes.Print:
        value = self.expression()
        self.consume(TokenType.SEMICOLON, "Expect ';' after value.")

        return nodes.Print(value)

    def return_statement(self) -> nodes.Return:
        keyword = self.previous()
        value = None if self.check(TokenType.SEMICOLON) else self.expression()
        self.consume(TokenType.SEMICOLON, "Expect ';' after return value.")

        return nodes.Return(keyword, value)

    def var_declaration(self) -> nodes.Var:
        name = self.consume(TokenType.IDENTIFIER, "Expect variable name.")

        initializer = None
        if self.match(TokenType.EQUAL):
            initializer = self.expression()

        self.consume(TokenType.SEMICOLON, "Expect ';' after expression.")
        return nodes.Var(name, initializer)

    def while_statement(self) -> nodes.While:
        self.consume(TokenType.LEFT_PAREN, "Expect '(' after if.")
        condition = self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expect ')' after if condition.")

        body = self.statement()

        return nodes.While(condition, body)

    def expression_statement(self) -> nodes.Expression:
        expr = self.expression()
        self.consume(TokenType.SEMICOLON, "Expect ';' after expression.")

        return nodes.Expression(expr)

    def function(self, kind: str) -> nodes.Function:
        name = self.consume(TokenType.IDENTIFIER, f"Expect {kind} name.")
        self.consume(TokenType.LEFT_PAREN, f"Expect '(' after {kind} name.")
        parameters: list[Token] = []
        if not self.check(TokenType.RIGHT_PAREN):
            while True:
                if len(parameters) >= MAXIMUM_ARGS_NUMBER:
                    self.error(
                        self.peek(),
                        f"Can't have more than {MAXIMUM_ARGS_NUMBER} parameters.",
                    )

                parameters.append(
                    self.consume(TokenType.IDENTIFIER, "Expect parameter name"),
                )
                if not self.match(TokenType.COMMA):
                    break

        self.consume(TokenType.RIGHT_PAREN, "Expect ')' after parameters.")
        self.consume(TokenType.LEFT_BRACE, f"Expect '{{' before {kind} body.")
        body = self.block()

        return nodes.Function(name, parameters, body)

    def block(self) -> list[nodes.Stmt]:
        statements: list[nodes.Stmt] = []
        while not (self.check(TokenType.RIGHT_BRACE) or self.is_at_end()):
            if (declaration := self.declaration()) is not None:
                statements.append(declaration)

        self.consume(TokenType.RIGHT_BRACE, "Expect '}' after expression.")

        return statements

    def assignment(self) -> nodes.Expr:
        expr = self.logical_or()
        if self.match(TokenType.EQUAL):
            equals = self.previous()
            value = self.assignment()
            if isinstance(expr, nodes.Variable):
                return nodes.Assign(expr.name, value)
            elif isinstance(expr, nodes.Get):
                return nodes.Set(expr.object, expr.name, value)
            self.error(equals, "Invalid assignment target.")
        return expr

    def logical_or(self) -> nodes.Expr:
        expr = self.logical_and()
        while self.match(TokenType.OR):
            operator = self.previous()
            right = self.logical_and()
            expr = nodes.Logical(expr, operator, right)

        return expr

    def logical_and(self) -> nodes.Expr:
        expr = self.equality()
        while self.match(TokenType.AND):
            operator = self.previous()
            right = self.equality()
            expr = nodes.Logical(expr, operator, right)

        return expr

    def equality(self) -> nodes.Expr:
        expr = self.comparison()
        while self.match(TokenType.BANG_EQUAL, TokenType.EQUAL_EQUAL):
            operator = self.previous()
            right = self.comparison()
            expr = nodes.Binary(expr, operator, right)

        return expr

    def comparison(self) -> nodes.Expr:
        expr = self.term()
        while self.match(
            TokenType.GREATER,
            TokenType.GREATER_EQUAL,
            TokenType.LESS,
            TokenType.LESS_EQUAL,
        ):
            operator = self.previous()
            right = self.term()
            expr = nodes.Binary(expr, operator, right)

        return expr

    def term(self) -> nodes.Expr:
        expr = self.factor()
        while self.match(TokenType.MINUS, TokenType.PLUS):
            operator = self.previous()
            right = self.factor()
            expr = nodes.Binary(expr, operator, right)

        return expr

    def factor(self) -> nodes.Expr:
        expr = self.unary()
        while self.match(TokenType.SLASH, TokenType.STAR):
            operator = self.previous()
            right = self.unary()
            expr = nodes.Binary(expr, operator, right)

        return expr

    def unary(self) -> nodes.Expr:
        if self.match(TokenType.BANG, TokenType.MINUS):
            operator = self.previous()
            right = self.unary()
            return nodes.Unary(operator, right)

        return self.call()

    def finish_call(self, callee: nodes.Expr) -> nodes.Call:
        arguments: list[nodes.Expr] = []
        if not self.check(TokenType.RIGHT_PAREN):
            while True:
                if len(arguments) >= MAXIMUM_ARGS_NUMBER:
                    self.error(
                        self.peek(),
                        f"Can't have more than {MAXIMUM_ARGS_NUMBER} arguments.",
                    )
                arguments.append(self.expression())
                if not self.match(TokenType.COMMA):
                    break

        paren = self.consume(TokenType.RIGHT_PAREN, "Expect ')' after arguments.")

        return nodes.Call(callee, paren, arguments)

    def call(self) -> nodes.Expr:
        expr = self.primary()
        while True:
            if self.match(TokenType.LEFT_PAREN):
                expr = self.finish_call(expr)
            elif self.match(TokenType.DOT):
                name = self.consume(
                    TokenType.IDENTIFIER,
                    "Expect property name after '.'.",
                )
                expr = nodes.Get(expr, name)
            else:
                break

        return expr

    def primary(self) -> nodes.Expr:
        if self.match(TokenType.TRUE):
            return nodes.Literal(True)
        if self.match(TokenType.FALSE):
            return nodes.Literal(False)
        if self.match(TokenType.NIL):
            return nodes.Literal(None)
        if self.match(TokenType.NUMBER, TokenType.STRING):
            return nodes.Literal(self.previous().literal)
        if self.match(TokenType.THIS):
            return nodes.This(self.previous())
        if self.match(TokenType.IDENTIFIER):
            return nodes.Variable(self.previous())
        if self.match(TokenType.SUPER):
            keyword = self.previous()
            self.consume(TokenType.DOT, "Expect '.' after 'super'.")
            method = self.consume(TokenType.IDENTIFIER, "Expect superclass method name.")
            return nodes.Super(keyword, method)
        if self.match(TokenType.LEFT_PAREN):
            expr = self.expression()
            self.consume(TokenType.RIGHT_PAREN, "Expect ')' after expression.")
            return nodes.Grouping(expr)

        raise self.error(self.peek(), "Expect expression.")

    def match(self, *types: TokenType) -> bool:
        if check := self.check(*types):
            self.advance()
        return check

    def consume(self, token_type: TokenType, message: str) -> Token:
        if self.check(token_type):
            return self.advance()
        raise self.error(self.peek(), message)

    def check(self, *types: TokenType) -> bool:
        if self.is_at_end():
            return False
        return self.peek().type in types

    def advance(self) -> Token:
        if not self.is_at_end():
            self.current += 1
        return self.previous()

    def is_at_end(self) -> bool:
        return self.peek().type == TokenType.EOF

    def peek(self) -> Token:
        return self.tokens[self.current]

    def previous(self) -> Token:
        return self.tokens[self.current - 1]

    def error(self, token: Token, message: str) -> LoxParseError:
        self.errors.append((token, message))
        return LoxParseError(message, token)

    def synchronize(self) -> None:
        self.advance()
        while not self.is_at_end():
            anchors = (
                TokenType.CLASS,
                TokenType.FUN,
                TokenType.VAR,
                TokenType.FOR,
                TokenType.IF,
                TokenType.WHILE,
                TokenType.PRINT,
                TokenType.RETURN,
            )
            if self.previous().type == TokenType.SEMICOLON or self.check(*anchors):
                return
            self.advance()
