from __future__ import annotations

from loxygen.exceptions import LoxRunTimeError
from loxygen.lox_token import Token


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
