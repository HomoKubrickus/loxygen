from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from enum import Enum
from enum import auto

from loxygen import nodes
from loxygen.interpreter import Interpreter
from loxygen.runtime import LoxObject
from loxygen.token import Token


class FunctionType(Enum):
    NONE = auto()
    FUNCTION = auto()
    INITIALIZER = auto()
    METHOD = auto()


class ClassType(Enum):
    NONE = auto()
    CLASS = auto()
    SUBCLASS = auto()


class Resolver(nodes.Visitor[LoxObject]):
    def __init__(self, interpreter: Interpreter):
        self.interpreter = interpreter
        self.scopes: list[dict[str, bool]] = []
        self.current_function = FunctionType.NONE
        self.current_class = ClassType.NONE
        self.errors: list[tuple[Token, str]] = []

    @property
    def current_scope(self) -> dict[str, bool]:
        return self.scopes[-1]

    def resolve(self, *statements: nodes.Expr | nodes.Stmt) -> None:
        for statement in statements:
            statement.accept(self)

    @contextmanager
    def scope(self) -> Iterator[None]:
        try:
            self.scopes.append({})
            yield
        finally:
            self.scopes.pop()

    def declare(self, name: Token) -> None:
        if self.scopes:
            if name.lexeme in self.current_scope:
                self.errors.append(
                    (
                        name,
                        "Already a variable with this name in this scope.",
                    ),
                )
            self.current_scope[name.lexeme] = False

    def define(self, name: Token) -> None:
        if self.scopes:
            self.current_scope[name.lexeme] = True

    def resolve_local(self, expr: nodes.Expr, name: Token) -> None:
        for idx, scope in enumerate(reversed(self.scopes)):
            if name.lexeme in scope:
                self.interpreter.resolve(expr, idx)
                break

    def resolve_function(self, function: nodes.Function, function_type: FunctionType) -> None:
        enclosing_function = self.current_function
        self.current_function = function_type
        with self.scope():
            for param in function.params:
                self.declare(param)
                self.define(param)
            self.resolve(*function.body)

        self.current_function = enclosing_function

    def resolve_class_body(self, stmt: nodes.Class) -> None:
        with self.scope():
            self.current_scope["this"] = True
            for method in stmt.methods:
                declaration = FunctionType.METHOD
                if method.name.lexeme == "init":
                    declaration = FunctionType.INITIALIZER
                self.resolve_function(method, declaration)

    def visit_block_stmt(self, stmt: nodes.Block) -> None:
        with self.scope():
            self.resolve(*stmt.statements)

    def visit_class_stmt(self, stmt: nodes.Class) -> None:
        enclosing_class = self.current_class
        self.current_class = ClassType.CLASS

        self.declare(stmt.name)
        self.define(stmt.name)

        if stmt.superclass is not None:
            if stmt.name.lexeme == stmt.superclass.name.lexeme:
                self.errors.append(
                    (
                        stmt.superclass.name,
                        "A class can't inherit from itself.",
                    ),
                )

            self.current_class = ClassType.SUBCLASS
            self.resolve(stmt.superclass)
            with self.scope():
                self.current_scope["super"] = True
                self.resolve_class_body(stmt)

        else:
            self.resolve_class_body(stmt)

        self.current_class = enclosing_class

    def visit_expression_stmt(self, stmt: nodes.Expression) -> None:
        self.resolve(stmt.expr)

    def visit_function_stmt(self, stmt: nodes.Function) -> None:
        self.declare(stmt.name)
        self.define(stmt.name)

        self.resolve_function(stmt, FunctionType.FUNCTION)

    def visit_if_stmt(self, stmt: nodes.If) -> None:
        self.resolve(stmt.condition)
        self.resolve(stmt.then_branch)
        if stmt.else_branch:
            self.resolve(stmt.else_branch)

    def visit_print_stmt(self, stmt: nodes.Print) -> None:
        self.resolve(stmt.expr)

    def visit_return_stmt(self, stmt: nodes.Return) -> None:
        if self.current_function == FunctionType.NONE:
            self.errors.append(
                (
                    stmt.keyword,
                    "Can't return from top-level code.",
                ),
            )
        if stmt.value is not None:
            if self.current_function == FunctionType.INITIALIZER:
                self.errors.append(
                    (
                        stmt.keyword,
                        "Can't return a value from an initializer.",
                    ),
                )
            self.resolve(stmt.value)

    def visit_var_stmt(self, stmt: nodes.Var) -> None:
        self.declare(stmt.name)
        if stmt.initializer is not None:
            self.resolve(stmt.initializer)
        self.define(stmt.name)

    def visit_while_stmt(self, stmt: nodes.While) -> None:
        self.resolve(stmt.condition)
        self.resolve(stmt.body)

    def visit_assign_expr(self, expr: nodes.Assign) -> None:
        self.resolve(expr.value)
        self.resolve_local(expr, expr.name)

    def visit_binary_expr(self, expr: nodes.Binary) -> None:
        self.resolve(expr.left)
        self.resolve(expr.right)

    def visit_call_expr(self, expr: nodes.Call) -> None:
        self.resolve(expr.callee)
        for argument in expr.arguments:
            self.resolve(argument)

    def visit_get_expr(self, expr: nodes.Get) -> None:
        self.resolve(expr.object)

    def visit_grouping_expr(self, expr: nodes.Grouping) -> None:
        self.resolve(expr.expr)

    def visit_literal_expr(self, expr: nodes.Literal) -> None:
        pass

    def visit_logical_expr(self, expr: nodes.Logical) -> None:
        self.resolve(expr.left)
        self.resolve(expr.right)

    def visit_set_expr(self, expr: nodes.Set) -> None:
        self.resolve(expr.value)
        self.resolve(expr.object)

    def visit_super_expr(self, expr: nodes.Super) -> None:
        if self.current_class == ClassType.NONE:
            self.errors.append(
                (
                    expr.keyword,
                    "Can't use 'super' outside of a class.",
                ),
            )
        elif self.current_class != ClassType.SUBCLASS:
            self.errors.append(
                (
                    expr.keyword,
                    "Can't use 'super' in a class with no superclass.",
                ),
            )

        self.resolve_local(expr, expr.keyword)

    def visit_this_expr(self, expr: nodes.This) -> None:
        if self.current_class == ClassType.NONE:
            self.errors.append(
                (
                    expr.keyword,
                    "Can't use 'this' outside of a class.",
                ),
            )
        self.resolve_local(expr, expr.keyword)

    def visit_unary_expr(self, expr: nodes.Unary) -> None:
        self.resolve(expr.right)

    def visit_variable_expr(self, expr: nodes.Variable) -> None:
        if self.scopes and self.current_scope.get(expr.name.lexeme) is False:
            self.errors.append(
                (
                    expr.name,
                    "Can't read local variable in its own initializer.",
                ),
            )
        self.resolve_local(expr, expr.name)
