# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Project telemetry: compression report + vault recall on ProjectWorkflowResult."""

from helpers import (
    TEST_CONFIG as CONFIG,
)
from helpers import (
    FakeProjectMuse as FakeMuse,
)
from helpers import (
    FakeProjectSandbox as FakeSandbox,
)
from helpers import (
    project_verification as verification,
)
from helpers import (
    run_project_workflow as run_workflow,
)

from modules.shared.sms_compress import CompressionReport
from modules.workflows.project_workflow import ProjectWorkflowResult


def test_telemetry_fields_exist_with_defaults():
    result = ProjectWorkflowResult(project="demo", cycles_requested=1)
    assert isinstance(result.compression, CompressionReport)
    assert result.compression.raw_tokens_estimated == 0
    assert result.vault_recall == ""
    assert result.vault_namespaces == []


def test_telemetry_fields_serialize():
    result = ProjectWorkflowResult(
        project="demo",
        cycles_requested=1,
        compression=CompressionReport(
            raw_tokens_estimated=120,
            compressed_tokens_sent=80,
            tokens_saved=40,
            compression_ratio=0.3333,
            compressed_text="x",
        ),
        vault_recall="KNOWN_ARCHETYPE",
        vault_namespaces=["red", "blue"],
    )
    dumped = result.model_dump()
    assert dumped["compression"]["raw_tokens_estimated"] == 120
    assert dumped["compression"]["compressed_tokens_sent"] == 80
    assert dumped["vault_recall"] == "KNOWN_ARCHETYPE"
    assert dumped["vault_namespaces"] == ["red", "blue"]
    assert dumped["compression"]["compressed_text"] == "x"


def test_format_facts_renders_compression_and_vault_rows():
    from sms_cli import format_facts

    result = ProjectWorkflowResult(
        project="demo",
        cycles_requested=1,
        compression=CompressionReport(
            raw_tokens_estimated=120,
            compressed_tokens_sent=80,
            tokens_saved=40,
            compression_ratio=0.3333,
            compressed_text="x",
        ),
        vault_recall="KNOWN_ARCHETYPE",
        vault_namespaces=["red", "blue"],
    )
    facts = format_facts(result, use_color=False)
    assert facts["compression"] == "120 -> 80 tokens (saved 40, ratio 0.33)"
    assert facts["vault_recall"] == "KNOWN_ARCHETYPE (red, blue)"


def test_format_facts_defaults_report_not_reported():
    from sms_cli import format_facts

    result = ProjectWorkflowResult(project="demo", cycles_requested=1)
    facts = format_facts(result, use_color=False)
    assert facts["compression"] == "Not reported"
    assert facts["vault_recall"] == "Not reported"


async def test_workflow_populates_compression_and_vault_once(tmp_path, monkeypatch):
    """The workflow compresses the snapshot context and vault-queries it once."""
    monkeypatch.setenv("PURPLEBOX_VAULT_DIR", str(tmp_path / "vault"))
    events = []

    async def emit(team, message):
        events.append((team, message))

    from modules.workflows.project_workflow import ProjectWorkflowInput, execute_project_workflow

    project = ProjectWorkflowInput(
        name="demo",
        files={"src/app.py": "value = input()\nprint(value)\n"},
        regression_command=["pytest", "-q"],
    )
    muse = FakeMuse(red_outcomes=["no_finding"])
    sandbox = FakeSandbox([verification(1)])
    result = await execute_project_workflow(
        project,
        emit,
        config=CONFIG,
        sandbox_factory=lambda _settings: sandbox,
        muse_factory=lambda _settings: muse,
    )
    assert result.compression.raw_tokens_estimated > 0
    assert result.compression.compressed_text != ""
    assert result.vault_recall in ("KNOWN_ARCHETYPE", "NOVEL_SURFACE")
    assert result.vault_namespaces == []
    messages = [message for _, message in events]
    assert sum("[phase compress]" in message for message in messages) == 1
    assert sum("[phase vault]" in message for message in messages) == 1


async def test_workflow_vault_failure_falls_back_without_raising(monkeypatch):
    """Vault errors never raise: the result carries VAULT_UNAVAILABLE."""
    import modules.intel.sms_vault as vault

    monkeypatch.setattr(
        vault, "query_vault", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down"))
    )
    muse = FakeMuse(red_outcomes=["no_finding"])
    sandbox = FakeSandbox([verification(1)])
    result = await run_workflow(muse=muse, sandbox=sandbox)
    assert result.status == "no_findings"
    assert result.vault_recall == "VAULT_UNAVAILABLE"
    assert result.compression.raw_tokens_estimated > 0
