from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass

from loxygen.runtime import LoxObject
from loxygen.token import Token


class Visitor(ABC):
    @abstractmethod
    def visit_assign_expr(self, expr: Assign) -> LoxObject:
        pass

    @abstractmethod
    def visit_binary_expr(self, expr: Binary) -> LoxObject:
        pass

    @abstractmethod
    def visit_call_expr(self, expr: Call) -> LoxObject:
        pass

    @abstractmethod
    def visit_get_expr(self, expr: Get) -> LoxObject:
        pass

    @abstractmethod
    def visit_grouping_expr(self, expr: Grouping) -> LoxObject:
        pass

    @abstractmethod
    def visit_literal_expr(self, expr: Literal) -> LoxObject:
        pass

    @abstractmethod
    def visit_logical_expr(self, expr: Logical) -> LoxObject:
        pass

    @abstractmethod
    def visit_set_expr(self, expr: Set) -> LoxObject:
        pass

    @abstractmethod
    def visit_super_expr(self, expr: Super) -> LoxObject:
        pass

    @abstractmethod
    def visit_this_expr(self, expr: This) -> LoxObject:
        pass

    @abstractmethod
    def visit_unary_expr(self, expr: Unary) -> LoxObject:
        pass

    @abstractmethod
    def visit_variable_expr(self, expr: Variable) -> LoxObject:
        pass

    @abstractmethod
    def visit_block_stmt(self, stmt: Block) -> None:
        pass

    @abstractmethod
    def visit_expression_stmt(self, stmt: Expression) -> None:
        pass

    @abstractmethod
    def visit_function_stmt(self, stmt: Function) -> None:
        pass

    @abstractmethod
    def visit_class_stmt(self, stmt: Class) -> None:
        pass

    @abstractmethod
    def visit_if_stmt(self, stmt: If) -> None:
        pass

    @abstractmethod
    def visit_print_stmt(self, stmt: Print) -> None:
        pass

    @abstractmethod
    def visit_return_stmt(self, stmt: Return) -> None:
        pass

    @abstractmethod
    def visit_var_stmt(self, stmt: Var) -> None:
        pass

    @abstractmethod
    def visit_while_stmt(self, stmt: While) -> None:
        pass


@dataclass(frozen=True, slots=True)
class Expr:
    def accept(self, visitor: Visitor) -> LoxObject:
        pass


@dataclass(frozen=True, slots=True)
class Stmt:
    def accept(self, visitor: Visitor) -> None:
        pass


@dataclass(frozen=True, slots=True)
class Assign(Expr):
    name: Token
    value: Expr

    def accept(self, visitor: Visitor) -> LoxObject:
        return visitor.visit_assign_expr(self)


@dataclass(frozen=True, slots=True)
class Binary(Expr):
    left: Expr
    operator: Token
    right: Expr

    def accept(self, visitor: Visitor) -> LoxObject:
        return visitor.visit_binary_expr(self)


@dataclass(frozen=True, slots=True)
class Call(Expr):
    callee: Expr
    paren: Token
    arguments: list[Expr]

    def accept(self, visitor: Visitor) -> LoxObject:
        return visitor.visit_call_expr(self)


@dataclass(frozen=True, slots=True)
class Get(Expr):
    object: Expr
    name: Token

    def accept(self, visitor: Visitor) -> LoxObject:
        return visitor.visit_get_expr(self)


@dataclass(frozen=True, slots=True)
class Grouping(Expr):
    expr: Expr

    def accept(self, visitor: Visitor) -> LoxObject:
        return visitor.visit_grouping_expr(self)


@dataclass(frozen=True, slots=True)
class Literal(Expr):
    value: LoxObject

    def accept(self, visitor: Visitor) -> LoxObject:
        return visitor.visit_literal_expr(self)


@dataclass(frozen=True, slots=True)
class Logical(Expr):
    left: Expr
    operator: Token
    right: Expr

    def accept(self, visitor: Visitor) -> LoxObject:
        return visitor.visit_logical_expr(self)


@dataclass(frozen=True, slots=True)
class Set(Expr):
    object: Expr
    name: Token
    value: Expr

    def accept(self, visitor: Visitor) -> LoxObject:
        return visitor.visit_set_expr(self)


@dataclass(frozen=True, slots=True)
class Super(Expr):
    keyword: Token
    method: Token

    def accept(self, visitor: Visitor) -> LoxObject:
        return visitor.visit_super_expr(self)


@dataclass(frozen=True, slots=True)
class This(Expr):
    keyword: Token

    def accept(self, visitor: Visitor) -> LoxObject:
        return visitor.visit_this_expr(self)


@dataclass(frozen=True, slots=True)
class Unary(Expr):
    operator: Token
    right: Expr

    def accept(self, visitor: Visitor) -> LoxObject:
        return visitor.visit_unary_expr(self)


@dataclass(frozen=True, slots=True)
class Variable(Expr):
    name: Token

    def accept(self, visitor: Visitor) -> LoxObject:
        return visitor.visit_variable_expr(self)


@dataclass(frozen=True, slots=True)
class Block(Stmt):
    statements: list[Stmt]

    def accept(self, visitor: Visitor) -> None:
        return visitor.visit_block_stmt(self)


@dataclass(frozen=True, slots=True)
class Expression(Stmt):
    expr: Expr

    def accept(self, visitor: Visitor) -> None:
        return visitor.visit_expression_stmt(self)


@dataclass(frozen=True, slots=True)
class Function(Stmt):
    name: Token
    params: list[Token]
    body: list[Stmt]

    def accept(self, visitor: Visitor) -> None:
        return visitor.visit_function_stmt(self)


@dataclass(frozen=True, slots=True)
class Class(Stmt):
    name: Token
    superclass: Variable | None
    methods: list[Function]

    def accept(self, visitor: Visitor) -> None:
        return visitor.visit_class_stmt(self)


@dataclass(frozen=True, slots=True)
class If(Stmt):
    condition: Expr
    then_branch: Stmt
    else_branch: Stmt | None

    def accept(self, visitor: Visitor) -> None:
        return visitor.visit_if_stmt(self)


@dataclass(frozen=True, slots=True)
class Print(Stmt):
    expr: Expr

    def accept(self, visitor: Visitor) -> None:
        return visitor.visit_print_stmt(self)


@dataclass(frozen=True, slots=True)
class Return(Stmt):
    keyword: Token
    value: Expr | None

    def accept(self, visitor: Visitor) -> None:
        return visitor.visit_return_stmt(self)


@dataclass(frozen=True, slots=True)
class Var(Stmt):
    name: Token
    initializer: Expr | None

    def accept(self, visitor: Visitor) -> None:
        return visitor.visit_var_stmt(self)


@dataclass(frozen=True, slots=True)
class While(Stmt):
    condition: Expr
    body: Stmt

    def accept(self, visitor: Visitor) -> None:
        return visitor.visit_while_stmt(self)
