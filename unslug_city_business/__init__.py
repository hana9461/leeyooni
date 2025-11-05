"""Minimal unslug_city_business package for signal handling."""

from .signals import SignalPayload, assemble_signals

__all__ = ["SignalPayload", "assemble_signals"]
