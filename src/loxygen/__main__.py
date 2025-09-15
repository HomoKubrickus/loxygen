from __future__ import annotations

import sys

from loxygen.loxygen import Lox


def main():
    Lox().main(sys.argv[1:])


if __name__ == "__main__":
    main()
