"""CSV Tidy: validate and explicitly clean CSV files with declared number and date formats.

Public API::

    from csv_tidy import check_file, clean_file, export_clean, load_profile

See docs/ARCHITECTURE.md for the result model and exceptions.
"""

__version__ = "0.1.0"

from .api import CheckResult, CleanResult, ScanInfo, check_file, clean_file, export_clean
from .batch import BatchResult, run_batch, select_inputs
from .errors import CsvTidyError, InputError, OutputError, ProfileError
from .normalization import FieldChange, RemovedRecord
from .output import ArtifactOutcome
from .schema import ColumnSpec, Overrides, Profile, Settings, load_profile, profile_to_toml
from .validation import Issue

__all__ = [
    "ArtifactOutcome",
    "BatchResult",
    "CheckResult",
    "CleanResult",
    "ColumnSpec",
    "CsvTidyError",
    "FieldChange",
    "InputError",
    "Issue",
    "OutputError",
    "Overrides",
    "Profile",
    "ProfileError",
    "RemovedRecord",
    "ScanInfo",
    "Settings",
    "__version__",
    "check_file",
    "clean_file",
    "export_clean",
    "load_profile",
    "profile_to_toml",
    "run_batch",
    "select_inputs",
]
