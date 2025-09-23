from __future__ import annotations

import subprocess
import sys
from abc import ABC
from abc import abstractmethod
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
        "Grouping": (("expr", "Expr"),),
        "Literal": (("value", "LoxObject"),),
        "Logical": (("left", "Expr"), ("operator", "Token"), ("right", "Expr")),
        "Set": (("object", "Expr"), ("name", "Token"), ("value", "Expr")),
        "Super": (("keyword", "Token"), ("method", "Token")),
        "This": (("keyword", "Token"),),
        "Unary": (("operator", "Token"), ("right", "Expr")),
        "Variable": (("name", "Token"),),
    },
    "Stmt": {
        "Block": (("statements", "list[Stmt]"),),
        "Expression": (("expr", "Expr"),),
        "Function": (
            ("name", "Token"),
            ("params", "list[Token]"),
            ("body", "list[Stmt]"),
        ),
        "Class": (
            ("name", "Token"),
            ("superclass", "Variable | None"),
            ("methods", "list[Function]"),
        ),
        "If": (("condition", "Expr"), ("then_branch", "Stmt"), ("else_branch", "Stmt | None")),
        "Print": (("expr", "Expr"),),
        "Return": (("keyword", "Token"), ("value", "Expr | None")),
        "Var": (("name", "Token"), ("initializer", "Expr | None")),
        "While": (("condition", "Expr"), ("body", "Stmt")),
    },
}


class ClassGenerator:
    def __init__(self, indent: int = INDENT):
        self.indent = " " * indent

    def format_line(self, text, level):
        return self.indent * level + text

    @staticmethod
    def get_return_type(node_base_class):
        return "None" if node_base_class == "Stmt" else "LoxObject"

    @staticmethod
    def get_visitor_method_name(node_class_name: str, base_class_name: str) -> str:
        return f"visit_{node_class_name.lower()}_{base_class_name.lower()}"


class NodeGenerator(ClassGenerator, ABC):
    def __init__(
        self,
        class_name: str,
        indent: int = INDENT,
    ):
        super().__init__(indent)
        self.class_name = class_name

    @property
    @abstractmethod
    def return_type(self):
        pass

    @property
    @abstractmethod
    def inheritance_str(self):
        pass

    @abstractmethod
    def get_accept_body(self):
        pass

    def generate_class_declaration(self):
        decorator = "@dataclass(frozen=True, slots=True)"
        declaration = f"class {self.class_name}{self.inheritance_str}:"
        yield from (self.format_line(line, 0) for line in (decorator, declaration))

    def generate_class_attrs(self):
        return ()

    def generate_accept_method(self):
        declaration = f"def accept(self, visitor: Visitor) -> {self.return_type}:"
        body = self.get_accept_body()
        yield from (self.format_line(declaration, 1), self.format_line(body, 2))

    def generate_class(self):
        cls = (
            self.generate_class_declaration(),
            self.generate_class_attrs(),
            self.generate_accept_method(),
        )
        yield from chain(*cls)


class BaseNodeGenerator(NodeGenerator):
    def __init__(
        self,
        class_name: str,
        indent: int = INDENT,
    ):
        super().__init__(class_name, indent)

    @property
    def return_type(self):
        return ClassGenerator.get_return_type(self.class_name)

    @property
    def inheritance_str(self):
        return ""

    def get_accept_body(self):
        return "pass"


class ConcreteNodeGenerator(NodeGenerator):
    def __init__(
        self,
        class_name: str,
        base_class: str,
        attrs: FieldList,
        indent: int = INDENT,
    ):
        super().__init__(class_name, indent)
        self.base_class = base_class
        self.attrs = attrs

    @property
    def return_type(self):
        return ClassGenerator.get_return_type(self.base_class)

    @property
    def inheritance_str(self):
        return f"({self.base_class})"

    def generate_class_attrs(self):
        attrs = (self.format_line(f"{attr}:{annotation}", 1) for attr, annotation in self.attrs)
        yield from attrs

    def get_accept_body(self):
        method_name = self.get_visitor_method_name(self.class_name, self.base_class)
        return f"return visitor.{method_name}(self)"


class VisitorGenerator(ClassGenerator):
    def generate_class_declaration(self):
        cls = "class Visitor(ABC):"
        yield self.format_line(cls, 0)

    def generate_visit_method(self, node: str, node_base_class: str):
        decorator = "@abstractmethod"
        method_name = self.get_visitor_method_name(node, node_base_class)
        params = f"self, {node_base_class.lower()}: {node}"
        return_type = self.get_return_type(node_base_class)
        declaration = f"def {method_name}({params}) -> {return_type}:"
        body = "pass"

        yield from (
            self.format_line(decorator, 1),
            self.format_line(declaration, 1),
            self.format_line(body, 2),
        )

    def generate_class(self, node_defs: NodeDefinitions):
        declaration = self.generate_class_declaration()
        methods = chain.from_iterable(
            self.generate_visit_method(class_name, node_base_class)
            for node_base_class, subclass_defs in node_defs.items()
            for class_name in subclass_defs
        )

        yield from chain(declaration, methods)


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
        "from __future__ import annotations\n",
        "from abc import ABC",
        "from abc import abstractmethod",
        "from dataclasses import dataclass\n",
        f"from {package_name}.runtime import LoxObject",
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
