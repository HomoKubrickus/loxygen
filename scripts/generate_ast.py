from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from itertools import chain
from pathlib import Path
from shutil import which

type FieldList = tuple[tuple[str, str], ...]
type SubclassMap = dict[str, FieldList]
type NodeDefinitions = dict[str, SubclassMap]


PACKAGE_NAME = "loxygen"
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


class CodeGenerator:
    def __init__(self, indent: int = INDENT):
        self.indent = " " * indent

    def format_line(self, text, level):
        return self.indent * level + text


class BaseNodeGenerator(CodeGenerator):
    def __init__(
        self,
        class_name: str,
        indent: int = INDENT,
    ):
        super().__init__(indent)
        self.class_name = class_name

    def generate_class_declaration(self):
        yield self.format_line("@dataclass(frozen=True, slots=True)", 0)
        yield self.format_line(f"class {self.class_name}:", 0)

    def generate_accept_method(self):
        yield self.format_line("def accept(self, visitor: Visitor):", 1)
        yield self.format_line("pass", 2)

    def generate_class(self):
        yield from self.generate_class_declaration()
        yield from self.generate_accept_method()


class ConcreteNodeGenerator(CodeGenerator):
    def __init__(
        self,
        class_name: str,
        base_class: str,
        attrs: FieldList,
        indent: int = INDENT,
    ):
        super().__init__(indent)
        self.class_name = class_name
        self.base_class = base_class
        self.attrs = attrs

    def generate_class_declaration(self):
        decorator = "@dataclass(frozen=True, slots=True)"
        yield self.format_line(decorator, 0)
        declaration = f"class {self.class_name}({self.base_class}):"
        yield self.format_line(declaration, 0)

    def generate_attrs(self):
        for attr, annotation in self.attrs:
            yield self.format_line(f"{attr}:{annotation}", 1)

    def generate_accept_method(self):
        declaration = "def accept(self, visitor: Visitor):"
        yield self.format_line(declaration, 1)
        method_name = f"visit_{self.class_name.lower()}_{self.base_class.lower()}"
        return_stmt = f"return visitor.{method_name}(self)"
        yield self.format_line(return_stmt, 2)

    def generate_class(self):
        yield from self.generate_class_declaration()
        yield from self.generate_attrs()
        yield from self.generate_accept_method()


class VisitorGenerator(CodeGenerator):
    def generate_class_declaration(self):
        cls = "class Visitor(ABC):"
        yield self.format_line(cls, 0)

    def generate_visit_method(self, node: str, node_base_class: str):
        yield self.format_line("@abstractmethod", 1)
        method_name = f"visit_{node.lower()}_{node_base_class.lower()}"
        params = f"self, {node_base_class.lower()}: {node}"
        yield self.format_line(f"def {method_name}({params}):", 1)
        yield self.format_line("pass", 2)

    def generate_class(self, node_defs: NodeDefinitions):
        yield from self.generate_class_declaration()
        for node_base_class, subclass_defs in node_defs.items():
            for class_name in subclass_defs:
                yield from self.generate_visit_method(class_name, node_base_class)


def format_file(text: str) -> str:
    if (ruff_path := which("ruff")) is None:
        print("'ruff' is not installed. Code will not be formatted.", file=sys.stderr)
        return text

    process = subprocess.run(
        [ruff_path, "format", "-"],
        input=text,
        capture_output=True,
        text=True,
    )

    if process.returncode != 0:
        print(process.stderr.removesuffix("\n"), file=sys.stderr)
        return text

    return process.stdout


def generate_all_nodes(package_name: str, node_defs: NodeDefinitions) -> Iterator[str]:
    imports = (
        "from __future__ import annotations",
        "from abc import ABC",
        "from abc import abstractmethod",
        "from dataclasses import dataclass",
        f"from {package_name}.token import Token",
    )
    visitor = VisitorGenerator().generate_class(node_defs)
    base_nodes = chain.from_iterable(
        BaseNodeGenerator(base_class).generate_class() for base_class in node_defs
    )
    concrete_nodes = chain.from_iterable(
        ConcreteNodeGenerator(class_name, base_class, attrs).generate_class()
        for base_class, subclass_defs in node_defs.items()
        for class_name, attrs in subclass_defs.items()
    )

    yield from chain(imports, visitor, base_nodes, concrete_nodes)


def generate_nodes_file(package_name: str, node_defs: NodeDefinitions) -> None:
    lines = generate_all_nodes(package_name, node_defs)
    text = format_file("\n".join(lines))
    root = Path(__file__).parent.parent.resolve()
    filename = root / "src" / package_name / "nodes.py"
    filename.write_text(text)
    print(f"File saved to {filename}")


if __name__ == "__main__":
    generate_nodes_file(PACKAGE_NAME, NODE_DEFS)
