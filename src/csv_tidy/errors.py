"""Exceptions raised by the public API. All of them map to CLI exit code 2."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .output import ArtifactOutcome


class CsvTidyError(Exception):
    """Base class for CSV Tidy errors that are reported without a traceback."""


class ProfileError(CsvTidyError):
    """A profile file or option value is invalid or inconsistent."""


class InputError(CsvTidyError):
    """An input file cannot be opened or read."""


class OutputError(CsvTidyError):
    """An output artifact cannot be written safely.

    ``outcomes`` lists what happened to each artifact when the failure occurred after
    some artifacts were already finalized.
    """

    def __init__(self, message: str, outcomes: tuple[ArtifactOutcome, ...] = ()) -> None:
        super().__init__(message)
        self.outcomes = outcomes
