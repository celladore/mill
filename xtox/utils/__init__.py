"""Compatibility bridge from xtox.utils to the existing utilities."""

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parents[2] / "utils")]
