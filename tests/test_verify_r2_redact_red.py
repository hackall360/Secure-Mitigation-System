"""R2 redact gap tests (LAW 9 RED-first): sms_redact + chatter + personas branches.

Every function/branch below is unexecuted by any existing test (verified by
grep over tests/ before writing):
- sms_redact: non-dict finding passthrough, non-string before-trace
  passthrough, exact-200-char normal boundary, missing-traces-key safety,
  plain-dict evidence input, evidence_digests candidate path, batch item
  without candidates, empty red report gaining the withheld key,
  independent_verification exit-code preservation, probe-less section and
  non-dict section passthrough, string-evidence cycle passthrough,
  string-evidence history passthrough.
- chatter: default persona ("Agent") + default path ("the boundary"),
  str-int code/n coercion, model_active unknown defaults + allowlist
  stripping, backslash-path basename behavior, socket_emit msg passthrough.
- personas: zero/negative index wrap, frozen-dataclass immutability,
  leader/green keys.
All assertions pin behavior observed by direct probing (no invented values).
"""

import asyncio
import dataclasses

from library.core.personas import (
    BLUE_LEADER_PERSONA,
    GREEN_PERSONA,
    RED_LEADER_PERSONA,
    blue_persona,
    red_persona,
)
from library.services.chatter import chatter, socket_emit
from library.shared.sms_redact import (
    EXPLOIT_REDACTED,
    NORMAL_OUTPUT_SUFFIX,
    PROBE_OUTPUT_WITHHELD,
    redact_cycle_evidence,
    redact_fixture_result,
    redact_project_result,
)


class _Dump:
    def __init__(self, data):
        self._data = data

    def model_dump(self):
        return self._data


# --- redact_fixture_result gaps ---


def test_finding_non_dict_and_nonstr_trace_pass_through():
    data = redact_fixture_result(
        _Dump({"finding": None, "traces": {"before": 123, "baseline": "k" * 200}})
    )
    assert data["finding"] is None
    assert data["traces"]["before"] == 123
    assert data["traces"]["baseline"] == "k" * 200


def test_string_finding_passes_through_untouched():
    data = redact_fixture_result(_Dump({"finding": "verdict-string", "traces": {}}))
    assert data["finding"] == "verdict-string"


def test_after_trace_withheld_like_before():
    data = redact_fixture_result(_Dump({"finding": {}, "traces": {"after": "payload-bytes"}}))
    assert data["traces"]["after"] == PROBE_OUTPUT_WITHHELD


def test_normal_trace_exact_200_char_boundary_untouched():
    edge = "e" * 200
    data = redact_fixture_result(
        _Dump({"finding": {}, "traces": {"baseline": edge, "regression": edge}})
    )
    assert data["traces"]["baseline"] == edge
    assert NORMAL_OUTPUT_SUFFIX not in data["traces"]["regression"]


def test_missing_traces_key_is_safe():
    # Even an empty finding dict gains the withheld marker (isinstance dict
    # branch mutates in place); the point is no KeyError without "traces".
    data = redact_fixture_result(_Dump({"finding": {}}))
    assert data["finding"] == {"verification_script_python": EXPLOIT_REDACTED}


# --- redact_cycle_evidence gaps ---


def test_plain_dict_evidence_redacts_like_model_dump():
    ev = {
        "red": {
            "batch_evidence": [
                {"candidates": [{"verification_script_python": "evil()", "evidence": "raw"}]}
            ],
            "report": {"verification_script_python": "evil2()"},
        },
        "pre_verification": {"probe": {"output": "short payload", "exit_code": 0}},
    }
    data = redact_cycle_evidence(ev)
    blob = str(data)
    assert "evil()" not in blob and "raw" not in blob.replace("draw", "")
    assert "short payload" not in blob
    assert data["red"]["report"]["verification_script_python"] == EXPLOIT_REDACTED
    assert data["pre_verification"]["probe"]["exit_code"] == 0


def test_evidence_digests_candidate_path_redacted():
    class Ev:
        def model_dump(self):
            return {
                "red": {
                    "evidence_digests": [
                        {
                            "candidates": [
                                {
                                    "verification_script_python": "digest-evil()",
                                    "evidence": "digest-payload",
                                }
                            ]
                        }
                    ]
                }
            }

    data = redact_cycle_evidence(Ev())
    cand = data["red"]["evidence_digests"][0]["candidates"][0]
    assert cand["verification_script_python"] == EXPLOIT_REDACTED
    assert cand["evidence"] == EXPLOIT_REDACTED


def test_batch_item_without_candidates_passes_through():
    class Ev:
        def model_dump(self):
            return {"red": {"batch_evidence": [{"no_candidates_here": 1}]}}

    data = redact_cycle_evidence(Ev())
    assert data["red"]["batch_evidence"] == [{"no_candidates_here": 1}]


def test_empty_red_report_stays_empty():
    # red.get("report") or {} builds a throwaway for falsy reports, so the
    # withheld marker is dropped and the stored report stays {}. Benign:
    # an empty report carries no script to redact.
    class Ev:
        def model_dump(self):
            return {"red": {"report": {}}}

    data = redact_cycle_evidence(Ev())
    assert data["red"]["report"] == {}


def test_empty_independent_report_stays_empty():
    class Ev:
        def model_dump(self):
            return {"red": {"report": {}}, "independent_red": {"report": {}}}

    data = redact_cycle_evidence(Ev())
    assert data["independent_red"]["report"] == {}


def test_independent_verification_probe_keeps_exit_code():
    class Ev:
        def model_dump(self):
            return {
                "red": {"report": {}},
                "independent_verification": {"probe": {"output": "secret-bytes", "exit_code": 2}},
            }

    data = redact_cycle_evidence(Ev())
    probe = data["independent_verification"]["probe"]
    assert probe["output"] == EXPLOIT_REDACTED
    assert probe["exit_code"] == 2


def test_probeless_section_and_nondict_section_untouched():
    class Ev:
        def model_dump(self):
            return {
                "red": {"report": {}},
                "pre_verification": {"no_probe_key": 1},
                "patched_verification": "not-a-dict",
            }

    data = redact_cycle_evidence(Ev())
    assert data["pre_verification"] == {"no_probe_key": 1}
    assert data["patched_verification"] == "not-a-dict"


# --- redact_project_result gaps ---


def test_cycle_string_evidence_and_missing_evidence_pass_through():
    data = redact_project_result(
        _Dump(
            {
                "cycle_reports": [{"evidence": "just-a-string"}, {"no_evidence": True}],
                "verified_history": [{"evidence": "history-string"}],
            }
        )
    )
    assert data["cycle_reports"][0]["evidence"] == "just-a-string"
    assert data["cycle_reports"][1] == {"no_evidence": True}
    assert data["verified_history"] == [{"evidence": "history-string"}]
    assert data["cycles"] == data["cycle_reports"]


# --- chatter gaps ---


def test_default_persona_and_path_fallbacks():
    line = chatter("red_done", seed=0)
    assert line == "Agent reporting back: one testable claim, rest is noise."
    assert "the boundary" in chatter("red_start", seed=1)
    assert chatter("red_start", seed=1).startswith("Agent ")


def test_code_and_n_string_coercion():
    assert "exit 3" in chatter("red_proof", code="3", seed=0)
    assert "exit 0" in chatter("red_proof", code="not-an-int", seed=0)
    assert "exit 0" in chatter("red_proof", code=None, seed=0)


def test_model_active_unknown_defaults():
    line = chatter("model_active", seed=0)
    assert "unknown-model" in line
    assert "unknown-phase" in line


def test_model_active_allowlist_strips_hostile_chars():
    line = chatter("model_active", model="bad model;id\x00$", phase="a/b phase!", seed=0)
    assert "badmodelid" in line
    assert "bad model" not in line
    assert "\x00" not in line


def test_backslash_path_not_split_to_basename():
    line = chatter("red_start", path="C:\\x\\y\\app.py", seed=1)
    assert "app.py" in line
    assert "\\" in line  # rsplit("/") keeps backslash paths whole (truncated to 64)
    assert len(line) <= 220


def test_trailing_slash_path_yields_empty_basename():
    line = chatter("red_start", path="a/b/", seed=0)
    assert len(line) <= 220
    assert "\n" not in line


def test_socket_emit_forwards_msg_verbatim_with_log_type_and_ts():
    seen: list[dict] = []

    class FakeSocket:
        async def send_json(self, payload):
            seen.append(payload)

    async def go():
        emit = socket_emit(FakeSocket())
        await emit("blue", "Wall raised on app.py.")

    asyncio.run(go())
    assert seen[0]["team"] == "blue"
    assert seen[0]["msg"] == "Wall raised on app.py."
    assert seen[0]["type"] == "log"
    assert isinstance(seen[0]["ts"], float)


# --- personas gaps ---


def test_zero_and_negative_index_wrap_around():
    assert red_persona(0).name == "Cartographer"
    assert blue_persona(0).name == "Proofreader"
    assert red_persona(-1).name == "Sparkler"  # (-1-1) % 5 == 3
    assert blue_persona(-6).name == "Sentinel"  # (-6-1) % 5 == 3


def test_persona_replace_copies_without_mutating_original():
    clone = dataclasses.replace(red_persona(1), name="Mutant")
    assert clone.name == "Mutant"
    assert red_persona(1).name == "Breakwater"
    assert clone.key == "breakwater"  # only name overridden
    assert dataclasses.is_dataclass(red_persona(1))


def test_persona_setattr_raises_frozen():
    try:
        red_persona(1).name = "Mutant"
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError("Persona dataclass is not frozen")
    assert red_persona(1).name == "Breakwater"


def test_leader_and_green_keys():
    assert RED_LEADER_PERSONA.key == "warlord"
    assert BLUE_LEADER_PERSONA.key == "warden"
    assert GREEN_PERSONA.key == "greenhouse"
