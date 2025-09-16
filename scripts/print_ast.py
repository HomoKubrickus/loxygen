from __future__ import annotations

import sys
from pathlib import Path

from loxygen import nodes
from loxygen.parser import Parser
from loxygen.scanner import Scanner


class ASTPrinter:
    def visit_binary_expr(self, expression: nodes.Binary):
        return self.parenthesize(expression.operator.lexeme, expression.left, expression.right)

    def visit_grouping_expr(self, expression: nodes.Grouping):
        return self.parenthesize("group", expression.expression)

    def visit_literal_expr(self, expression: nodes.Literal):
        if expression.value is None:
            return "nil"
        return str(expression.value)

    def visit_unary_expr(self, expression: nodes.Unary):
        return self.parenthesize(expression.operator.lexeme, expression.right)

    def parenthesize(self, name: str, *exprs: nodes.Expr):
        output = f"({name}"
        for expression in exprs:
            output += f" {expression.accept(self)}"
        output += ")"
        return output

    def print(self, expression: nodes.Expr):
        return expression.accept(self)


def generate_ast_string(inp: str) -> str:
    scanner = Scanner(inp)
    scanner.scan_tokens()
    expression = Parser(scanner.tokens).expression()
    return ASTPrinter().print(expression)


def test(argv: list[str]):
    test_path = Path("expressions") / "parse.lox"
    if len(argv) != 2:
        raise ValueError(f"Only one argument is allowed: the parent directory of {test_path}.")

    full_path = Path(argv[1]) / test_path
    if not full_path.exists():
        raise FileNotFoundError(f"The provided path does not contain {test_path}.")

    text = full_path.read_text()
    for line in text.splitlines():
        if not line.startswith("//"):
            code = line.strip()
        elif line.startswith("// expect:"):
            expected = line.removeprefix("// expect:").strip()

    actual = generate_ast_string(code)

    print(f"Expression: {code}")
    print(f"\n{'Expected string:':<18}{expected}")
    print(f"{'Actual string:':<18}{actual}")
    assert actual == expected, "There's a mismatch between the expected and computed output."
    print("\nTest Passed: The generated AST matches the expected output.")


if __name__ == "__main__":
    try:
        test(sys.argv)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except AssertionError as e:
        print(f"\nTest Failed: {e}", file=sys.stderr)
        sys.exit(1)
