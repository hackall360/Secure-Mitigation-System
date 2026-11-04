# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED (LAW 9): staged targets must boot with a writable scratch cwd.

Found live 2026-11-04 (Part 2 dry run): AnyCam staged fine (44 files) but
the target container exited 1 on start:

  OSError: [Errno 30] Read-only file system: '/workspace/cert'

Real apps persist runtime state (certs, caches, uploads) under their cwd.
The sandbox runs everything read-only with only /tmp writable — but the
target starts with cwd=/workspace (staged source, must stay pristine), so
relative writes hit the read-only root.

Fix contract: the ingest target wrapper copies the staged tree to
/tmp/scratch (writable tmpfs: rw, nosuid, nodev, non-root) and execs the
runtime argv there. Relative reads find staged bytes, relative writes land
on scratch, never on staged bytes. Absolute-path writes still fail closed
on the read-only root. The /workspace image layers are never mutated.

This pin stages a fake tree with a writer entrypoint and asserts the
workflow input the target factory produces boots from scratch (not from
/workspace) — without Docker, at the command-construction level.
"""

from __future__ import annotations


def test_ingest_target_wrapper_copies_tree_to_scratch():

    src = open("main.py").read()
    anchor = "cp -r /workspace/. /tmp/scratch/"
    assert anchor in src, (
        "ingest _ensure_target must copy the staged tree to writable "
        "scratch before exec (real apps write certs/caches under cwd; "
        "/workspace is read-only staged source)"
    )
    assert "cd /tmp/scratch" in src
    assert 'exec "$@"' in src, "wrapper must exec the runtime argv (PID 1)"


def test_scratch_mount_is_bounded_tmpfs():
    import inspect

    import library.core.docker_manager as dm

    src = inspect.getsource(dm.DockerSandboxManager._runtime)
    assert "/tmp" in src and "tmpfs" in src
    assert "noexec" in src and "nosuid" in src and "nodev" in src
    assert "10001" in src, "scratch must be owned by the non-root user"
