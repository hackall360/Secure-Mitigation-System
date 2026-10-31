# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Explicit, local fixture registry; no arbitrary path or command input."""

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
TARGETS_DIR = BASE_DIR / "targets"


@dataclass(frozen=True)
class Target:
    key: str
    filename: str
    title: str
    description: str
    command: tuple[str, ...]
    mutable_prefixes: tuple[str, ...]
    contract: str

    def read_source(self) -> str:
        path = TARGETS_DIR / self.key / self.filename
        if path.is_symlink() or path.stat().st_size > 65_536:
            raise ValueError("Fixture must be a regular UTF-8 file smaller than 64 KiB.")
        return path.read_text(encoding="utf-8")


TARGETS_REGISTRY = {
    "node_query_sink": Target(
        "node_query_sink",
        "app.js",
        "Node.js query boundary",
        "Validate account IDs before a dynamic query expression.",
        ("node", "/workspace/app.js"),
        ("const rawUserId =", "const queryExpression ="),
        "GET /lookup?id=101 returns Alice; id=102 returns Bob; id=999 returns no matches. "
        "Keep status/count/results and the 404 route. Only existing lines starting with "
        "'const rawUserId =' or 'const queryExpression =' may be replaced. Insert strict "
        "decimal integer validation before building the expression. Keep other lines verbatim.",
    ),
    "node_chain_link": Target(
        "node_chain_link",
        "app.js",
        "Node.js chain boundary",
        "Prove the chain sweep flips what single-step misses: a logic-abuse "
        "role grant (Link A) gates a dynamic query expression (Link B).",
        ("node", "/workspace/app.js"),
        ("const rawRole =", "const queryExpression ="),
        "GET /lookup?role=reviewer&grant=<privileged>&id=101 returns Alice; "
        "id=102 returns Bob; id=999 returns no matches. Unprivileged "
        "role=viewer&id=101 returns HTTP 400. "
        "Keep status/count/results and the 404 route. Only existing lines "
        "starting with 'const rawRole =' or 'const queryExpression =' may "
        "be replaced. Guard the role grant (Link A) and add strict decimal "
        "integer validation (Link B) before building the expression. Keep "
        "other lines verbatim.",
    ),
    "php_command_sink": Target(
        "php_command_sink",
        "index.php",
        "PHP command boundary",
        "Validate a host argument passed to a local diagnostic command.",
        ("php", "-S", "0.0.0.0:8080", "-t", "/workspace"),
        ("$host =", "$output ="),
        "GET /?host=localhost and /?host=127.0.0.1 return status=ok, host and diagnostic "
        "equal to the requested host. The local printf command is intentional; no ping or "
        "external traffic is needed. Reject malformed hosts with HTTP 400. Only existing "
        "lines starting '$host =' or '$output =' may change; preserve all other lines.",
    ),
    "mysql_insecure_conf": Target(
        "mysql_insecure_conf",
        "my.cnf",
        "MySQL configuration",
        "Audit three configuration directives; no database server is started.",
        ("python3", "-m", "http.server", "8080", "--bind", "0.0.0.0", "--directory", "/workspace"),
        (),
        "GET /my.cnf serves a configuration fixture, not a running database. Preserve all "
        "directives except [mysqld] bind-address=127.0.0.1, local-infile=0, and "
        "secure-file-priv=/var/lib/mysql-files. Keep port=3306 and max_connections=100.",
    ),
    "binary_argv_echo": Target(
        "binary_argv_echo",
        "echo",
        "Binary argv echo",
        "Probe an unvalidated argv reflection in the compiled ELF fixture "
        "(targets/binary_argv_echo/echo). Run via the binary harness path "
        "(--binary-target / /ws/binary), not --scan: the ELF bytes are not "
        "UTF-8 source. Short alphanumeric argv input echoes back; overlong "
        "or shell-metachar argv input must be rejected by the mitigated harness.",
        ("python3", "/workspace/binary_harness.py"),
        (),
        "Companion to the compiled ELF fixture targets/binary_argv_echo/echo. "
        "Short alphanumeric argv input echoes back; overlong or shell-metachar "
        "argv input must be rejected by the mitigated harness.",
    ),
}
