from __future__ import annotations

from enum import IntEnum
from os import EX_DATAERR
from os import EX_OK
from os import EX_SOFTWARE


class LoxStatus(IntEnum):
    OK = EX_OK
    STATIC_ERROR = EX_DATAERR
    RUNTIME_ERROR = EX_SOFTWARE
