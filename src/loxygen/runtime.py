from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from time import perf_counter_ns
from typing import Protocol

from loxygen import nodes
from loxygen.environment import Environment
from loxygen.exceptions import LoxRunTimeError
from loxygen.token import LiteralValue
from loxygen.token import Token

type LoxObject = LiteralValue | LoxCallable | LoxInstance


class Return(RuntimeError):
    def __init__(self, value: LoxObject):
        super().__init__()
        self.value = value


class Executor(Protocol):
    def execute_block(
        self, stmts: list[nodes.Stmt], environment: Environment[LoxObject]
    ) -> None: ...


class LoxCallable(ABC):
    @abstractmethod
    def call(self, interpreter: Executor, arguments: list[LoxObject]) -> LoxObject:
        pass

    @abstractmethod
    def arity(self) -> int:
        pass


class LoxFunction(LoxCallable):
    def __init__(
        self,
        declaration: nodes.Function,
        closure: Environment[LoxObject],
        is_initializer: bool,
    ):
        self.is_initializer = is_initializer
        self.declaration = declaration
        self.closure = closure

    def bind(self, instance: LoxInstance) -> LoxFunction:
        env = Environment(self.closure)
        env.define("this", instance)

        return LoxFunction(self.declaration, env, self.is_initializer)

    def call(self, interpreter: Executor, arguments: list[LoxObject]) -> LoxObject:
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

        return None

    def arity(self) -> int:
        return len(self.declaration.params)

    def __repr__(self) -> str:
        return f"<fn {self.declaration.name.lexeme}>"


class LoxClass(LoxCallable):
    def __init__(self, name: str, superclass: LoxClass | None, methods: dict[str, LoxFunction]):
        self.name = name
        self.superclass = superclass
        self.methods = methods

    def find_method(self, name: str) -> LoxFunction | None:
        if name in self.methods:
            return self.methods[name]

        if self.superclass is not None:
            return self.superclass.find_method(name)

        return None

    def call(self, interpreter: Executor, arguments: list[LoxObject]) -> LoxInstance:
        instance = LoxInstance(self)
        if (initializer := self.find_method("init")) is not None:
            initializer.bind(instance).call(interpreter, arguments)
        return instance

    def arity(self) -> int:
        initializer = self.find_method("init")
        if initializer is None:
            return 0
        return initializer.arity()

    def __repr__(self) -> str:
        return self.name


class LoxInstance:
    def __init__(self, cls: LoxClass):
        self.cls = cls
        self.fields: dict[str, LoxObject] = {}

    def get(self, name: Token) -> LoxObject:
        if (field := self.fields.get(name.lexeme)) is not None:
            return field

        method = self.cls.find_method(name.lexeme)
        if method is not None:
            return method.bind(self)

        raise LoxRunTimeError(name, f"Undefined property '{name.lexeme}'.")

    def set(self, name: Token, value: LoxObject) -> None:
        self.fields[name.lexeme] = value

    def __repr__(self) -> str:
        return f"{self.cls.name} instance"


class Clock(LoxCallable):
    def call(self, interpreter: Executor, arguments: list[LoxObject]) -> float:
        return perf_counter_ns() / 1000

    def arity(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "<native fn>"
