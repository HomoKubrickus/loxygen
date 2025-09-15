from __future__ import annotations

from time import perf_counter_ns


class Callable:
    def call(self, interpreter, arguments):
        pass

    def arity(self):
        pass


class Clock(Callable):
    @staticmethod
    def call(self, interpreter, arguments):
        return perf_counter_ns() * 1000

    def arity(self):
        return 0

    def __repr__(self):
        return "<native fn>"
