# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): signature guard is shallow — methods, kwonly, defaults invisible.

_extract_signatures only walks tree.body (module level): methods inside
classes are NOT counted, so deleting/renaming a method passes the guard
silently. And it counts len(args.args) only: kwonly args, *args/**kwargs,
defaults, and posonly markers are invisible — a patch that adds a
required kwonly param (breaking all callers) counts as "same signature".

Parity contract:
- Walk the FULL tree (ast.walk): qualify methods as Class.method so a
  deleted/renamed method rejects.
- Count the full signature shape: positional params, kwonly params,
  *args/**kwargs presence, and defaults count. Any change rejects.
"""

from __future__ import annotations


def test_methods_are_guarded():
    from modules.workflows.project_workflow import _extract_signatures

    funcs, _ = _extract_signatures("class A:\n    def keep(self):\n        pass\n")
    assert "A.keep" in funcs, "methods must be signature-guarded, not just module funcs"


def test_full_signature_shape_guarded():
    from modules.workflows.project_workflow import _extract_signatures

    base, _ = _extract_signatures("def f(a, b=1, *, c):\n    pass\n")
    same, _ = _extract_signatures("def f(a, b=2, *, c):\n    pass\n")
    assert base == same, "default VALUE changes are fine (behavior-preserving)"
    changed, _ = _extract_signatures("def f(a, b=1, *, c, d=2):\n    pass\n")
    assert base != changed, "added kwonly param must change the guarded shape"
    star, _ = _extract_signatures("def f(a, *args):\n    pass\n")
    plain, _ = _extract_signatures("def f(a):\n    pass\n")
    assert star != plain, "*args presence must change the guarded shape"
