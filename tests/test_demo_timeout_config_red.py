# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): model timeout configurability (found live 2026-11-03 dry run).

The deep-sweep red call timed out 4x in a row (392 s of model-call time:
180 s x4 + ladder waits) and killed a 10-minute live demo run. The timeout
knob exists (META_MUSE_TIMEOUT_SECONDS) but is too rigid for real use:

Gap 1 — default 180 s is too short for heavy passes. The standard red call
answered in 166 s (near the limit); the deep red call never answers within
180 s. Default must rise to 300 s.

Gap 2 — 0 must mean "no timeout" (wait as long as the model needs). Today
0 fails validation (1..300), so there is no way to say "this production
run is worth whatever it takes." 0 = httpx Timeout(None) (connect stays
bounded; only the read wait is uncapped).

Gap 3 — the knob is env-only. A demo run (Spark red / Wonder blue,
balanced) and a production run (Spark/Spark, economy, cheaper showcase)
need different budgets on the SAME server without restarting it. Timeout
must ride the WS query string (?timeout_s=) and the profile, same as
sweep_passes and research do.

This pin asserts the contract:
- default api_timeout_seconds == 300.0
- 0 validates (means no read timeout downstream)
- _request honors per-call timeout_s (query/plumbing), not only config
- economy profile is Spark/Spark (the cheap production showcase pairing)
"""

from __future__ import annotations


def test_timeout_defaults_to_five_minutes():
    from library.core.config import PurpleBoxConfig

    assert PurpleBoxConfig(meta_api_key="unit-test-key").api_timeout_seconds == 300.0


def test_zero_timeout_validates_as_no_timeout():
    from library.core import config as config_mod

    cfg = config_mod.PurpleBoxConfig(meta_api_key="unit-test-key", api_timeout_seconds=0)
    cfg.validate()  # must not raise: 0 = wait as long as the model needs


def test_request_honors_per_call_timeout_override():
    import inspect

    from library.core import agents as agents_mod

    src = inspect.getsource(agents_mod.MetaMuseClient._request)
    assert "timeout_s" in src, (
        "_request must accept a per-call timeout_s override (WS ?timeout_s=), "
        "not read config.api_timeout_seconds only"
    )


def test_economy_is_spark_spark_cheap_showcase():
    from library.core.profiles import META_PROFILES

    eco = META_PROFILES["economy"]
    assert eco.red_model == "muse-spark-1.3-contributor"
    assert eco.blue_model == "muse-spark-1.3-contributor"


def test_balanced_stays_spark_wonder():
    from library.core.profiles import META_PROFILES

    bal = META_PROFILES["balanced"]
    assert bal.red_model == "muse-spark-1.3-contributor"
    assert bal.blue_model == "muse-wonder-1.0"
