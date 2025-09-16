from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from shutil import which

type FieldList = tuple[tuple[str, str], ...]
type SubclassMap = dict[str, FieldList]
type NodeDefinitions = dict[str, SubclassMap]


PACKAGE_NAME = "loxygen"
FORMATTER = "ruff"
INDENT = 4


NODE_DEFS: NodeDefinitions = {
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
        attrs: FieldList = (),
        indent: int = INDENT,
    ):
        self.class_name = class_name
        self.base_class = base_class
        self.attrs = attrs
        self.indent = " " * indent

    def format_line(self, text, level):
        return self.indent * level + text

    def generate_class_declaration(self):
        yield self.format_line("@dataclass(frozen=True, slots=True)", 0)
        cls = f"class {self.class_name}"
        cls += ":" if self.base_class is None else f"({self.base_class}):"
        yield self.format_line(cls, 0)

    def generate_attrs(self):
        for attr, annotation in self.attrs:
            yield self.format_line(f"{attr}:{annotation}", 1)

    def generate_accept_method(self):
        yield self.format_line("def accept(self, visitor):", 1)
        body = (
            "pass"
            if self.base_class is None
            else f"return visitor.visit_{self.class_name.lower()}_{self.base_class.lower()}(self)"
        )
        yield self.format_line(body, 2)

    def generate_class(self):
        yield from self.generate_class_declaration()
        yield from self.generate_attrs()
        yield from self.generate_accept_method()


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


def generate_all_nodes(
    base_class: str, package_name: str, subclass_defs: SubclassMap
) -> Iterator[str]:
    yield "from dataclasses import dataclass"
    if base_class == "Stmt":
        yield f"from {package_name}.expr import Expr"
        yield f"from {package_name}.expr import Variable"
    yield f"from {package_name}.token import Token"

    yield from NodeGenerator(base_class).generate_class()

    for class_name, attrs in subclass_defs.items():
        yield from NodeGenerator(class_name, base_class, attrs).generate_class()


def generate_nodes_file(
    base_class: str, package_name: str, subclass_defs: SubclassMap, formatter: str, filename: Path
) -> None:
    lines = generate_all_nodes(base_class, package_name, subclass_defs)
    text = format_file("\n".join(lines), formatter)
    filename.write_text(text)
    print(f"File saved to {filename}")


def main(node_defs: NodeDefinitions, package_name: str, formatter: str) -> None:
    for base_class, nodes_dict in node_defs.items():
        root = Path(__file__).parent.parent.resolve()
        filename = root / "src" / package_name / f"{base_class.lower()}.py"
        generate_nodes_file(base_class, package_name, nodes_dict, formatter, filename)


if __name__ == "__main__":
    main(NODE_DEFS, PACKAGE_NAME, FORMATTER)
