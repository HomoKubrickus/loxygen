from __future__ import annotations

from loxygen.lox_token import Token


class LoxError(Exception):
    pass


class LoxStaticError(LoxError):
    pass


class LoxParseError(LoxStaticError):
    pass


class LoxRunTimeError(LoxError):
    def __init__(self, token, message):
        super().__init__()
        self.token: Token = token
        self.message: str = message
