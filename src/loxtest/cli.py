from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

URL = "https://github.com/munificent/craftinginterpreters.git"
REMOTE_TESTS_DIR = "test"


RULES = {
    "line_number": {
        "static": {r"(//)( Error)": r"\1 [line {line_number}]\2"},
        "runtime": {r"(// expect runtime error:)(?! \[line \d+])": r"\1 [line {line_number}]"},
    },
    "remove_prefix": {
        "default": {r"\[{prefix} (line \d+)]": r"[\1]"},
    },
}

RESOURCES = {
    "ast-generator": "generate_ast.py",
    "ast-printer": "print_ast.py",
}


def download(destination: Path, url: str, remote_tests_dir: str, force: bool = False):
    if destination.exists() and not force:
        raise FileExistsError(f"Destination '{destination}' already exists.")

    if (git := shutil.which("git")) is None:
        raise FileNotFoundError("Command 'git' not found.")

    print(f"Downloading tests to '{destination}'...")
    with TemporaryDirectory() as temp_dir:
        commands = [
            [git, "clone", "--no-checkout", "--depth=1", "--filter=blob:none", url, "."],
            ["git", "sparse-checkout", "set", "--no-cone", remote_tests_dir],
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


def process_file(path: Path, rules: dict[re.Pattern, str]):
    text = path.read_text()
    has_trailing_newline = text.endswith("\n")
    lines = text.splitlines()
    for nb, line in enumerate(lines, 1):
        for pattern, replacement in rules.items():
            line = re.sub(pattern, replacement.format(line_number=nb), line)
        lines[nb - 1] = line

    text = "\n".join(lines) + "\n" * has_trailing_newline
    path.write_text(text)


def get_prefix_rules(
    rules: dict[str, dict[str, dict[str, str]]], prefixes: list[str]
) -> dict[str, str]:
    rule = rules["remove_prefix"]["default"]
    pattern, replacement = next(iter(rule.items()))

    return {pattern.format(prefix=prefix): replacement for prefix in prefixes}


def get_line_number_rules(
    rules: dict[str, dict[str, dict[str, str]]], line_number: list[str]
) -> dict[str, str]:
    return {
        pattern: replacement
        for mode in line_number
        for pattern, replacement in rules["line_number"][mode].items()
    }


def process_rules(
    rules: dict[str, dict[str, dict[str, str]]], line_number: list[str], prefixes: list[str]
):
    result: dict[str, str] = {}

    result.update(get_line_number_rules(rules, line_number))
    result.update(get_prefix_rules(rules, prefixes))

    return {re.compile(pattern): replacement for pattern, replacement in result.items()}


def process_directory(
    path: Path,
    rules: dict[str, dict[str, dict[str, str]]],
    line_number: list[str],
    prefixes: list[str],
):
    print(f"Processing files in '{path}'...")
    paths = path.rglob("*.lox")
    active_rules = process_rules(rules, line_number, prefixes)
    for path in paths:
        process_file(path, active_rules)
    print("Processing complete.")


def handle_setup(args: argparse.Namespace):
    download(args.directory, args.url, args.remote_tests_dir, args.force)
    process_directory(args.directory, args.rules, args.line_number, args.prefixes)


def handle_download(args: argparse.Namespace):
    try:
        download(
            args.directory,
            args.url,
            args.remote_tests_dir,
            args.force,
        )
    except (FileExistsError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def handle_process(args: argparse.Namespace):
    if not (args.line_number or args.prefix):
        args.parser.error("no transformation specified.")

    process_directory(
        args.directory,
        args.rules,
        args.line_number,
        args.prefix,
    )


def handle_run(args: argparse.Namespace, *unknown_args):
    cmd = ["pytest"]
    if args.pytest_help:
        subprocess.run(cmd + ["--help"])
        return
    if args.interpreter_cmd:
        cmd.extend(["--interpreter_cmd", args.interpreter_cmd])
    if args.skip_dirs:
        cmd.extend([item for dir in args.skip_dirs for item in ["--skip_dirs", dir]])

    cmd.extend(list(unknown_args))
    subprocess.run(cmd)


def handle_clean(args: argparse.Namespace):
    if not args.directory.is_dir():
        print(f"Error:Directory not found: {args.directory}", file=sys.stderr)
        sys.exit(1)

    if not (force := args.force):
        response = input(f"Are you sure you want to permanently delete {args.directory}? [y/N] ")
        force = response.lower() == "y"

    if force:
        shutil.rmtree(args.directory)
        print(f"Successfully removed {args.directory}")
    else:
        print("The 'clean' command was cancelled.")


def handle_export(args: argparse.Namespace):
    for resource in set(args.resource):
        project_root = Path(__file__).parent.parent.parent
        resource_path = project_root / "scripts" / RESOURCES[resource]
        destination_path = Path.cwd() / resource_path.name
        if destination_path.exists() and not args.force:
            print("File already exists. Use --force to overwrite.", file=sys.stderr)
            sys.exit(1)
        shutil.copy(resource_path, destination_path)
        print(f"Exported '{resource_path.name}' to current directory.")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "A toolkit for downloading and running the Crafting Interpreters Lox test suite."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    path_parser = argparse.ArgumentParser(add_help=False)
    path_parser.add_argument(
        "directory",
        type=Path,
        help="Directory where the operation will be performed.",
    )

    force_parser = argparse.ArgumentParser(add_help=False)
    force_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite destination directory if it exists.",
    )

    parser_setup = subparsers.add_parser(
        "setup",
        parents=[path_parser, force_parser],
        help="Download and process all tests in one step.",
    )
    parser_setup.set_defaults(
        func=handle_setup,
        url=URL,
        remote_tests_dir=REMOTE_TESTS_DIR,
        rules=RULES,
        line_number=["static", "runtime"],
        prefixes=["java"],
    )

    parser_download = subparsers.add_parser(
        "download",
        parents=[path_parser, force_parser],
        help="Download the official Lox test suite.",
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
        "--line_number",
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
    parser_process.set_defaults(func=handle_process, rules=RULES)

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
        "--interpreter_cmd",
        metavar="CMD",
        help="The command to run the interpreter.",
    )
    parser_run.add_argument(
        "-s",
        "--skip_dirs",
        action="append",
        metavar="DIR",
        help="Skip tests within the specified subdirectory (e.g., benchmark)."
        " Can be specified multiple times.",
    )
    parser_run.set_defaults(func=handle_run)

    parser_clean = subparsers.add_parser(
        "clean",
        parents=[path_parser, force_parser],
        help="Remove a directory of downloaded tests.",
    )
    parser_clean.set_defaults(func=handle_clean)

    parser_export = subparsers.add_parser(
        "export",
        parents=[force_parser],
        help="Export a resource to the current directory.",
    )
    parser_export.add_argument(
        "resource",
        nargs="+",
        choices=["ast-generator", "ast-printer"],
        help="The resource to export.",
    )
    parser_export.set_defaults(func=handle_export)

    args, unknown_args = parser.parse_known_args()
    if args.command != "run" and unknown_args:
        parser.parse_args()
    args.parser = parser
    args.func(args, *unknown_args)


if __name__ == "__main__":
    main()
