from __future__ import annotations

from dataclasses import dataclass

from loxygen.lox_token import Token


@dataclass(frozen=True, slots=True)
class Expr:
    def accept(self, visitor):
        pass


@dataclass(frozen=True, slots=True)
class Assign(Expr):
    name: Token
    value: Expr

    def accept(self, visitor):
        return visitor.visit_assign_expr(self)


@dataclass(frozen=True, slots=True)
class Binary(Expr):
    left: Expr
    operator: Token
    right: Expr

    def accept(self, visitor):
        return visitor.visit_binary_expr(self)


@dataclass(frozen=True, slots=True)
class Call(Expr):
    callee: Expr
    paren: Token
    arguments: list[Expr]

    def accept(self, visitor):
        return visitor.visit_call_expr(self)


@dataclass(frozen=True, slots=True)
class Get(Expr):
    object: Expr
    name: Token

    def accept(self, visitor):
        return visitor.visit_get_expr(self)


@dataclass(frozen=True, slots=True)
class Grouping(Expr):
    expression: Expr

    def accept(self, visitor):
        return visitor.visit_grouping_expr(self)


@dataclass(frozen=True, slots=True)
class Literal(Expr):
    value: object

    def accept(self, visitor):
        return visitor.visit_literal_expr(self)


@dataclass(frozen=True, slots=True)
class Logical(Expr):
    left: Expr
    operator: Token
    right: Expr

    def accept(self, visitor):
        return visitor.visit_logical_expr(self)


@dataclass(frozen=True, slots=True)
class Set(Expr):
    object: Expr
    name: Token
    value: Expr

    def accept(self, visitor):
        return visitor.visit_set_expr(self)


@dataclass(frozen=True, slots=True)
class Super(Expr):
    keyword: Token
    method: Token

    def accept(self, visitor):
        return visitor.visit_super_expr(self)


@dataclass(frozen=True, slots=True)
class This(Expr):
    keyword: Token

    def accept(self, visitor):
        return visitor.visit_this_expr(self)


@dataclass(frozen=True, slots=True)
class Unary(Expr):
    operator: Token
    right: Expr

    def accept(self, visitor):
        return visitor.visit_unary_expr(self)


@dataclass(frozen=True, slots=True)
class Variable(Expr):
    name: Token

    def accept(self, visitor):
        return visitor.visit_variable_expr(self)
