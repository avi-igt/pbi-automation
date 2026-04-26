"""Shared logging setup for pbi-automation entry points.

When --log is active, all output (both print() and logging calls) is
captured to a timestamped file under output/.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


class _Tee:
    """Write to multiple streams simultaneously."""

    def __init__(self, *streams):
        self._streams = streams
        self.encoding = getattr(streams[0], "encoding", "utf-8")
        self.errors = getattr(streams[0], "errors", "replace")

    def write(self, data):
        for s in self._streams:
            s.write(data)

    def flush(self):
        for s in self._streams:
            s.flush()

    def isatty(self):
        return self._streams[0].isatty() if hasattr(self._streams[0], "isatty") else False

    def reconfigure(self, **kwargs):
        for s in self._streams:
            if hasattr(s, "reconfigure"):
                s.reconfigure(**kwargs)


def setup_file_logging(output_dir: str = "output", verbose: bool = False) -> Path:
    """Configure logging + stdout/stderr tee to a timestamped log file.

    Returns the log file path.
    """
    ts = datetime.now().strftime("%Y-%m-%d-%H-%M")
    log_dir = Path(output_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"pbi-automation-{ts}.log"

    log_file = open(log_path, "w", encoding="utf-8")

    sys.stdout = _Tee(sys.stdout, log_file)
    sys.stderr = _Tee(sys.stderr, log_file)

    level = logging.DEBUG if verbose else logging.INFO
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")
    )
    file_handler.setLevel(level)

    root = logging.getLogger()
    root.addHandler(file_handler)

    logging.info("Log file: %s", log_path)
    return log_path
