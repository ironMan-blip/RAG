import time
from contextlib import contextmanager


@contextmanager
def timed(timings: list, step: str):
    """Appends {"step", "ms"} to timings once the block finishes; order = pipeline order."""
    start = time.perf_counter()
    try:
        yield
    finally:
        timings.append({"step": step, "ms": round((time.perf_counter() - start) * 1000)})
