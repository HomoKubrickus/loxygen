from __future__ import annotations

import readline  # noqa: F401
import sys
from collections.abc import Iterable
from os import EX_USAGE
from pathlib import Path

from contract import LoxStatus
from loxygen.exceptions import LoxRunTimeError
from loxygen.interpreter import Interpreter
from loxygen.parser import Parser
from loxygen.resolver import Resolver
from loxygen.scanner import Scanner
from loxygen.token import Token
from loxygen.token import TokenType


class Lox:
    def __init__(self) -> None:
        self.interpreter = Interpreter()

    def main(self, args: list[str]) -> None:
        if len(args) > 1:
            print("Usage: loxygen [script]")
            sys.exit(EX_USAGE)
        elif len(args) == 1:
            self.run_file(Path(args[0]))
        else:
            self.run_prompt()

    def run_file(self, filename: Path) -> None:
        with open(filename) as f:
            source = f.read()
        status = self.run(source)
        if status != LoxStatus.OK:
            sys.exit(status.value)

    def run_prompt(self) -> None:
        while True:
            line = input(">")
            if line == "":
                break
            self.run(line)

    def run(self, source: str) -> LoxStatus:
        scanner = Scanner(source)
        scanner.scan_tokens()
        parser = Parser(scanner.tokens)
        stmts = parser.parse()

        errors = (error for producer in (scanner, parser) for error in producer.errors)
        if self.check_error(errors):
            return LoxStatus.STATIC_ERROR

        resolver = Resolver(self.interpreter)
        resolver.resolve(*stmts)

        if self.check_error(resolver.errors):
            return LoxStatus.STATIC_ERROR

        try:
            self.interpreter.interpret(*stmts)
        except LoxRunTimeError as e:
            self.error(e.token.line, e.message)
            return LoxStatus.RUNTIME_ERROR

        return LoxStatus.OK

    def check_error(self, errors: Iterable[tuple[int | Token, str]]) -> bool:
        error = False
        for context, message in errors:
            self.error(context, message)
            error = True
        return error

    def error(
        self,
        context: int | Token,
        message: str,
    ) -> None:
        if isinstance(context, int):
            line = context
            token = ""
        elif isinstance(context, Token):
            line = context.line
            position = "end" if context.type == TokenType.EOF else f"'{context.lexeme}'"
            token = f"Error at {position}: "

        print(f"[line {line}] {token}{message}", file=sys.stderr)


def main() -> None:
    Lox().main(sys.argv[1:])


if __name__ == "__main__":
    main()
