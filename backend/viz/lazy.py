"""Lazy module proxy: heavy optional libraries (scipy) load on first attribute access, keeping the serverless cold start short."""
from __future__ import annotations

from importlib import import_module


class LazyModule:
    def __init__(self, name: str) -> None:
        self._name, self._mod = name, None

    def __getattr__(self, attr: str):
        if self._mod is None:
            self._mod = import_module(self._name)
        return getattr(self._mod, attr)


sps = LazyModule("scipy.stats")
