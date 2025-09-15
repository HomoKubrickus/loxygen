from __future__ import annotations

from enum import Enum
from enum import auto

from loxygen import expr
from loxygen import stmt
from loxygen.interpreter import Interpreter
from loxygen.lox_token import Token


class FunctionType(Enum):
    NONE = auto()
    FUNCTION = auto()
    INITIALIZER = auto()
    METHOD = auto()


class ClassType(Enum):
    NONE = auto()
    CLASS = auto()
    SUBCLASS = auto()


class Resolver:
    def __init__(self, interpreter: Interpreter):
        self.interpreter = interpreter
        self.scopes: list[dict] = []
        self.current_function = FunctionType.NONE
        self.current_class = ClassType.NONE
        self.errors: list[tuple[Token, str]] = []

    def resolve(self, *statements: expr.Expr | stmt.Stmt):
        for statement in statements:
            statement.accept(self)

    def resolve_function(self, function: stmt.Function, function_type: FunctionType):
        enclosing_function = self.current_function
        self.current_function = function_type
        self.begin_scope()
        for param in function.params:
            self.declare(param)
            self.define(param)

        self.resolve(*function.body)
        self.end_scope()
        self.current_function = enclosing_function

    def scope(self):
        try:
            self.scopes.append({})
            yield
        finally:
            self.scopes.pop()

    def begin_scope(self):
        self.scopes.append({})

    def end_scope(self):
        self.scopes.pop()

    def declare(self, name: Token):
        if self.scopes:
            scope = self.scopes[-1]
            if name.lexeme in scope:
                self.errors.append(
                    (
                        name,
                        "Already a variable with this name in this scope.",
                    ),
                )
            scope[name.lexeme] = False

    def define(self, name: Token):
        if self.scopes:
            scope = self.scopes[-1]
            scope[name.lexeme] = True

    def resolve_local(self, expression: expr.Expr, name: Token):
        for idx, scope in enumerate(reversed(self.scopes)):
            if name.lexeme in scope:
                self.interpreter.resolve(expression, idx)
                break

    def visit_block_stmt(self, stmt: stmt.Block):
        self.begin_scope()
        self.resolve(*stmt.statements)
        self.end_scope()

    def visit_class_stmt(self, stmt: stmt.Class):
        enclosing_class = self.current_class
        self.current_class = ClassType.CLASS

        self.declare(stmt.name)
        self.define(stmt.name)

        if stmt.superclass is not None and stmt.name.lexeme == stmt.superclass.name.lexeme:
            self.errors.append(
                (
                    stmt.superclass.name,
                    "A class can't inherit from itself.",
                ),
            )

        if stmt.superclass is not None:
            self.current_class = ClassType.SUBCLASS
            self.resolve(stmt.superclass)
            self.begin_scope()
            self.scopes[-1]["super"] = True

        self.begin_scope()
        self.scopes[-1]["this"] = True
        for method in stmt.methods:
            declaration = FunctionType.METHOD
            if method.name.lexeme == "init":
                declaration = FunctionType.INITIALIZER
            self.resolve_function(method, declaration)

        self.end_scope()
        if stmt.superclass is not None:
            self.end_scope()

        self.current_class = enclosing_class

    def visit_expression_stmt(self, stmt: stmt.Expression):
        self.resolve(stmt.expression)

    def visit_function_stmt(self, stmt: stmt.Function):
        self.declare(stmt.name)
        self.define(stmt.name)

        self.resolve_function(stmt, FunctionType.FUNCTION)

    def visit_if_stmt(self, stmt: stmt.If):
        self.resolve(stmt.condition)
        self.resolve(stmt.then_branch)
        if stmt.else_branch:
            self.resolve(stmt.else_branch)

    def visit_print_stmt(self, stmt: stmt.Print):
        self.resolve(stmt.expression)

    def visit_return_stmt(self, stmt: stmt.Return):
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

    def visit_var_stmt(self, stmt: stmt.Var):
        self.declare(stmt.name)
        if stmt.initializer is not None:
            self.resolve(stmt.initializer)
        self.define(stmt.name)

    def visit_while_stmt(self, stmt: stmt.While):
        self.resolve(stmt.condition)
        self.resolve(stmt.body)

    def visit_assign_expr(self, expression: expr.Assign):
        self.resolve(expression.value)
        self.resolve_local(expression, expression.name)

    def visit_binary_expr(self, expression: expr.Binary):
        self.resolve(expression.left)
        self.resolve(expression.right)

    def visit_call_expr(self, expression: expr.Call):
        self.resolve(expression.callee)
        for argument in expression.arguments:
            self.resolve(argument)

    def visit_get_expr(self, expression: expr.Get):
        self.resolve(expression.object)

    def visit_grouping_expr(self, expression: expr.Grouping):
        self.resolve(expression.expression)

    def visit_literal_expr(self, expression: expr.Literal):
        pass

    def visit_logical_expr(self, expression: expr.Logical):
        self.resolve(expression.left)
        self.resolve(expression.right)

    def visit_set_expr(self, expression: expr.Set):
        self.resolve(expression.value)
        self.resolve(expression.object)

    def visit_super_expr(self, expression: expr.Super):
        if self.current_class == ClassType.NONE:
            self.errors.append(
                (
                    expression.keyword,
                    "Can't use 'super' outside of a class.",
                ),
            )
        elif self.current_class != ClassType.SUBCLASS:
            self.errors.append(
                (
                    expression.keyword,
                    "Can't use 'super' in a class with no superclass.",
                ),
            )

        self.resolve_local(expression, expression.keyword)

    def visit_this_expr(self, expression: expr.This):
        if self.current_class == ClassType.NONE:
            self.errors.append(
                (
                    expression.keyword,
                    "Can't use 'this' outside of a class.",
                ),
            )
        self.resolve_local(expression, expression.keyword)

    def visit_unary_expr(self, expression: expr.Unary):
        self.resolve(expression.right)

    def visit_variable_expr(self, expression: expr.Variable):
        if self.scopes and self.scopes[-1].get(expression.name.lexeme) is False:
            self.errors.append(
                (
                    expression.name,
                    "Can't read local variable in its own initializer.",
                ),
            )
        self.resolve_local(expression, expression.name)
