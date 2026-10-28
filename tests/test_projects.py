# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from config import PurpleBoxConfig
from projects import ProjectSpec, replace_snapshot_files, snapshot_project


def spec_for(path: Path, **overrides) -> ProjectSpec:
    values = {
        "path": str(path),
        "command": ["python3", "/workspace/src/app.py"],
        "test_command": ["python3", "-m", "unittest"],
        "contract": "GET / returns status 200.",
    }
    values.update(overrides)
    return ProjectSpec.model_validate(values)


def test_project_spec_is_strict_bounded_and_uses_configured_image(tmp_path):
    project = spec_for(tmp_path)
    assert project.path == tmp_path.absolute()
    assert project.image == "purplebox-target-base:latest"
    assert project.cycles == 1 and project.context_budget == 32_768
    assert project.allow_remote_inference is False

    configured = ProjectSpec.with_config_defaults(
        PurpleBoxConfig(target_base_image="local/project-runtime:v2"),
        path=str(tmp_path),
        command=["python3", "app.py"],
        test_command=["python3", "-m", "unittest"],
        contract="Keep the HTTP contract.",
    )
    assert configured.image == "local/project-runtime:v2"

    with pytest.raises(ValidationError):
        spec_for(tmp_path, cycles=0)
    with pytest.raises(ValidationError):
        spec_for(tmp_path, cycles=21)
    with pytest.raises(ValidationError):
        spec_for(tmp_path, context_budget=1023)
    with pytest.raises(ValidationError):
        spec_for(tmp_path, cycles="2")
    with pytest.raises(ValidationError):
        spec_for(tmp_path, test_command=[])
    with pytest.raises(ValidationError):
        spec_for(tmp_path, allow_remote_inference=1)
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(
            {
                "path": str(tmp_path),
                "command": ["true"],
                "contract": "x",
                "unknown": True,
            }
        )


def test_snapshot_is_bounded_deterministic_and_excludes_secrets_and_dependencies(tmp_path):
    source = tmp_path / "src" / "bin"
    source.mkdir(parents=True)
    executable = source / "serve.py"
    executable.write_bytes(b"#!/usr/bin/env python3\nprint('ok')\n")
    executable.chmod(0o751)
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    (tmp_path / ".env").write_text("API_KEY=never-copy\n", encoding="utf-8")
    (tmp_path / "server.key").write_text("private\n", encoding="utf-8")
    (tmp_path / "asset.bin").write_bytes(b"\x00\xffbinary")
    for excluded in (".git", "node_modules", "dist", ".venv"):
        directory = tmp_path / excluded
        directory.mkdir()
        (directory / "ignored.txt").write_text("ignored", encoding="utf-8")

    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in (executable, tmp_path / "README.md")
    }
    first = snapshot_project(spec_for(tmp_path))
    second = snapshot_project(spec_for(tmp_path))

    assert first.files == {
        "README.md": b"hello\n",
        "asset.bin": b"\x00\xffbinary",
        "src/bin/serve.py": b"#!/usr/bin/env python3\nprint('ok')\n",
    }
    assert first.metadata["src/bin/serve.py"].mode == 0o755
    assert first.metadata["src/bin/serve.py"].executable is True
    assert first.metadata["README.md"].mode == 0o644
    assert first.digest == second.digest
    assert first.binary_files == ("asset.bin",)
    assert first.skipped[".env"] == "secret or credential filename"
    assert first.skipped["server.key"] == "secret or credential filename"
    assert first.skipped["node_modules"].startswith("version-control")
    assert first.total_bytes == sum(map(len, first.files.values()))
    assert before == {
        path.relative_to(tmp_path): path.read_bytes()
        for path in (executable, tmp_path / "README.md")
    }
    with pytest.raises(TypeError):
        first.files["new.py"] = b"bad"


def test_snapshot_rejects_symlinks_special_files_and_limits(tmp_path):
    (tmp_path / "app.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "link.py").symlink_to(tmp_path / "app.py")
    with pytest.raises(ValueError, match="symbolic links"):
        snapshot_project(spec_for(tmp_path))

    (tmp_path / "link.py").unlink()
    if hasattr(os, "mkfifo"):
        os.mkfifo(tmp_path / "pipe")
        with pytest.raises(ValueError, match="special files"):
            snapshot_project(spec_for(tmp_path))
        (tmp_path / "pipe").unlink()

    with pytest.raises(ValueError, match="more than 1"):
        (tmp_path / "second.py").write_text("pass", encoding="utf-8")
        snapshot_project(spec_for(tmp_path), max_files=1)
    with pytest.raises(ValueError, match="exceeds 4 bytes"):
        snapshot_project(spec_for(tmp_path), max_file_bytes=4)


def test_project_spec_rejects_symlinked_root(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValidationError, match="symbolic links"):
        spec_for(link)


def test_replacements_are_in_memory_existing_path_only_and_preserve_mode(tmp_path):
    executable = tmp_path / "run.sh"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    original = snapshot_project(spec_for(tmp_path))
    patched = replace_snapshot_files(original, {"run.sh": "#!/bin/sh\nexit 1\n"})

    assert original.files["run.sh"] == b"#!/bin/sh\nexit 0\n"
    assert executable.read_text(encoding="utf-8") == "#!/bin/sh\nexit 0\n"
    assert patched.files["run.sh"] == b"#!/bin/sh\nexit 1\n"
    assert patched.metadata["run.sh"].mode == 0o755
    assert patched.digest != original.digest
    with pytest.raises(ValueError, match="not in the original snapshot"):
        replace_snapshot_files(original, {"new.sh": b"exit 0"})
    with pytest.raises(ValueError, match="unsafe"):
        replace_snapshot_files(original, {"../run.sh": b"exit 0"})
