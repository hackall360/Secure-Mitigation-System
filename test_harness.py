# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Opt-in live checks. Deterministic fixtures here are tests, never an inference fallback."""

import argparse
import asyncio
import json

from agents import BlueTeamPatch, MetaMuseClient, RedTeamFinding
from checks import ISOLATION_SCRIPT, normal_behavior_script
from config import load_config
from docker_manager import DockerSandboxManager
from patches import validate_patch
from registry import TARGETS_REGISTRY


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def known_patch(key: str, source: str) -> str:
    if key == "node_query_sink":
        return source.replace(
            "        const queryExpression =",
            "        if (typeof rawUserId !== 'string' || !/^[0-9]+$/.test(rawUserId)) {\n"
            "            res.writeHead(400, { 'Content-Type': 'application/json' });\n"
            "            res.end(JSON.stringify({ status: 'error', detail: 'Invalid ID' }));\n"
            "            return;\n"
            "        }\n"
            "        const queryExpression =",
        )
    if key == "php_command_sink":
        return source.replace(
            "$output = shell_exec",
            "if (!is_string($host) || !preg_match('/^[a-zA-Z0-9.-]+$/D', $host)) {\n"
            "    http_response_code(400);\n"
            "    echo json_encode(['status' => 'error', 'detail' => 'Invalid host']);\n"
            "    exit;\n"
            "}\n"
            "$output = shell_exec",
        )
    return (
        source.replace("bind-address = 0.0.0.0", "bind-address = 127.0.0.1")
        .replace("local-infile = 1", "local-infile = 0")
        .replace('secure-file-priv = ""', "secure-file-priv = /var/lib/mysql-files")
    )


def diagnostic_script(key: str) -> str:
    return r"""
import configparser
import json
import sys
import urllib.error
import urllib.request

target = TARGET_VALUE
paths = {'node_query_sink': '/lookup?id=%27', 'php_command_sink': '/?host=bad%20host',
         'mysql_insecure_conf': '/my.cnf'}
try:
    with urllib.request.urlopen('http://target-service:8080' + paths[target], timeout=3) as response:
        status, body = response.status, response.read(65537).decode()
except urllib.error.HTTPError as error:
    status, body = error.code, error.read(65537).decode()
if target == 'node_query_sink':
    if status == 400:
        print('Malformed account ID blocked')
        sys.exit(1)
    if status == 500 and json.loads(body).get('status') == 'error':
        print('Benign quote reached dynamic expression parser')
        sys.exit(0)
elif target == 'php_command_sink':
    if status == 400:
        print('Malformed hostname blocked')
        sys.exit(1)
    if status == 200 and json.loads(body).get('diagnostic') == 'badhost':
        print('Benign space changed shell argument boundaries')
        sys.exit(0)
else:
    if status == 200:
        config = configparser.ConfigParser()
        config.read_string(body)
        expected = {'bind-address': '127.0.0.1', 'local-infile': '0',
                    'secure-file-priv': '/var/lib/mysql-files'}
        hardened = all(config.get('mysqld', k).strip('"\'') == v for k, v in expected.items())
        print('Configuration hardened' if hardened else 'Insecure configuration observed')
        sys.exit(1 if hardened else 0)
print('Unexpected response; inconclusive')
sys.exit(2)
""".replace("TARGET_VALUE", json.dumps(key))


def local_checks() -> None:
    finding = RedTeamFinding.model_validate(
        {
            "vulnerability_class": "fixture boundary",
            "sink_location": "fixture",
            "analysis_summary": "Local schema test",
            "verification_script_python": "import sys\nsys.exit(0)",
        }
    )
    RedTeamFinding.model_validate_json(finding.model_dump_json())
    for key, target in TARGETS_REGISTRY.items():
        source = target.read_source()
        patched = known_patch(key, source)
        patch = BlueTeamPatch(
            sanitization_strategy="Harness-only deterministic patch",
            diff_summary="Known fixture edit",
            patched_file_content=patched,
        )
        BlueTeamPatch.model_validate_json(patch.model_dump_json())
        validate_patch(target, source, patched)
        compile(normal_behavior_script(key), "normal_check.py", "exec")
        compile(diagnostic_script(key), "boundary_check.py", "exec")
    compile(ISOLATION_SCRIPT, "isolation_check.py", "exec")
    print("PASS: local schemas, three fixture patches, and check-script syntax")


def docker_checks() -> None:
    settings = load_config()
    for key, target in TARGETS_REGISTRY.items():
        print(f"RUN: {key}: starting sandbox and baseline checks", flush=True)
        with DockerSandboxManager(settings) as manager:
            manager.require_base_images()
            network = manager.create_isolated_network()
            source = target.read_source()
            container, snapshot = manager.start_cloneable_target(network, target, source)
            isolation = container.exec_run(["python3", "-c", ISOLATION_SCRIPT])
            check(isolation.exit_code == 0, f"Target egress check failed: {key}")
            check(
                manager.run_isolated_verifier(network, ISOLATION_SCRIPT).exit_code == 0,
                "Verifier egress check failed",
            )
            print(f"RUN: {key}: target/verifier egress checks passed", flush=True)
            normal = normal_behavior_script(key)
            boundary = diagnostic_script(key)
            check(manager.run_isolated_verifier(network, normal).exit_code == 0, "Baseline failed")
            check(
                manager.run_isolated_verifier(network, boundary).exit_code == 0,
                "Boundary was not confirmed",
            )
            print(f"RUN: {key}: baseline and unsanitized boundary confirmed", flush=True)
            patched = known_patch(key, source)
            validate_patch(target, source, patched)
            manager.replace_target(container, snapshot, network, target, patched)
            check(
                manager.run_isolated_verifier(network, normal).exit_code == 0,
                "Regression checks failed",
            )
            check(
                manager.run_isolated_verifier(network, boundary).exit_code == 1,
                "Patch did not block boundary",
            )
        print(
            f"PASS: {key} baseline, pre/post probe, normal regression, egress checks, cleanup",
            flush=True,
        )


async def api_checks() -> None:
    client = MetaMuseClient(load_config())
    target = TARGETS_REGISTRY["node_query_sink"]
    try:
        source = target.read_source()
        finding = await client.run_red_team_analysis(target.filename, source, target.contract)
        await client.run_blue_team_sanitizer(
            target.filename,
            source,
            finding,
            "Schema-connectivity test only; no boundary verification has been performed.",
            target.contract,
        )
        print(
            "PASS: live red/blue Muse responses conform to their schemas (not a vulnerability verification)"
        )
    finally:
        await client.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description="PurpleBox self-test harness")
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Run live container and egress tests; base images must exist",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Make two real Muse requests; requires a key and incurs API usage",
    )
    args = parser.parse_args()
    try:
        local_checks()
        if args.docker:
            docker_checks()
        if args.api:
            asyncio.run(api_checks())
        if not (args.docker or args.api):
            print("SKIP: live Docker and Muse checks; request --docker and/or --api explicitly")
        return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}. Check setup and the failing harness stage.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
