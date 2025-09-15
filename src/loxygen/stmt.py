from __future__ import annotations

from dataclasses import dataclass

from loxygen.expr import Expr
from loxygen.expr import Variable
from loxygen.lox_token import Token


@dataclass(frozen=True, slots=True)
class Stmt:
    def accept(self, visitor):
        pass


@dataclass(frozen=True, slots=True)
class Block(Stmt):
    statements: list[Stmt]

    def accept(self, visitor):
        return visitor.visit_block_stmt(self)


@dataclass(frozen=True, slots=True)
class Expression(Stmt):
    expression: Expr

    def accept(self, visitor):
        return visitor.visit_expression_stmt(self)


@dataclass(frozen=True, slots=True)
class Function(Stmt):
    name: Token
    params: list[Token]
    body: list[Stmt]

    def accept(self, visitor):
        return visitor.visit_function_stmt(self)


@dataclass(frozen=True, slots=True)
class Class(Stmt):
    name: Token
    superclass: Variable
    methods: list[Function]

    def accept(self, visitor):
        return visitor.visit_class_stmt(self)


@dataclass(frozen=True, slots=True)
class If(Stmt):
    condition: Expr
    then_branch: Stmt
    else_branch: Stmt

    def accept(self, visitor):
        return visitor.visit_if_stmt(self)


@dataclass(frozen=True, slots=True)
class Print(Stmt):
    expression: Expr

    def accept(self, visitor):
        return visitor.visit_print_stmt(self)


@dataclass(frozen=True, slots=True)
class Return(Stmt):
    keyword: Token
    value: Expr

    def accept(self, visitor):
        return visitor.visit_return_stmt(self)


@dataclass(frozen=True, slots=True)
class Var(Stmt):
    name: Token
    initializer: Expr

    def accept(self, visitor):
        return visitor.visit_var_stmt(self)


@dataclass(frozen=True, slots=True)
class While(Stmt):
    condition: Expr
    body: Stmt

    def accept(self, visitor):
        return visitor.visit_while_stmt(self)
