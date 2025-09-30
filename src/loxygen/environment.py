from __future__ import annotations

from typing import Self

from loxygen.exceptions import LoxRunTimeError
from loxygen.token import Token


class Environment[T]:
    def __init__(self, enclosing: Self | None = None):
        self.values: dict[str, T] = {}
        self.enclosing = enclosing

    def define(self, name: str, value: T) -> None:
        self.values[name] = value

    def ancestor(self, distance: int) -> Self:
        environment = self
        for _ in range(distance):
            assert environment.enclosing is not None
            environment = environment.enclosing
        return environment

    def get_at(self, distance: int, name: str) -> T:
        return self.ancestor(distance).values[name]

    def assign_at(self, distance: int, name: Token, value: T) -> None:
        self.ancestor(distance).values[name.lexeme] = value

    def get(self, name: Token) -> T:
        try:
            return self.values[name.lexeme]
        except KeyError:
            pass

        if self.enclosing is not None:
            return self.enclosing.get(name)

        raise LoxRunTimeError(name, f"Undefined variable '{name.lexeme}'.")

    def assign(self, name: Token, value: T) -> None:
        if name.lexeme in self.values:
            self.values[name.lexeme] = value
            return

        if self.enclosing is not None:
            self.enclosing.assign(name, value)
            return

        raise LoxRunTimeError(name, f"Undefined variable '{name.lexeme}'.")
