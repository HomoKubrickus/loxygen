from __future__ import annotations

from loxygen import nodes
from loxygen.environment import Environment
from loxygen.exceptions import LoxRunTimeError
from loxygen.runtime import Clock
from loxygen.runtime import LoxCallable
from loxygen.runtime import LoxClass
from loxygen.runtime import LoxFunction
from loxygen.runtime import LoxInstance
from loxygen.runtime import LoxObject
from loxygen.runtime import Return
from loxygen.token import Token
from loxygen.token import TokenType


class Interpreter(nodes.Visitor):
    def __init__(self) -> None:
        self.globals = Environment()
        self.globals.define("clock", Clock())
        self.locals: dict[nodes.Expr, int] = {}

        self.env = self.globals

    def visit_literal_expr(self, expr: nodes.Literal) -> LoxObject:
        return expr.value

    def visit_logical_expr(self, expr: nodes.Logical) -> LoxObject:
        left = self.evaluate(expr.left)
        if expr.operator.type == TokenType.OR:
            if self.is_truthy(left):
                return left
        else:
            if not self.is_truthy(left):
                return left

        return self.evaluate(expr.right)

    def visit_set_expr(self, expr: nodes.Set) -> LoxObject:
        object = self.evaluate(expr.object)
        if not isinstance(object, LoxInstance):
            raise LoxRunTimeError(expr.name, "Only instances have fields.")

        value = self.evaluate(expr.value)
        object.set(expr.name, value)

        return value

    def visit_super_expr(self, expr: nodes.Super) -> LoxObject:
        distance = self.locals.get(expr)
        assert distance is not None
        superclass = self.env.get_at(distance, "super")
        assert isinstance(superclass, LoxClass)
        object = self.env.get_at(distance - 1, "this")
        assert isinstance(object, LoxInstance)
        method = superclass.find_method(expr.method.lexeme)
        if method is None:
            raise LoxRunTimeError(
                expr.method,
                f"Undefined property '{expr.method.lexeme}'.",
            )

        return method.bind(object)

    def visit_this_expr(self, expr: nodes.This) -> LoxObject:
        return self.look_up_variable(expr.keyword, expr)

    def visit_unary_expr(self, expr: nodes.Unary) -> LoxObject:
        right = self.evaluate(expr.right)
        if expr.operator.type == TokenType.BANG:
            return not self.is_truthy(right)
        if expr.operator.type == TokenType.MINUS:
            if not isinstance(right, float):
                raise LoxRunTimeError(expr.operator, "Operand must be a number.")
            return -right

        return None

    def visit_variable_expr(self, expr: nodes.Variable) -> LoxObject:
        return self.look_up_variable(expr.name, expr)

    def look_up_variable(self, name: Token, expr: nodes.Expr) -> LoxObject:
        distance = self.locals.get(expr)
        if distance is not None:
            return self.env.get_at(distance, name.lexeme)
        return self.globals.get(name)

    def visit_binary_expr(self, expr: nodes.Binary) -> LoxObject:
        left = self.evaluate(expr.left)
        right = self.evaluate(expr.right)

        match expr.operator.type:
            case TokenType.GREATER:
                left, right = self.check_number_operands(expr.operator, left, right)
                return left > right
            case TokenType.GREATER_EQUAL:
                left, right = self.check_number_operands(expr.operator, left, right)
                return left >= right
            case TokenType.LESS:
                left, right = self.check_number_operands(expr.operator, left, right)
                return left < right
            case TokenType.LESS_EQUAL:
                left, right = self.check_number_operands(expr.operator, left, right)
                return left <= right
            case TokenType.MINUS:
                left, right = self.check_number_operands(expr.operator, left, right)
                return left - right
            case TokenType.PLUS:
                if isinstance(left, float) and isinstance(right, float):
                    return left + right
                if isinstance(left, str) and isinstance(right, str):
                    return left + right
                raise LoxRunTimeError(
                    expr.operator,
                    "Operands must be two numbers or two strings.",
                )
            case TokenType.SLASH:
                left, right = self.check_number_operands(expr.operator, left, right)
                return left / right if right else float("nan")
            case TokenType.STAR:
                left, right = self.check_number_operands(expr.operator, left, right)
                return left * right
            case TokenType.BANG_EQUAL:
                return not self.is_equal(left, right)
            case TokenType.EQUAL_EQUAL:
                return self.is_equal(left, right)

        return None

    @staticmethod
    def check_number_operands(
        operator: Token, left: LoxObject, right: LoxObject
    ) -> tuple[float, float]:
        if isinstance(left, float) and isinstance(right, float):
            return left, right
        raise LoxRunTimeError(operator, "Operands must be numbers.")

    def visit_call_expr(self, expr: nodes.Call) -> LoxObject:
        callee = self.evaluate(expr.callee)
        arguments = [self.evaluate(argument) for argument in expr.arguments]

        if not isinstance(callee, LoxCallable):
            raise LoxRunTimeError(
                expr.paren,
                "Can only call functions and classes.",
            )

        if (nb_args := len(arguments)) != (arity := callee.arity()):
            raise LoxRunTimeError(
                expr.paren,
                f"Expected {arity} arguments but got {nb_args}.",
            )

        return callee.call(self, arguments)

    def visit_get_expr(self, expr: nodes.Get) -> LoxObject:
        object = self.evaluate(expr.object)
        if isinstance(object, LoxInstance):
            return object.get(expr.name)

        raise LoxRunTimeError(expr.name, "Only instances have properties.")

    def visit_grouping_expr(self, expr: nodes.Grouping) -> LoxObject:
        return self.evaluate(expr.expr)

    @staticmethod
    def is_truthy(obj: LoxObject) -> bool:
        if obj is None:
            return False
        if isinstance(obj, bool):
            return obj
        return True

    @staticmethod
    def is_equal(obj1: LoxObject, obj2: LoxObject) -> bool:
        if isinstance(obj1, float) and isinstance(obj2, bool):
            return False
        if isinstance(obj1, bool) and isinstance(obj2, float):
            return False

        return obj1 == obj2

    def evaluate(self, expr: nodes.Expr) -> LoxObject:
        return expr.accept(self)

    def execute(self, stmt: nodes.Stmt) -> None:
        stmt.accept(self)

    def resolve(self, expr: nodes.Expr, depth: int) -> None:
        self.locals[expr] = depth

    def execute_block(self, stmts: list[nodes.Stmt], environment: Environment) -> None:
        enclosing = self.env
        try:
            self.env = environment
            for stmt in stmts:
                self.execute(stmt)
        finally:
            self.env = enclosing

    def visit_block_stmt(self, stmt: nodes.Block) -> None:
        self.execute_block(stmt.statements, Environment(self.env))

    def visit_class_stmt(self, stmt: nodes.Class) -> None:
        superclass: LoxClass | None = None
        if stmt.superclass is not None:
            if isinstance(evaluated_obj := self.evaluate(stmt.superclass), LoxClass):
                superclass = evaluated_obj
            else:
                raise LoxRunTimeError(
                    stmt.superclass.name,
                    "Superclass must be a class.",
                )

        self.env.define(stmt.name.lexeme, None)
        if stmt.superclass is not None:
            self.env = Environment(self.env)
            self.env.define("super", superclass)

        methods = {}
        for method in stmt.methods:
            is_initializer = method.name.lexeme == "init"
            function = LoxFunction(method, self.env, is_initializer)
            methods[method.name.lexeme] = function
        cls = LoxClass(stmt.name.lexeme, superclass, methods)

        if stmt.superclass is not None:
            assert self.env.enclosing is not None
            self.env = self.env.enclosing

        self.env.assign(stmt.name, cls)

    def visit_expression_stmt(self, stmt: nodes.Expression) -> None:
        self.evaluate(stmt.expr)

    def visit_function_stmt(self, stmt: nodes.Function) -> None:
        function = LoxFunction(stmt, self.env, False)
        self.env.define(stmt.name.lexeme, function)

    def visit_if_stmt(self, stmt: nodes.If) -> None:
        if self.is_truthy(self.evaluate(stmt.condition)):
            self.execute(stmt.then_branch)
        elif stmt.else_branch is not None:
            self.execute(stmt.else_branch)

    def visit_print_stmt(self, stmt: nodes.Print) -> None:
        value = self.evaluate(stmt.expr)
        print(self.stringify(value))

    def visit_return_stmt(self, stmt: nodes.Return) -> None:
        value = None
        if stmt.value is not None:
            value = self.evaluate(stmt.value)

        raise Return(value)

    def visit_var_stmt(self, stmt: nodes.Var) -> None:
        value = None
        if stmt.initializer is not None:
            value = self.evaluate(stmt.initializer)
        self.env.define(stmt.name.lexeme, value)

    def visit_while_stmt(self, stmt: nodes.While) -> None:
        while self.is_truthy(self.evaluate(stmt.condition)):
            self.execute(stmt.body)

    def visit_assign_expr(self, expr: nodes.Assign) -> LoxObject:
        value = self.evaluate(expr.value)
        distance = self.locals.get(expr)
        if distance is not None:
            self.env.assign_at(distance, expr.name, value)
        else:
            self.globals.assign(expr.name, value)

        return value

    def interpret(self, *stmts: nodes.Stmt) -> None:
        for stmt in stmts:
            self.execute(stmt)

    def stringify(self, obj: LoxObject) -> str:
        if obj is None:
            return "nil"
        if isinstance(obj, bool):
            return str(obj).lower()
        if isinstance(obj, float) and (repr := str(obj)).endswith(".0"):
            return repr[:-2]

        return str(obj)
