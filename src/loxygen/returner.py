from __future__ import annotations


class Return(RuntimeError):
    def __init__(self, value):
        super().__init__()
        self.value = value
