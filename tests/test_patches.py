# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
import pytest

from modules.core.patches import PatchRejected, validate_patch
from modules.core.registry import TARGETS_REGISTRY


def node_patch(source):
    return source.replace(
        "        const queryExpression =",
        "        if (!/^[0-9]+$/.test(rawUserId)) {\n"
        "            res.writeHead(400, { 'Content-Type': 'application/json' });\n"
        "            res.end(JSON.stringify({ status: 'error', detail: 'Invalid ID' }));\n"
        "            return;\n"
        "        }\n"
        "        const queryExpression =",
    )


def test_surgical_node_patch_preserves_routes_and_returns_diff():
    target = TARGETS_REGISTRY["node_query_sink"]
    source = target.read_source()
    diff = validate_patch(target, source, node_patch(source))
    assert diff.startswith("--- a/node_query_sink/app.js")
    assert "+        if (" in diff


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value,
        lambda value: "",
        lambda value: value.replace("'/lookup'", "'/removed'"),
        lambda value: value.replace("results: matches", "results: []"),
        lambda value: value.replace("Copyright (c) 2026 hackall360", "Copyright Someone Else"),
    ],
)
def test_invalid_source_changes_rejected(mutation):
    target = TARGETS_REGISTRY["node_query_sink"]
    with pytest.raises(PatchRejected):
        validate_patch(target, target.read_source(), mutation(target.read_source()))


def test_config_hardening_only():
    target = TARGETS_REGISTRY["mysql_insecure_conf"]
    source = target.read_source()
    patch = (
        source.replace("0.0.0.0", "127.0.0.1")
        .replace("local-infile = 1", "local-infile = 0")
        .replace('secure-file-priv = ""', "secure-file-priv = /var/lib/mysql-files")
    )
    assert validate_patch(target, source, patch)
    with pytest.raises(PatchRejected, match="unrelated"):
        validate_patch(
            target, source, patch.replace("max_connections = 100", "max_connections = 1")
        )
    with pytest.raises(PatchRejected, match="harden"):
        validate_patch(target, source, patch.replace("local-infile = 0", "local-infile = 1"))
