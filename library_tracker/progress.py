"""Progress output of long-running steps: stderr, so stdout stays for results."""
from __future__ import annotations

import sys


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
