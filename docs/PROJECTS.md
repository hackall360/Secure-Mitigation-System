# Local project intake and sandbox execution

Secure Mitigation System can snapshot an arbitrary local source repository without mounting it into
Docker or modifying its files. The implementation is split between `projects.py`
and project-specific methods on `DockerSandboxManager` in `docker_manager.py`.

## Project specification

`ProjectSpec` is a strict, frozen Pydantic model with forbidden extra fields:

- `path`: an existing local directory. String input is explicitly converted to an
  absolute `Path`; a symlink used as the project root is rejected.
- `image`: a preloaded Docker image reference. The literal default is
  `purplebox-target-base:latest`. Use
  `ProjectSpec.with_config_defaults(config, **values)` when an omitted image must
  follow `config.target_base_image`.
- `command`: non-empty argv list used to start the target. No shell parsing occurs.
- `test_command`: non-empty regression argv list used by `run_project_check` when
  neither `command` nor `script` is passed. It is mandatory so a project cannot
  silently claim verification without a regression command.
- `contract`: non-empty behavior contract, bounded at 32,768 characters.
- `cycles`: `1..20`, default `1`.
- `context_budget`: `1,024..131,072`, default `32,768`.
- `allow_remote_inference`: strict boolean, default `false`. Hosted inference must
  not receive project source unless the operator explicitly opts in.

Command arguments are non-empty, NUL-free strings, at most 4,096 characters each.
Command and test-command lists contain at most 64 arguments.

## Snapshot rules

Call `snapshot_project(spec)` to create a frozen `ProjectSnapshot` containing:

- `files: Mapping[str, bytes]`, keyed by relative POSIX path.
- `metadata: Mapping[str, ProjectFileMetadata]`, with byte size and normalized mode
  `0644` or `0755`.
- `skipped: Mapping[str, str]`, listing each excluded relative path and its reason.
- `binary_files: tuple[str, ...]`, listing included files that contain NUL bytes or
  are not valid UTF-8. Binary bytes stay in the Docker snapshot even when a model
  source view omits them.
- `digest`: deterministic SHA-256 over sorted paths, modes, lengths, and content.
- `total_bytes`: sum of included file bytes.

Default bounds are 4,096 files, 32 MiB total, and 1 MiB per file. Limits fail
explicitly rather than truncating the repository. Snapshotting uses
`lstat`-style inspection, does not follow links, opens files with `O_NOFOLLOW` where
supported, and checks identity and size/mtime around the read. Symlinks and special
files are rejected. Only regular files enter the manifest. Nested paths and the
presence of any executable bit are preserved. Directory metadata, ownership, and
mtimes are intentionally normalized.

The walker excludes version-control metadata (`.git`, `.hg`, `.svn`), dependency
and build trees (`node_modules`, `vendor`, virtual environments, `build`, `dist`,
`target`, caches), `.env` variants, common credential files, and private-key or
keystore suffixes. Excluded directories are not traversed. Snapshot collection and
`replace_snapshot_files(snapshot, replacements)` never write to the source tree.
The replacement helper accepts only paths already present in the manifest,
preserves their modes, reapplies byte limits, and returns a new digest.
Hosted-inference prompts must use only relative snapshot paths and must disclose
`skipped` and any `binary_files` omitted from model text. Never include `spec.path`
or another full local filesystem path in a hosted request.

## Docker lifecycle

Create the network through `DockerSandboxManager.create_isolated_network()`. It is
a user-defined bridge with `internal=True`, IPv6 disabled, and Docker bridge option
`com.docker.network.bridge.gateway_mode_ipv4=isolated`. Docker documents that plain
internal bridges still receive a host bridge address; isolated gateway mode omits
that address, preventing access to host services through it. Network creation fails
closed on daemons that do not support the option.

Project methods are:

```python
container, snapshot_image = manager.start_project(network, spec, snapshot)
result = manager.run_project_check(network, spec, snapshot, command=[...])
result = manager.run_project_check(network, spec, snapshot, script="...")
manager.stop_project(container)
manager.close()
```

`start_project` commits the in-memory files over the preloaded project image and
starts the exact argv command as the `target-service` alias. Each call creates a
fresh immutable target. `run_project_check` creates another disposable image and
container. A command check uses the project image and source. A Python script check
uses the verifier image, receives the same source under read-only `/workspace`, and
can reach a separately running target at `target-service`. Its script runs through
`docker/runner.py`, preserving exit meanings `0`, `1`, and `2`.

`ProjectCheckResult` contains `exit_code`, separately bounded `stdout` and `stderr`,
and `timed_out`. Both output streams retain only their final 16 KiB. Checks use
`config.verifier_timeout_seconds`; timeout returns `exit_code=None` and
`timed_out=True`. The disposable check container is always force-removed.
`stop_project` supports prompt cancellation, while `close` removes all remaining
session containers, networks, and committed snapshot images.

## Image and runtime restrictions

Project execution never builds a Dockerfile, pulls an image, downloads dependencies,
uses host binds, publishes ports, mounts the Docker socket, or starts the staging
container. The requested project image must already exist locally. Before use,
Secure Mitigation System rejects images declaring `Config.Volumes`, because Docker can create
anonymous host-side volumes, and rejects images embedding secret-like environment
variable names. Runtime and staging override inherited entrypoints and disable
inherited health checks.

Containers retain the common `_options` hardening: UID/GID 10001, all capabilities
dropped, no-new-privileges, PID/CPU/memory limits, bounded JSON logs, no Docker proxy
environment injection, a read-only root, and a small `noexec,nosuid,nodev` `/tmp`.
Source enters through a deterministic tar archive owned by UID/GID 10001. No host
path is exposed to the container.

These controls reduce accidental and application-level escape paths, but containers
share the host kernel. Secure Mitigation System is not a hostile-code virtual-machine boundary. Run
it only with trusted preloaded runtime images and on a Docker host whose compromise
would not be catastrophic.

## Docker references used

- Bridge network behavior and user-defined network DNS:
  <https://docs.docker.com/engine/network/drivers/bridge/>
- Isolated bridge gateway mode and why `internal` alone still exposes a host bridge
  address: <https://docs.docker.com/engine/network/port-publishing/>
- Container resource limits, filesystems, and network behavior:
  <https://docs.docker.com/engine/containers/run/>
- Docker SDK container options (`read_only`, `network_mode`, `put_archive`, resource
  limits): <https://docker-py.readthedocs.io/en/stable/containers.html>
