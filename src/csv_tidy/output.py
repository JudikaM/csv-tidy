"""Safe artifact writing: path identity checks, overwrite refusal, per-file atomic writes."""

from __future__ import annotations

import contextlib
import csv
import errno
import io
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .errors import OutputError

LINE_TERMINATORS = {"crlf": "\r\n", "lf": "\n"}


@dataclass(frozen=True)
class ArtifactOutcome:
    """What happened to one artifact: "written", "not_written" or "failed"."""

    kind: str
    path: str
    status: str
    error: str | None = None


def same_file(a: Path, b: Path) -> bool:
    """True if ``a`` and ``b`` name the same file, including symlink and hardlink aliases."""
    if os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve())):
        return True
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def validate_artifact_paths(
    protected: Mapping[str, Path], artifacts: Mapping[str, Path | None], overwrite: bool
) -> None:
    """Reject artifacts that alias an input, alias each other, or exist without ``overwrite``.

    ``protected`` maps a label (e.g. "input CSV") to a path that must never be written.
    """
    chosen = {kind: Path(p) for kind, p in artifacts.items() if p is not None}
    for kind, path in chosen.items():
        for label, source in protected.items():
            if same_file(path, Path(source)):
                raise OutputError(
                    f"the {kind} path {path} refers to the {label}; refusing to overwrite it"
                )
        if path.exists() and path.is_dir():
            raise OutputError(f"the {kind} path {path} is a directory")
    kinds = list(chosen)
    for i, first in enumerate(kinds):
        for second in kinds[i + 1 :]:
            if same_file(chosen[first], chosen[second]):
                raise OutputError(
                    f"the {first} and {second} paths refer to the same file: {chosen[first]}"
                )
    if not overwrite:
        for kind, path in chosen.items():
            if path.exists():
                raise OutputError(
                    f"the {kind} file already exists: {path} (use --overwrite to replace it)"
                )


def write_atomic(path: Path, data: bytes, overwrite: bool) -> None:
    """Write ``data`` to a temporary file next to ``path`` and move it into place.

    On failure the temporary file is removed and any existing ``path`` is left unchanged.
    The write is atomic per file, not across several artifacts.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".csv-tidy.tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _finalize(temp_name, path, overwrite)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_name)
        raise


# Windows: os.rename refuses an existing destination. Elsewhere os.rename would replace it,
# so a hard link is used instead. Module-level so tests can exercise both strategies.
_RENAME_IS_NO_CLOBBER = os.name == "nt"
_NO_HARDLINK_ERRNOS = {errno.EPERM, errno.EXDEV, errno.EMLINK, errno.ENOTSUP, errno.EOPNOTSUPP}


def _finalize(temp_name: str, path: Path, overwrite: bool) -> None:
    """Move the finished temporary file into place, atomically.

    With ``overwrite`` the replacement uses ``os.replace``. Without it, the final step itself
    refuses an existing destination, so a file created by another process after the earlier
    checks is never replaced: ``os.rename`` on Windows and ``os.link`` elsewhere fail if the
    destination exists. Where hard links are unavailable, the write fails instead of falling
    back to a non-atomic copy that could expose a partial file.
    """
    if overwrite:
        os.replace(temp_name, path)
        return
    try:
        if _RENAME_IS_NO_CLOBBER:
            os.rename(temp_name, path)
            return
        os.link(temp_name, path)
    except FileExistsError:
        raise OutputError(
            f"{path} was created by another process while writing; refusing to overwrite it"
        ) from None
    except OSError as exc:
        if _RENAME_IS_NO_CLOBBER or exc.errno not in _NO_HARDLINK_ERRNOS:
            raise
        raise OutputError(
            f"cannot create {path} without risking a partial or overwritten file: this file "
            f"system does not support hard links ({exc.strerror or exc}). Write to another "
            "location, or use --overwrite if replacing an existing file there is acceptable."
        ) from None
    os.unlink(temp_name)


def render_csv(
    header: Sequence[str], rows: Iterable[Sequence[str]], delimiter: str, line_ending: str
) -> str:
    """Serialize rows with minimal quoting. Fields containing CR or LF are always quoted."""
    terminator = LINE_TERMINATORS[line_ending]
    out = io.StringIO()
    row_buffer = io.StringIO()
    writer = csv.writer(
        row_buffer,
        delimiter=delimiter,
        quotechar='"',
        doublequote=True,
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\r\n",
    )
    for row in [header, *rows]:
        row_buffer.seek(0)
        row_buffer.truncate()
        writer.writerow(row)
        text = row_buffer.getvalue()
        out.write(text[:-2] + terminator)
    return out.getvalue()


def encode_text(text: str, encoding: str, what: str) -> bytes:
    try:
        return text.encode(encoding, errors="strict")
    except UnicodeEncodeError as exc:
        raise OutputError(
            f"cannot encode the {what} as {encoding}: "
            f"character {exc.object[exc.start]!r} is not representable"
        ) from None


def write_artifact(path: Path, data: bytes, overwrite: bool, kind: str) -> ArtifactOutcome:
    try:
        write_atomic(path, data, overwrite)
    except OutputError:
        raise
    except OSError as exc:
        raise OutputError(f"cannot write the {kind} {path}: {exc.strerror or exc}") from None
    return ArtifactOutcome(kind, str(path), "written")
