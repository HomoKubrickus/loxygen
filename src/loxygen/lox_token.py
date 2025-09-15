from __future__ import annotations

from typing import Any

from loxygen.tokens import TokenType


class Token:
    def __init__(self, type: TokenType, lexeme: str, literal: Any, line: int):
        self.type = type
        self.lexeme = lexeme
        self.literal = literal
        self.line = line

    def __str__(self):
        return f"{self.type} {self.lexeme} {self.literal}"

    def __repr__(self):
        return (
            f"Token(type={self.type.name}, "
            f"lexeme={self.lexeme}, "
            f"literal={self.literal}, "
            f"line={self.line})"
        )
