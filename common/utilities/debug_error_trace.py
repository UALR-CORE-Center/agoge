"""Locate local debug failures without exposing exception or request payloads."""
from pathlib import Path
from traceback import walk_tb


def safe_error_trace(error: BaseException, root: Path | str) -> list[dict]:
    """Return at most eight repository frame locations, oldest to newest.

    Only code filenames, function names, and line numbers are inspected. Never
    format the exception, source lines, frame locals, or SDK response metadata.
    Virtual environments can live inside a checkout, so omit their frames too.
    """
    root = Path(root).resolve()
    frames = []
    for frame, line in walk_tb(error.__traceback__):
        filename = frame.f_code.co_filename
        if not filename or filename.startswith('<'):
            continue
        try:
            relative = Path(filename).resolve().relative_to(root)
        except (OSError, RuntimeError, ValueError):
            continue
        parts = tuple(part.lower() for part in relative.parts)
        if (parts and parts[0] in {'venv', '.venv', 'env', '.env'}
                or any(part in {'site-packages', 'dist-packages'} for part in parts)):
            continue
        frames.append({'file': relative.as_posix(), 'line': line,
                       'function': frame.f_code.co_name})
    return frames[-8:]
