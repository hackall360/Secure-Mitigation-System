# Shim for library/workflows (see modules/__init__.py + docs/REFACTOR_PLAN.md).
import sys as _sys

_sub = __import__("library.workflows", fromlist=["*"])
_sys.modules[__name__] = _sub
