from __future__ import annotations

import re
import shlex
import subprocess
import traceback
from collections import Counter
from collections.abc import Generator
from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Literal
from typing import Self
from typing import TypeVar
from typing import cast

import pytest
from _pytest._code.code import TerminalRepr
from _pytest._code.code import TracebackStyle
from _pytest.terminal import TerminalReporter

from contract import LoxStatus

DEFAULT_INTERPRETER = ["loxygen"]
DEFAULT_SKIP_DIRS = ["benchmark", "scanning", "limit", "expressions"]

T = TypeVar("T")
type PytestIniType = Literal["string", "paths", "pathlist", "args", "linelist", "bool"]


@dataclass(frozen=True)
class Option[T]:
    name: str
    help: str
    ini_type: PytestIniType
    ini_default: T
    cli: dict[str, Any]
    stash_key: pytest.StashKey[T] = field(default_factory=pytest.StashKey, init=False)


OPTIONS = {
    "interpreter-cmd": Option[list[str]](
        name="interpreter-cmd",
        help="The command to run the interpreter.",
        ini_type="args",
        ini_default=DEFAULT_INTERPRETER,
        cli={"type": shlex.split},
    ),
    "skip-dirs": Option[list[str]](
        name="skip-dirs",
        help="Skips tests located within the specified directory names.",
        ini_type="linelist",
        ini_default=DEFAULT_SKIP_DIRS,
        cli={"action": "append"},
    ),
}


class LoxTestError(Exception):
    pass


class FailedTestException(LoxTestError):
    def __init__(self, failed_lines: tuple[int, ...], *args: object) -> None:
        super().__init__(*args)
        self.failed_lines = failed_lines


class BackEndError(LoxTestError):
    def __init__(self, error: str, *args: object) -> None:
        super().__init__(*args)
        self.error = error


@dataclass
class LoxEvent:
    status: LoxStatus
    text: str


@dataclass
class ExpectedLoxEvent(LoxEvent):
    lineno: int

    @classmethod
    def from_match(cls, match: re.Match[str], lineno: int) -> Self:
        group = match.lastgroup
        assert group is not None
        output = match.group(group).strip()
        status = LoxStatus[group.upper()]

        return cls(status, output, lineno)


class TestItem(pytest.Item):
    def __init__(self, parent: LoxFile, name: str, expected: list[ExpectedLoxEvent]) -> None:
        super().__init__(name, parent)
        self.expected: list[ExpectedLoxEvent] = expected
        self.output: list[LoxEvent] = []

    def runtest(self) -> None:
        self.run_lox()

        if (output_len := len(self.output)) != (expected_len := len(self.expected)):
            raise FailedTestException(
                (-1,),
                f"Mismatch in number of output lines: expected {expected_len},"
                f" but got {output_len}.",
            )

        failed_lines = tuple(
            expected.lineno
            for output, expected in zip(self.output, self.expected)
            if (output.status != expected.status) or (output.text != expected.text)
        )

        if len(failed_lines):
            raise FailedTestException(failed_lines)

    def run_lox(self) -> None:
        cmd = self.config.stash[OPTIONS["interpreter-cmd"].stash_key] + [self.path]
        try:
            process = subprocess.run(cmd, capture_output=True, text=True)
        except OSError:
            raise BackEndError(traceback.format_exc()) from None

        if process.stdout:
            self.output = [
                LoxEvent(LoxStatus.OK, line.strip()) for line in process.stdout.splitlines()
            ]

        if process.returncode != 0:
            if process.returncode in LoxStatus:
                self.output.extend(
                    LoxEvent(LoxStatus(process.returncode), line.strip())
                    for line in process.stderr.splitlines()
                )
            else:
                raise BackEndError(process.stderr)

    def repr_failure(
        self, excinfo: pytest.ExceptionInfo[BaseException], style: TracebackStyle | None = None
    ) -> str | TerminalRepr:
        if isinstance(excinfo.value, FailedTestException):
            return self.colorize(*excinfo.value.failed_lines)
        if isinstance(excinfo.value, BackEndError):
            return excinfo.value.error

        return super().repr_failure(excinfo, style)

    def add_result(self) -> list[str]:
        text = self.path.read_text().splitlines()

        for result, output in zip(self.expected, self.output):
            text[result.lineno] = text[result.lineno] + f" // output: {output.text}"

        return text

    def colorize(self, *indexes: int) -> str:
        colors = {"red": 91, "green": 92}
        text = self.add_result()
        if indexes == (-1,):
            indexes = tuple(range(len(text)))
        for result in self.expected:
            color = colors["red"] if result.lineno in indexes else colors["green"]
            text[result.lineno] = f"\033[{color}m{text[result.lineno]}\033[0m"

        return "\n".join(text)

    def reportinfo(self) -> tuple[Path, int, str]:
        return self.path, 0, self.name


class LoxFile(pytest.File):
    def parse_test(self) -> list[ExpectedLoxEvent]:
        pattern = re.compile(
            rf"// expect: (?P<{LoxStatus.OK.name.lower()}>.*)|"
            rf"// (?P<{LoxStatus.STATIC_ERROR.name.lower()}>\[line \d+] Error.*)|"
            rf"// expect runtime error: (?P<{LoxStatus.RUNTIME_ERROR.name.lower()}>(.*))",
        )

        return [
            ExpectedLoxEvent.from_match(result, lineno)
            for lineno, line in enumerate(self.path.read_text().splitlines())
            if (result := re.search(pattern, line)) is not None
        ]

    def collect(self) -> Iterator[TestItem]:
        yield TestItem.from_parent(
            self,
            name=self.path.stem,
            expected=self.parse_test(),
        )


def pytest_addoption(parser: pytest.Parser) -> None:
    for option in OPTIONS.values():
        parser.addini(option.name, option.help, option.ini_type, option.ini_default)
        parser.addoption(f"--{option.name}", help=option.help, **option.cli)


def get_value[T](config: pytest.Config, option: Option[T]) -> T:
    name = option.name
    if (value := config.getoption(f"--{name}")) is None:
        value = config.getini(name)

    return cast(T, value)


def pytest_configure(config: pytest.Config) -> None:
    for option in OPTIONS.values():
        value = get_value(config, option)
        config.stash[option.stash_key] = value


def pytest_collect_file(parent: pytest.Dir, file_path: Path) -> pytest.Collector | None:
    if file_path.suffix == ".lox":
        return LoxFile.from_parent(
            parent,
            path=file_path,
        )

    return None


def mark_items_as_skipped(items: list[TestItem]) -> None:
    for item in items:
        root_path = item.config.rootpath
        parts = item.path.relative_to(root_path).parent.parts
        skip_dirs = item.config.stash[OPTIONS["skip-dirs"].stash_key]
        if not set(parts).isdisjoint(set(skip_dirs)):
            skipped_dir = set(parts).intersection(skip_dirs).pop()
            reason = f"Test located in a skipped directory: {skipped_dir}"
            item.add_marker(pytest.mark.skip(reason=reason))


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[TestItem]
) -> Generator[None, None, None]:
    collected_count = len(items)
    yield
    if len(items) == collected_count:
        mark_items_as_skipped(items)


def pytest_runtest_makereport(item: TestItem, call: pytest.CallInfo[None]) -> pytest.TestReport:
    report = pytest.TestReport.from_item_and_call(item, call)
    if call.when == "call" and call.excinfo:
        if isinstance(call.excinfo.value, BackEndError):
            report.user_properties.append(
                ("BackEndError", call.excinfo.value.error.splitlines()[-1])
            )

    return report


def pytest_terminal_summary(
    terminalreporter: TerminalReporter,
    exitstatus: pytest.ExitCode,
    config: pytest.Config,
) -> None:
    if config.getoption("--collect-only", default=False):
        return None

    failed_reports: list[pytest.TestReport] = terminalreporter.getreports("failed")
    if not (failed_reports := [report for report in failed_reports if report.when == "call"]):
        return None

    backend_errors = [
        message
        for report in failed_reports
        for (error, message) in report.user_properties
        if error == "BackEndError"
    ]

    if backend_errors:
        terminalreporter.ensure_newline()
        terminalreporter.section("python backend errors summary", sep="-", blue=True, bold=True)
        for error, count in Counter(backend_errors).items():
            terminalreporter.line(f"{error} (occurred {count} time{'s' if count > 1 else ''})")
