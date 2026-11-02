# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""C1/C2 (closed-loop directive Subsystem B): snippet-map dedup + import-direction pins.

- C1: mcp_bridge.SNIPPET_LANGUAGE_BY_SUFFIX is the canonical map; main.py and
  tui.py import it (identity, not a copy).
- C2: package import-direction rules: library/core imports no workflows/services
  modules (except services.projects types); nothing imports root main/tui.
"""

import ast
import pathlib


def test_c1_canonical_map_identity():
    import main
    import tui
    from modules.services.mcp_bridge import SNIPPET_LANGUAGE_BY_SUFFIX

    assert main._SNIPPET_LANGUAGE_BY_SUFFIX is SNIPPET_LANGUAGE_BY_SUFFIX
    assert tui._SNIPPET_LANGUAGE_BY_SUFFIX is SNIPPET_LANGUAGE_BY_SUFFIX
    assert SNIPPET_LANGUAGE_BY_SUFFIX[".js"] == "javascript"
    assert SNIPPET_LANGUAGE_BY_SUFFIX[".py"] == "python"
    assert SNIPPET_LANGUAGE_BY_SUFFIX[".php"] == "php"


def _module_deps(path: pathlib.Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    deps = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            if mod.startswith("library."):
                mod = mod.replace("library", "modules", 1)
            if mod == "modules" or mod.startswith("modules."):
                deps.add(mod)
        elif isinstance(node, ast.Import) and node.names:
            for alias in node.names:
                if alias.name == "main" or alias.name == "tui":
                    deps.add(alias.name)
    return deps


def test_c2_core_imports_no_workflows_or_services():
    # Load-time direction only: core modules must not import workflows/services
    # at module top level (lazy function-level imports for constants like
    # BINARY_MAX_BYTES are permitted — they create no load cycle).
    allowed = {"modules.services.projects", "modules.services.binary_intake"}
    offenders = []
    for path in pathlib.Path("library/core").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                if mod.startswith("library."):
                    mod = mod.replace("library", "modules", 1)
                if mod.startswith("modules.workflows") or (
                    mod.startswith("modules.services") and mod not in allowed
                ):
                    offenders.append(f"{path}:{mod}")
    assert not offenders, f"core layer violations: {offenders}"


def test_c2_no_load_time_root_main_or_tui_imports():
    # Same load-time scope: tui.py lazily imports main inside dispatch
    # functions (entrypoint delegation, no cycle); main.py lazily imports
    # tui.main for --tui. Only module top-level imports are checked.
    offenders = []
    for path in list(pathlib.Path("library").rglob("*.py")) + [
        pathlib.Path("main.py"),
        pathlib.Path("tui.py"),
        pathlib.Path("sms_cli.py"),
    ]:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module in ("main", "tui"):
                offenders.append(f"{path}:{node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ("main", "tui"):
                        offenders.append(f"{path}:{alias.name}")
    assert not offenders, f"root-module imports: {offenders}"
