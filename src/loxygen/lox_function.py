from __future__ import annotations

from loxygen import stmt
from loxygen.environment import Environment
from loxygen.lox_callable import Callable
from loxygen.returner import Return


class LoxFunction(Callable):
    def __init__(
        self,
        declaration: stmt.Function,
        closure: Environment,
        is_initializer: bool,
    ):
        self.is_initializer = is_initializer
        self.declaration = declaration
        self.closure = closure

    def bind(self, instance):
        env = Environment(self.closure)
        env.define("this", instance)

        return LoxFunction(self.declaration, env, self.is_initializer)

    def call(self, interpreter, arguments):
        env = Environment(self.closure)
        for param, arg in zip(self.declaration.params, arguments, strict=False):
            env.define(param.lexeme, arg)
        try:
            interpreter.execute_block(self.declaration.body, env)
        except Return as e:
            if self.is_initializer:
                return self.closure.get_at(0, "this")
            return e.value

        if self.is_initializer:
            return self.closure.get_at(0, "this")

    def arity(self):
        return len(self.declaration.params)

    def __repr__(self):
        return f"<fn {self.declaration.name.lexeme}>"
