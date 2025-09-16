from __future__ import annotations

from time import perf_counter_ns

from loxygen import nodes
from loxygen.environment import Environment
from loxygen.exceptions import LoxRunTimeError
from loxygen.token import Token


class Return(RuntimeError):
    def __init__(self, value):
        super().__init__()
        self.value = value


class Callable:
    def call(self, interpreter, arguments):
        pass

    def arity(self):
        pass


class LoxFunction(Callable):
    def __init__(
        self,
        declaration: nodes.Function,
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


class LoxClass(Callable):
    def __init__(self, name, superclass, methods):
        self.name = name
        self.superclass = superclass
        self.methods = methods

    def find_method(self, name: str):
        if name in self.methods:
            return self.methods[name]

        if self.superclass is not None:
            return self.superclass.find_method(name)

        return None

    def call(self, interpreter, arguments):
        instance = LoxInstance(self)
        if (initializer := self.find_method("init")) is not None:
            initializer.bind(instance).call(interpreter, arguments)
        return instance

    def arity(self):
        initializer = self.find_method("init")
        if initializer is None:
            return 0
        return initializer.arity()

    def __repr__(self):
        return self.name


class LoxInstance:
    def __init__(self, cls):
        self.cls = cls
        self.fields = {}

    def get(self, name: Token):
        if (field := self.fields.get(name.lexeme)) is not None:
            return field

        method = self.cls.find_method(name.lexeme)
        if method is not None:
            return method.bind(self)

        raise LoxRunTimeError(name, f"Undefined property '{name.lexeme}'.")

    def set(self, name: Token, value):
        self.fields[name.lexeme] = value

    def __repr__(self):
        return f"{self.cls.name} instance"


class Clock(Callable):
    @staticmethod
    def call(self, interpreter, arguments):
        return perf_counter_ns() * 1000

    def arity(self):
        return 0

    def __repr__(self):
        return "<native fn>"
