# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED test for the model swap: red default must be muse-spark-1.3-contributor.

LAW 9 red-first: written BEFORE the swap, fails on unpatched code.
"""

from modules.core.config import ConfigurationError, PurpleBoxConfig, load_config
from modules.core.pricing import estimate_cost
from modules.core.profiles import META_PROFILES


def test_red_default_is_contributor():
    assert PurpleBoxConfig().red_team_model == "muse-spark-1.3-contributor"


def test_default_env_loads_contributor(monkeypatch):
    monkeypatch.delenv("META_MUSE_RED_MODEL", raising=False)
    assert load_config().red_team_model == "muse-spark-1.3-contributor"


def test_economy_and_balanced_profiles_red_is_contributor():
    assert META_PROFILES["economy"].red_model == "muse-spark-1.3-contributor"
    assert META_PROFILES["balanced"].red_model == "muse-spark-1.3-contributor"


def test_contributor_id_validates_and_prices():
    PurpleBoxConfig(red_team_model="muse-spark-1.3-contributor").validate()
    try:
        PurpleBoxConfig(red_team_model="muse-spark-1.3").validate()
    except ConfigurationError:
        pass  # old id may or may not stay allowed; contributor must validate
    assert estimate_cost("muse-spark-1.3-contributor", 1000, 0, 500) is not None


def test_blue_default_is_spark_with_wonder_escalation_off():
    assert PurpleBoxConfig().blue_team_model == "muse-spark-1.3-contributor"
    assert PurpleBoxConfig().blue_escalation_model == ""
