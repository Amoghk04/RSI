"""Benchmark adapters (YELLOW). May import core; core must not import adapters."""

from rsi_harness.adapters.registry import load_adapter

__all__ = ["load_adapter"]
