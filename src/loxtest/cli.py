from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from signal import SIGINT
from subprocess import CalledProcessError
from tempfile import TemporaryDirectory

URL = "https://github.com/munificent/craftinginterpreters.git"
REMOTE_TESTS_DIR = "test"

LINE_NB_RULES: dict[str, dict[str, str]] = {
    "static": {r"(//)( Error)": r"\1 [line {line_number}]\2"},
    "runtime": {r"(// expect runtime error:)(?! \[line \d+])": r"\1 [line {line_number}]"},
}

PREFIX_RULE: dict[str, str] = {r"\[{prefix} (line \d+)]": r"[\1]"}


class CommandError(Exception):
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


def download(destination: Path, url: str, remote_tests_dir: str, force: bool = False) -> None:
    if destination.exists() and not force:
        raise FileExistsError(f"Destination '{destination}' already exists.")

    if (git := shutil.which("git")) is None:
        raise FileNotFoundError("Command 'git' not found.")

    print(f"Downloading tests to '{destination}'...")
    with TemporaryDirectory() as temp_dir:
        commands = [
            [git, "clone", "--no-checkout", "--depth=1", "--filter=blob:none", url, "."],
            [git, "sparse-checkout", "set", "--no-cone", remote_tests_dir],
            [git, "checkout"],
        ]
        for cmd in commands:
            subprocess.run(
                cmd,
                cwd=temp_dir,
                check=True,
                capture_output=True,
                text=True,
            )

        if destination.exists():
            shutil.rmtree(destination)

        source = Path(temp_dir) / remote_tests_dir
        shutil.move(source, destination)


def process_rules(
    line_nb_rules: dict[str, dict[str, str]],
    prefix_rule: dict[str, str],
    line_number: list[str],
    prefixes: list[str],
) -> dict[re.Pattern[str], str]:
    result: dict[str, str] = {}

    result.update(
        {
            pattern: replacement
            for mode in line_number
            for pattern, replacement in line_nb_rules[mode].items()
        }
    )
    result.update(
        {
            pattern.format(prefix=prefix): replacement
            for prefix in prefixes
            for pattern, replacement in prefix_rule.items()
        }
    )

    return {re.compile(pattern): replacement for pattern, replacement in result.items()}


def process_file(path: Path, rules: dict[re.Pattern[str], str]) -> None:
    text = path.read_text()
    has_trailing_newline = text.endswith("\n")
    lines = text.splitlines()
    for nb, line in enumerate(lines, 1):
        for pattern, replacement in rules.items():
            line = re.sub(pattern, replacement.format(line_number=nb), line)
        lines[nb - 1] = line

    text = "\n".join(lines) + "\n" * has_trailing_newline
    path.write_text(text)


def process_directory(
    path: Path,
    line_nb_rules: dict[str, dict[str, str]],
    prefix_rule: dict[str, str],
    line_number: list[str],
    prefixes: list[str],
) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Directory '{path}' does not exist.")
    if not path.is_dir():
        raise ValueError(f"Path '{path}' is not a directory.")
    if not (paths := list(path.rglob("*.lox"))):
        raise FileNotFoundError(f"No '.lox' files found in '{path}'.")

    print(f"Processing files in '{path}'...")
    active_rules = process_rules(line_nb_rules, prefix_rule, line_number, prefixes)
    for path in paths:
        process_file(path, active_rules)
    print("Processing complete.")


def handle_download(args: argparse.Namespace) -> None:
    download(
        args.directory,
        args.url,
        args.remote_tests_dir,
        args.force,
    )


def handle_process(args: argparse.Namespace) -> None:
    process_directory(
        args.directory,
        args.line_nb_rules,
        args.prefix_rule,
        args.line_number,
        args.prefix,
    )


def handle_run(args: argparse.Namespace, *unknown_args: str) -> None:
    cmd = ["pytest"]
    if args.pytest_help:
        cmd.append("--help")
    else:
        if args.interpreter_cmd:
            cmd.extend(["--interpreter-cmd", args.interpreter_cmd])
        if args.skip_dirs:
            cmd.extend([item for dir in args.skip_dirs for item in ("--skip-dirs", dir)])

    cmd.extend(list(unknown_args))

    try:
        process = subprocess.run(cmd)
    except OSError as e:
        # exit code that doesn't conflict with pytest's exit codes (0-5)
        raise CommandError(str(e), exit_code=6) from e

    sys.exit(process.returncode)


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("A toolkit for downloading and running the official Lox test suite."),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    path_parser = argparse.ArgumentParser(add_help=False)
    path_parser.add_argument(
        "directory",
        type=Path,
        metavar="PATH",
        help="Directory where the operation will be performed.",
    )

    parser_download = subparsers.add_parser(
        "download",
        parents=[path_parser],
        help="Download the official Lox test suite.",
    )
    parser_download.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite destination directory if it exists.",
    )
    parser_download.set_defaults(
        func=handle_download,
        url=URL,
        remote_tests_dir=REMOTE_TESTS_DIR,
    )

    parser_process = subparsers.add_parser(
        "process",
        parents=[path_parser],
        help="Process an existing directory of Lox tests.",
    )
    parser_process.add_argument(
        "-l",
        "--line-number",
        action="append",
        metavar="MODE",
        choices=["static", "runtime"],
        default=[],
        help="Add '[line N]' to errors. (Choices: 'static', 'runtime').",
    )
    parser_process.add_argument(
        "-p",
        "--prefix",
        action="append",
        metavar="PREFIX",
        choices=["java", "c"],
        default=[],
        help="Remove a language prefix. (Choices: 'java', 'c').",
    )
    parser_process.set_defaults(
        func=handle_process, line_nb_rules=LINE_NB_RULES, prefix_rule=PREFIX_RULE
    )

    parser_run = subparsers.add_parser(
        "run",
        help="Run tests against a Lox interpreter.",
    )
    parser_run.add_argument(
        "--pytest-help",
        action="store_true",
        help="Display pytest's help message and exit.",
    )
    parser_run.add_argument(
        "-i",
        "--interpreter-cmd",
        metavar="CMD",
        help="The command to run the interpreter.",
    )
    parser_run.add_argument(
        "-d",
        "--skip-dirs",
        action="append",
        metavar="DIR",
        help="Skip tests within the specified subdirectory (e.g., benchmark)."
        " Can be specified multiple times.",
    )
    parser_run.set_defaults(func=handle_run)

    return parser


def get_parsed_arguments() -> tuple[argparse.Namespace, list[str]]:
    parser = get_parser()
    args, unknown_args = parser.parse_known_args()
    if args.command != "run" and unknown_args:
        parser.parse_args()
    if args.command == "process" and not (args.line_number or args.prefix):
        parser.error("no transformation specified.")

    return args, unknown_args


def main() -> None:
    args, unknown_args = get_parsed_arguments()

    try:
        args.func(args, *unknown_args)
    except (CalledProcessError, CommandError, OSError, ValueError) as e:
        exit_code = e.exit_code if isinstance(e, CommandError) else 1

        msg = f"Error: {e}"
        if isinstance(e, CalledProcessError):
            msg = f"{e.stderr.strip()}\n{msg}"

        print(msg, file=sys.stderr)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nOperation aborted by user.", file=sys.stderr)
        sys.exit(128 + SIGINT)


if __name__ == "__main__":
    main()
