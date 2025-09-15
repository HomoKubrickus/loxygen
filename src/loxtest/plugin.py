from __future__ import annotations

import re
import shlex
import subprocess
import traceback
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pytest import CallInfo
from pytest import Config
from pytest import Dir
from pytest import ExceptionInfo
from pytest import ExitCode
from pytest import TestReport

from contract.contract import LoxStatus

if TYPE_CHECKING:
    from _pytest._code.code import TerminalRepr
    from _pytest.terminal import TerminalReporter


DEFAULT_INTERPRETER = "loxygen"
DEFAULT_SKIP_DIRS = ["benchmark", "scanning", "limit", "expressions"]


@dataclass(frozen=True)
class Option:
    name: str
    help: str
    ini: dict[str, str | list[str]]
    cli: dict[str, str]
    processor: Callable | None


OPTIONS: dict[str, Option] = {
    "interpreter_cmd": Option(
        name="interpreter_cmd",
        help="The command to run the interpreter.",
        ini={"type": "string", "default": DEFAULT_INTERPRETER},
        cli={},
        processor=shlex.split,
    ),
    "skip_dirs": Option(
        name="skip_dirs",
        help="Skips tests located within the specified directory names.",
        ini={"type": "args", "default": DEFAULT_SKIP_DIRS},
        cli={"action": "append"},
        processor=None,
    ),
}


INTERPRETER_CMD_KEY = pytest.StashKey[list[str]]()
SKIP_DIRS_KEY = pytest.StashKey[list[str]]()


@dataclass
class LoxEvent:
    status: LoxStatus
    text: str


@dataclass
class ExpectedLoxEvent(LoxEvent):
    lineno: int


class LoxTestError(Exception):
    """Base exception for all errors raised by the loxtest plugin."""

    pass


class FailedTestException(LoxTestError):
    """Indicates a mismatch between test output and expected output."""

    def __init__(self, failed_lines: tuple[int], *args):
        super().__init__(*args)
        self.failed_lines = failed_lines


class BackEndError(LoxTestError):
    """Indicates a failure while trying to execute the lox interpreter."""

    def __init__(self, error: str, *args):
        super().__init__(*args)
        self.error = error


class TestItem(pytest.Item):
    def __init__(self, name: str, expected, **kwargs):
        super().__init__(name, **kwargs)
        self.name: str = name
        self.expected: list[ExpectedLoxEvent] = expected
        self.output: list[LoxEvent] = []

    def runtest(self):
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

    def run_lox(self):
        cmd = self.config.stash[INTERPRETER_CMD_KEY] + [self.path]
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

    def repr_failure(self, excinfo: ExceptionInfo, *args, **kwargs) -> str | TerminalRepr:
        if isinstance(excinfo.value, FailedTestException):
            return self.colorize(*excinfo.value.failed_lines)
        if isinstance(excinfo.value, BackEndError):
            return excinfo.value.error

        return super().repr_failure(excinfo, *args, **kwargs)

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

    def reportinfo(self):
        return self.path, 0, self.name


class LoxFile(pytest.File):
    @staticmethod
    def process_match(result: re.Match):
        for group, output in result.groupdict().items():
            if output is not None:
                return group, output

    def parse_test(self) -> list[ExpectedLoxEvent]:
        pattern = re.compile(
            rf"// expect: (?P<{LoxStatus.OK.name.lower()}>.*)|"
            rf"// (?P<{LoxStatus.STATIC_ERROR.name.lower()}>\[line \d+] Error.*)|"
            rf"// expect runtime error: (?P<{LoxStatus.RUNTIME_ERROR.name.lower()}>(.*))",
        )

        results = [
            (lineno, *self.process_match(result))
            for lineno, line in enumerate(self.path.read_text().splitlines())
            if (result := re.search(pattern, line))
        ]

        return [
            ExpectedLoxEvent(LoxStatus[group.upper()], output.strip(), lineno)
            for lineno, group, output in results
        ]

    def collect(self):
        item = TestItem.from_parent(
            self,
            name=self.path.stem,
            expected=None,
        )

        root_path = self.config.rootpath
        parts = self.path.relative_to(root_path).parent.parts
        skip_dirs = self.parent.config.stash[SKIP_DIRS_KEY]

        if not set(parts).isdisjoint(set(skip_dirs)):
            skipped_dir = set(parts).intersection(skip_dirs).pop()
            reason = f"Test located in a skipped directory: {skipped_dir}"
            item.add_marker(pytest.mark.skip(reason=reason))
        else:
            item.expected = self.parse_test()

        yield item


def pytest_addoption(parser: pytest.Parser):
    for option in OPTIONS.values():
        parser.addini(option.name, option.help, **option.ini)
        parser.addoption(f"--{option.name}", help=option.help, **option.cli)


def get_value(config: Config, option: Option):
    name = option.name
    if (value := config.getoption(name)) is None:
        value = config.getini(name)
    if (processor := option.processor) is not None:
        value = processor(value)

    return value


def pytest_configure(config: Config):
    option = OPTIONS["interpreter_cmd"]
    value = get_value(config, option)
    config.stash[INTERPRETER_CMD_KEY] = value

    option = OPTIONS["skip_dirs"]
    value = get_value(config, option)
    config.stash[SKIP_DIRS_KEY] = value


def pytest_collect_file(parent: Dir, file_path: Path):
    if file_path.suffix == ".lox":
        return LoxFile.from_parent(
            parent,
            path=file_path,
        )

    return None


def pytest_runtest_makereport(item: TestItem, call: CallInfo) -> TestReport:
    report = TestReport.from_item_and_call(item, call)
    if call.when == "call" and call.excinfo:
        if isinstance(call.excinfo.value, BackEndError):
            report.user_properties.append(
                ("BackEndError", call.excinfo.value.error.splitlines()[-1])
            )

    return report


def pytest_terminal_summary(
    terminalreporter: TerminalReporter,
    exitstatus: ExitCode,
    config: Config,
):
    if config.getoption("--collect-only", default=False):
        return None

    failed_reports: list[TestReport] = terminalreporter.getreports("failed")
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
