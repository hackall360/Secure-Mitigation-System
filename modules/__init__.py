# Shim: `modules` was renamed to `library/` (history preserved via git mv).
# This package re-exports the new location so every existing
# `from modules.* import ...` site keeps working unchanged.
# New code should import from `library.*` directly.
# See docs/REFACTOR_PLAN.md (library section).
from library import *  # noqa: F401,F403
