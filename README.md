# Loxygen: A Python Lox Interpreter and Test Tool

[![PyPI version](https://img.shields.io/badge/version-0.1.1-blue.svg)](https://pypi.org/project/loxygen/)
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/HomoKubrickus/loxygen/blob/main/LICENSE)



Loxygen is a Lox interpreter and a command-line tool for running the official Lox test suite using pytest.

The interpreter is a tree-walk Python implementation of the Lox programming language, as specified in the book [*Crafting Interpreters*](https://craftinginterpreters.com/) by [Bob Nystrom](https://journal.stuffwithstuff.com). The test tool is implemented as a `pytest` plugin. It is an alternative to the book's original test runner that provides a familiar testing environment for Python developers.

## Features

- **Lox Interpreter:** A Python implementation of the Lox language, supporting file execution and a REPL.
- **Test Suite Tool:** A command-line tool to download, process, and run the official Lox test suite using `pytest`.

## Getting Started

### 1. Installation

Install the package from PyPI using `pip`:

```bash
pip install loxygen
```

This installation provides two new commands: the `loxygen` interpreter and the `loxtest` test runner.

### 2. Running the Interpreter

The `loxygen` command runs the Lox interpreter.  Its primary use is to execute a `.lox` source file:

```bash
loxygen path/to/your/file.lox
```

Alternatively, running `loxygen` without any arguments starts an interactive session (REPL):

```bash
> var a = 3 ; print a;
3
```

To exit the REPL, simply submit an empty line.

### 3. Running Your First Test Suite

The `loxtest` tool validates a Lox interpreter against the official test suite. The workflow has two steps: setting up the suite, and then running it.

#### Step 1: Set Up the Test Suite

The `setup` command creates your local test suite. It downloads the official tests and processes them to match the specific output of the `loxygen` interpreter.

```bash
loxtest setup lox-suite
```

#### Step 2: Run the Tests

The `run` command executes the tests. It automatically discovers the `lox-suite` directory and tests the `loxygen` interpreter against it.

```bash
loxtest run
```

This will execute the full suite and display the results using the standard `pytest` output.


## Command Reference

This section provides a complete guide to the `loxtest` tool.

While `run` is the command for executing the test suite, the tests must first be fetched and processed. The `setup` command from the "Getting Started" handles this by automating two underlying commands that can also be executed manually for more control:

- `download`: Efficiently fetches the official test files, minimizing data transfer by populating only the target subdirectory.
- `process`: Formats the test files to match the specific output of the loxygen interpreter.

### The process Command

The `process` command adapts raw `.lox` test files into a runnable test suite by standardizing test expectations to match the output of the `loxygen` interpreter. The specific transformations it can apply are detailed below.

#### Transformations
You have control over two main transformations:

**1. Adding Line Numbers to Errors**

The original test suite uses different formats for its error expectations. For instance, runtime errors and certain static errors do not always include a line number on the same line as the error message.

This transformation adapts all error expectations to a single, consistent format: `[line N] Error...`.


```diff
# Adapting a runtime error
- 1 * "1"; // expect runtime error: Operands must be numbers.
+ 1 * "1"; // expect runtime error: [line 1] Operands must be numbers.

# Adapting a static error
- return "result"; // Error at 'return': Can't return a value from an initializer.
+ return "result"; // [line 3] Error at 'return': Can't return a value from an initializer.
```

This transformation can be enabled using the `--line-number` (or `-l`) flag.

**2. Normalizing Language Prefixes**

The original suite includes error expectations tagged with `[java ...]` or `[c ...]`. This transformation removes such prefixes, aligning the test expectations with interpreters that do not produce them.

```diff
-// [java line 3] Error at 'b': Expect ')' after arguments.
+// [line 3] Error at 'b': Expect ')' after arguments.
```

This transformation is disabled by default. It is intended to be used with the `--prefix` (or `-p`) flag. Test expectations on lines with prefixes that are not targeted for removal will be ignored by the test runner.

#### Usage Example
To process a directory by adding a line number to all error messages:

```
loxtest process -l static -l runtime lox-suite
```

The following adds line numbers to both static and runtime errors and removes the `java` prefix. This makes the test suite conform to the `loxygen` interpreter and is equivalent to the `setup` command.

```
loxtest process -l static -l runtime -p java lox-suite
```

### The run Command
The `run` command executes your processed test suite against a Lox interpreter using `pytest` as its test runner.

The command's structure is simple: `loxtest` recognizes its own specific options, and all other arguments are passed transparently to `pytest`.

#### Specifying the Interpreter
The primary option for loxtest is `--interpreter` (or `-i`), which specifies the **full command** used to execute your Lox interpreter. By default, it will use the `loxygen` interpreter installed with this package.

`loxtest` will pass the path to the `.lox` test file as the final argument to this command.

#### Skipping Test Directories

You can specify which test directories to skip using the `--skip-dirs` (or `-s`) flag. To skip multiple directories, use the flag for each one (e.g., `-s limit -s scanning`).

By default, `loxtest` skips four directories: `benchmark`, `expressions`, `limit`, and `scanning`. Using the `-s` flag overrides this default list entirely. Since managing a long list via the command line can be cumbersome, the `skip_dirs` parameter can also be set from a standard configuration file (e.g., `pyproject.toml`).

The command-line flag takes precedence over the configuration file. If the `skip_dirs` parameter is not explicitly defined in the configuration file, the mentioned default value is automatically used.

#### Basic Usage

```bash
# Run tests against loxygen, automatically discovering the tests.
loxtest run

# Explicitly test a script-based interpreter like loxygen
loxtest run --interpreter "python -m loxygen" lox-suite
```

**Note**: When your interpreter command contains spaces, it should be enclosed in quotes.

#### Leveraging pytest Features

All unrecognized arguments are passed directly to `pytest`, allowing you to use its command-line flags to control the test run. To view `pytest`'s own help message, use the dedicated `--pytest-help` flag, as `-h` is reserved for `loxtest`.

Here are a few common examples:

```bash
# Stop immediately on the first failure (-x)
loxtest run -x lox-suite

# Only run tests with "variables" in their name or path (-k)
loxtest run -i "python -m loxygen"  -k "variables"

# Run with verbose output to see the name of each test (-v)
loxtest run  -v lox-suite
```

## The Testing Contract

To validate your interpreter, `loxtest` executes each test file and compares its output against a set of predefined expectations. For your interpreter to pass, it must adhere to a strict contract governing three key areas: its **Error Message Format**, **Standard Streams**, and **Exit Codes**.

### 1. Error Message Format

All error messages follow a general structure composed of a line number, an optional error location, and a description: `<Line Number> <Error Location>? <Error Description>`

Since not all errors can be pinpointed to a single token, the error location is optional:
- For parser or resolver errors, the message includes the token location (e.g., `Error at ')':`).
- For runtime or scanner errors, the token location is omitted, as the error typically relates to an entire operation or line.

The line number is always formatted as `[line N]`, and the error descriptions are those found in the book.

### 2. Standard Streams

The interpreter's output is distinguished by its destination stream:

- All normal program output is written to standard output (`stdout`).
- All error messages, formatted as described above, are written to standard error (`stderr`).

### 3. Exit Codes

The interpreter uses specific exit codes to signal the final status of the execution. These are defined in the `LoxStatus` enumeration shown below:

```python
import os
from enum import IntEnum

class LoxStatus(IntEnum):
    OK = os.EX_OK                   # Exit code 0
    STATIC_ERROR = os.EX_DATAERR    # Exit code 65
    RUNTIME_ERROR = os.EX_SOFTWARE  # Exit code 70
```

## Development and Resources
This section contains information for users who want to go beyond testing and interact with the project's source code.


### A Note on Project Architecture

The `loxygen` interpreter and the `loxtest` tool are designed as two architecturally independent Python packages. This separation ensures that the test tool is not tied to any specific interpreter implementation.

The two packages are connected only by the contract defined in the `src.contract` package. This contract provides the shared `LoxStatus` enumeration, which standardizes the exit codes reported by an interpreter and verified by the test tool.

By depending only on this shared contract, the packages remain fully decoupled. While installed together for convenience, this design makes `loxtest` a reusable tool for any interpreter that adheres to the testing contract.

### AST Generator Resource
For authors following the Crafting Interpreters book, the AST nodes generator script is included as a resource. To make it easily accessible from a pip-installed version, you can export a local copy to your current directory:

```bash
loxtest export ast-generator
```

This will place `generate_ast.py` in your directory, ready to be studied or adapted for your own project.

### Working with the Source Code
To work on the project's source code itself, clone the repository and install it in "editable" mode:

```bash
git clone https://github.com/your-username/loxygen.git
cd loxygen
pip install -e .[dev]
```

The `[dev]` extra is optional and installs development tools like `pre-commit`, `mypy` and the `ruff` formatter/linter, which is also used to format the code generated by the AST script. If `ruff` is not present when the script is run, the generated code will still be functional but will not be formatted.
