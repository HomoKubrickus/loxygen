from __future__ import annotations

from loxygen.exceptions import LoxRunTimeError
from loxygen.lox_token import Token


class Environment:
    def __init__(self, enclosing=None):
        self.values = {}
        self.enclosing = enclosing

    def define(self, name: str, value: object) -> None:
        self.values[name] = value

    def ancestor(self, distance):
        environment = self
        for _ in range(distance):
            environment = environment.enclosing
        return environment

    def get_at(self, distance: int, name: str):
        return self.ancestor(distance).values[name]

    def assign_at(self, distance: int, name: Token, value):
        self.ancestor(distance).values[name.lexeme] = value

    def get(self, name: Token) -> object:
        try:
            return self.values[name.lexeme]
        except KeyError:
            pass

        if self.enclosing is not None:
            return self.enclosing.get(name)

        raise LoxRunTimeError(name, f"Undefined variable '{name.lexeme}'.")

    def assign(self, name: Token, value: object):
        if name.lexeme in self.values:
            self.values[name.lexeme] = value
            return

        if self.enclosing is not None:
            self.enclosing.assign(name, value)
            return

        raise LoxRunTimeError(name, f"Undefined variable '{name.lexeme}'.")
