from __future__ import annotations

from loxygen.token import Token


class LoxError(Exception):
    pass


class LoxParseError(LoxError):
    pass


class LoxRunTimeError(LoxError):
    def __init__(self, token, message):
        super().__init__()
        self.token: Token = token
        self.message: str = message
