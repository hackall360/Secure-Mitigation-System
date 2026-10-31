# Shim: `modules` was renamed to `library/` (history preserved via git mv).
# Single-copy alias via a meta-path finder: `modules.x.y` resolves through
# the canonical `library.x.y` module spec, so both spellings share ONE
# module object (no double execution, `is` identity holds).
# New code should import from `library.*` directly.
# See docs/REFACTOR_PLAN.md (library section).
import importlib.abc as _abc
import importlib.machinery as _machinery
import sys as _sys


class _LibraryAliasLoader(_abc.Loader):
    def create_module(self, spec):
        import importlib as _importlib

        canonical = "library." + spec.name[len("modules."):]
        return _importlib.import_module(canonical)

    def exec_module(self, module):
        return None


class _LibraryAliasFinder(_abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "modules" or not fullname.startswith("modules."):
            return None
        return _machinery.ModuleSpec(fullname, _LibraryAliasLoader())


_sys.meta_path.insert(0, _LibraryAliasFinder())
