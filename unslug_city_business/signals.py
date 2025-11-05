"""Application-specific signal definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True, slots=True)
class SignalPayload:
    """Serializable payload describing a signal for a financial instrument."""

    symbol: str
    score: float


def assemble_signals(payloads: Iterable[SignalPayload]) -> List[SignalPayload]:
    """Normalize an iterable of payloads into a list.

    Parameters
    ----------
    payloads:
        Arbitrary iterable of :class:`SignalPayload` instances.

    Returns
    -------
    list of SignalPayload
        Materialized list of the provided payloads.
    """

    if isinstance(payloads, Sequence):
        return list(payloads)
    return [*payloads]


__all__ = ["SignalPayload", "assemble_signals"]
