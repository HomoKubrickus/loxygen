from __future__ import annotations

from typing import TYPE_CHECKING

from loxygen.exceptions import LoxRunTimeError
from loxygen.token import Token

if TYPE_CHECKING:
    from loxygen.runtime import LoxObject


class Environment:
    def __init__(self, enclosing: Environment | None = None):
        self.values: dict[str, LoxObject] = {}
        self.enclosing = enclosing

    def define(self, name: str, value: LoxObject) -> None:
        self.values[name] = value

    def ancestor(self, distance: int) -> Environment:
        environment = self
        for _ in range(distance):
            assert environment.enclosing is not None
            environment = environment.enclosing
        return environment

    def get_at(self, distance: int, name: str) -> LoxObject:
        return self.ancestor(distance).values[name]

    def assign_at(self, distance: int, name: Token, value: LoxObject) -> None:
        self.ancestor(distance).values[name.lexeme] = value

    def get(self, name: Token) -> LoxObject:
        try:
            return self.values[name.lexeme]
        except KeyError:
            pass

        if self.enclosing is not None:
            return self.enclosing.get(name)

        raise LoxRunTimeError(name, f"Undefined variable '{name.lexeme}'.")

    def assign(self, name: Token, value: LoxObject) -> None:
        if name.lexeme in self.values:
            self.values[name.lexeme] = value
            return

        if self.enclosing is not None:
            self.enclosing.assign(name, value)
            return

        raise LoxRunTimeError(name, f"Undefined variable '{name.lexeme}'.")
