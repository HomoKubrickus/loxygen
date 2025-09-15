from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from shutil import which

PACKAGE_NAME = "loxygen"
FORMATTER = "ruff"
INDENT = 4


MAPPING: dict[str, dict[str, tuple[tuple[str, str], ...]]] = {
    "Expr": {
        "Assign": (("name", "Token"), ("value", "Expr")),
        "Binary": (("left", "Expr"), ("operator", "Token"), ("right", "Expr")),
        "Call": (("callee", "Expr"), ("paren", "Token"), ("arguments", "list[Expr]")),
        "Get": (("object", "Expr"), ("name", "Token")),
        "Grouping": (("expression", "Expr"),),
        "Literal": (("value", "object"),),
        "Logical": (("left", "Expr"), ("operator", "Token"), ("right", "Expr")),
        "Set": (("object", "Expr"), ("name", "Token"), ("value", "Expr")),
        "Super": (("keyword", "Token"), ("method", "Token")),
        "This": (("keyword", "Token"),),
        "Unary": (("operator", "Token"), ("right", "Expr")),
        "Variable": (("name", "Token"),),
    },
    "Stmt": {
        "Block": (("statements", "list[Stmt]"),),
        "Expression": (("expression", "Expr"),),
        "Function": (
            ("name", "Token"),
            ("params", "list[Token]"),
            ("body", "list[Stmt]"),
        ),
        "Class": (
            ("name", "Token"),
            ("superclass", "Variable"),
            ("methods", "list[Function]"),
        ),
        "If": (("condition", "Expr"), ("then_branch", "Stmt"), ("else_branch", "Stmt")),
        "Print": (("expression", "Expr"),),
        "Return": (("keyword", "Token"), ("value", "Expr")),
        "Var": (("name", "Token"), ("initializer", "Expr")),
        "While": (("condition", "Expr"), ("body", "Stmt")),
    },
}


class NodeGenerator:
    def __init__(
        self,
        class_name: str,
        base_class: str | None = None,
        params: tuple[tuple[str, str]] | None = None,
        indent: int = INDENT,
    ):
        self.class_name = class_name
        self.base_class = base_class
        self.params = params
        self.indent = " " * indent
        self.text: list[str] = []
        self.level = 0

    def add_line(self, text):
        self.text.append(self.level * self.indent + text)

    def add_class_declaration(self):
        text = f"class {self.class_name}"
        text += ":" if self.base_class is None else f"({self.base_class}):"
        self.add_line(text)

    def add_function_declaration(self, name, params):
        self.level = 1
        params = ",".join(
            param + f":{annotation}" if annotation else param for param, annotation in params
        )
        declaration = f"def {name}({params}):"
        self.add_line(declaration)

    def add_init_body(self):
        self.level = 2
        for param, _ in self.params:
            self.add_line(f"self.{param} = {param}")

    def add_accept_body(self):
        self.level = 2
        if self.base_class is None:
            self.add_line("pass")
        else:
            self.add_line(
                f"return visitor.visit_{self.class_name.lower()}_{self.base_class.lower()}(self)",
            )

    def generate_parent_class(self):
        self.add_class_declaration()
        self.add_function_declaration("accept", (("self", ""), ("visitor", "")))
        self.add_accept_body()

        return self.text

    def generate_class(self):
        self.add_class_declaration()
        self.add_function_declaration("__init__", (("self", ""),) + self.params)
        self.add_init_body()
        self.add_function_declaration("accept", (("self", ""), ("visitor", "")))
        self.add_accept_body()

        return self.text


def format_file(text: str, formatter: str) -> str:
    if formatter not in ("black", "ruff"):
        print("Formatter must be 'black' or 'ruff'. Code will not be formatted.", file=sys.stderr)
        return text

    if (formatter_path := which(formatter)) is None:
        print(f"'{formatter}' is not installed. Code will not be formatted.", file=sys.stderr)
        return text

    if formatter == "ruff":
        cmd = [formatter_path, "format", "-"]
    if formatter == "black":
        cmd = [formatter_path, "-"]

    process = subprocess.run(
        cmd,
        input=text,
        capture_output=True,
        text=True,
    )

    if process.returncode != 0:
        print(process.stderr.removesuffix("\n"), file=sys.stderr)
        return text

    return process.stdout


def generate_nodes_file(base_class, mapping, package_name, formatter: str, filename: Path):
    lines: list[str] = []
    if base_class == "Stmt":
        lines.extend(
            (
                f"from {package_name}.expr import Expr",
                f"from {package_name}.expr import Variable",
            )
        )
    lines.append(f"from {package_name}.lox_token import Token")
    lines.extend(NodeGenerator(base_class).generate_parent_class())

    for cls, attrs in mapping.items():
        lines.extend(NodeGenerator(cls, base_class, attrs).generate_class())

    text = format_file("\n".join(lines), formatter)
    filename.write_text(text)
    print(f"File saved to {filename}")


def main(mapping: dict[str, dict], package_name: str, formatter: str):
    for base_class, nodes_dict in mapping.items():
        root = Path(__file__).parent.parent.resolve()
        filename = root / "src" / package_name / f"{base_class.lower()}.py"
        generate_nodes_file(base_class, nodes_dict, package_name, formatter, filename)


if __name__ == "__main__":
    main(MAPPING, PACKAGE_NAME, FORMATTER)
