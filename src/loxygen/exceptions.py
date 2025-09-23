from __future__ import annotations

from loxygen.token import Token


class LoxError(Exception):
    pass


class LoxParseError(LoxError):
    pass


class LoxRunTimeError(LoxError):
    def __init__(self, token: Token, message: str):
        super().__init__()
        self.token = token
        self.message = message
