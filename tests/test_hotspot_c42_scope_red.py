# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (C42 hotspot revisit): unguarded recursive merge must reject dunder keys.

C42's Node fixture was harness-incompatible (process-global prototype
pollution breaks pre/post differential gates). The portable residual,
pinned here for the Python side: a recursive merge that setattr()s keys
onto a config object lets `__class__`/`__dict__`-style dunder keys
overwrite behavior. The merge must refuse dunder keys; the read side is
then safe by construction.
"""


class _Config:
    role = "user"


def _merge_attrs(target: object, src: dict) -> object:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(getattr(target, key, None), dict):
            _merge_attrs(getattr(target, key), value)
        else:
            setattr(target, key, value)
    return target


def _merge_attrs_guarded(target: object, src: dict) -> object:
    for key, value in src.items():
        if not isinstance(key, str) or key.startswith("__"):
            raise ValueError("dunder keys rejected")
        if isinstance(value, dict) and isinstance(getattr(target, key, None), dict):
            _merge_attrs_guarded(getattr(target, key), value)
        else:
            setattr(target, key, value)
    return target


def test_unguarded_merge_allows_dunder_overwrite():
    cfg = _Config()
    _merge_attrs(cfg, {"__evil_flag__": "pwned", "role": "admin"})
    assert cfg.__evil_flag__ == "pwned"
    assert cfg.role == "admin"


def test_guarded_merge_rejects_dunder_keys():
    cfg = _Config()
    try:
        _merge_attrs_guarded(cfg, {"__evil_flag__": "pwned"})
    except ValueError:
        pass
    assert not hasattr(cfg, "__evil_flag__")
    assert _merge_attrs_guarded(_Config(), {"role": "admin"}).role == "admin"
