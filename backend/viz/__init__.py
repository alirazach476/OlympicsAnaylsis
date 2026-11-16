"""Visualization library: registry of chart builders (see core.py) + coverage evaluation."""
from importlib import import_module

from .core import REGISTRY, SECTIONS, Ctx, Spec, Unavailable, evaluate  # noqa: F401

for _m in ("charts_time", "charts_country", "charts_athlete", "charts_sports", "charts_stats", "charts_ml", "charts_team", "charts_eng"):
    try:
        import_module(f"{__name__}.{_m}")
    except ModuleNotFoundError as exc:  # section not written yet
        if _m not in str(exc):
            raise
