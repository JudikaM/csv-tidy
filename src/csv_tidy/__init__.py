"""CSV Tidy: validate and explicitly clean CSV files with declared number and date formats.

The public API is the set of names in ``__all__`` (see docs/STABILITY.md), mainly::

    from csv_tidy import check_file, clean_file, export_clean, load_profile
    from csv_tidy import profile_to_toml, run_batch, select_inputs

See docs/ARCHITECTURE.md for the result model and exceptions.
"""

__version__ = "1.0.0"

from .api import CheckResult, CleanResult, ScanInfo, check_file, clean_file, export_clean
from .batch import BatchInput, BatchResult, FileOutcome, run_batch, select_inputs
from .errors import CsvTidyError, InputError, OutputError, ProfileError
from .normalization import FieldChange, RemovedRecord
from .output import ArtifactOutcome
from .reader import FatalError
from .schema import (
    ColumnSpec,
    OutputSettings,
    Overrides,
    Profile,
    Settings,
    SourceSettings,
    load_profile,
    profile_to_toml,
)
from .validation import Issue

__all__ = [
    "ArtifactOutcome",
    "BatchInput",
    "BatchResult",
    "CheckResult",
    "CleanResult",
    "ColumnSpec",
    "CsvTidyError",
    "FatalError",
    "FieldChange",
    "FileOutcome",
    "InputError",
    "Issue",
    "OutputError",
    "OutputSettings",
    "Overrides",
    "Profile",
    "ProfileError",
    "RemovedRecord",
    "ScanInfo",
    "Settings",
    "SourceSettings",
    "__version__",
    "check_file",
    "clean_file",
    "export_clean",
    "load_profile",
    "profile_to_toml",
    "run_batch",
    "select_inputs",
]
