# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Trusted normal-input checks, independent of the model's boundary verifier."""

import ast
import json


def normal_behavior_script(target_key: str) -> str:
    return r"""
import configparser
import json
import sys
import urllib.error
import urllib.request

def get(path):
    with urllib.request.urlopen('http://target-service:8080' + path, timeout=3) as response:
        assert response.status == 200
        return response.read(65537).decode('utf-8')

target = TARGET_VALUE
if target == 'node_query_sink':
    for account_id, records in [
        (101, [{'id': 101, 'username': 'alice', 'role': 'user'}]),
        (102, [{'id': 102, 'username': 'bob', 'role': 'admin'}]),
        (999, []),
    ]:
        response = json.loads(get('/lookup?id=' + str(account_id)))
        assert response == {'status': 'ok', 'count': len(records), 'results': records}
    try:
        get('/unknown')
        raise AssertionError('404 route was removed (FAIL: GET /unknown must return HTTP 404 not_found; evidence: request succeeded instead of raising HTTPError 404)')
    except urllib.error.HTTPError as error:
        assert error.code == 404
        assert json.loads(error.read()) == {'status': 'not_found'}
elif target == 'php_command_sink':
    for host in ('localhost', '127.0.0.1'):
        assert json.loads(get('/?host=' + host)) == {
            'status': 'ok', 'host': host, 'diagnostic': host,
        }
elif target == 'mysql_insecure_conf':
    parser = configparser.ConfigParser()
    parser.read_string(get('/my.cnf'))
    assert parser.get('mysqld', 'port') == '3306'
    assert parser.get('mysqld', 'max_connections') == '100'
else:
    raise AssertionError('Unknown fixture (FAIL: no normal-behavior contract for this target; evidence: target matched none of node_query_sink/php_command_sink/mysql_insecure_conf)')
print('Trusted normal-input checks passed for ' + target + ' (PASS: every expected lookup, 404-route, and config value matched; boundary verifier not involved)')
sys.exit(0)
""".replace("TARGET_VALUE", json.dumps(target_key))


ISOLATION_SCRIPT = r"""
# Runs INSIDE the Linux verifier container only (never on the host):
# /proc/net/route and the no-default-route assertion are Linux-container
# checks. Windows/macOS hosts are supported; the container image is Linux.
import socket
import sys
from pathlib import Path

routes = Path('/proc/net/route').read_text().splitlines()[1:]
assert not any(row.split()[1] == '00000000' for row in routes), 'Unexpected default route (FAIL: verifier container must have no IPv4 default route; evidence: /proc/net/route row with destination 00000000)'
for address, port in [('1.1.1.1', 443), ('8.8.8.8', 53)]:
    try:
        with socket.create_connection((address, port), timeout=2):
            raise AssertionError('Unexpected public egress connectivity (FAIL: verifier container must not reach public net; evidence: TCP dial to 1.1.1.1:443 or 8.8.8.8:53 succeeded)')
    except OSError:
        pass
print('No IPv4 default route; public TCP probes blocked (not proof of complete isolation). PASS basis: /proc/net/route has no 00000000 destination and dials to 1.1.1.1:443 + 8.8.8.8:53 raised OSError.')
sys.exit(0)
"""

# Wave 8 R1: deterministic seeded property/metamorphic normal-contract checks.
# These run through the same in-container HTTP helper shape as the normal
# checks but widen the net beyond fixed equality asserts: known-good ids
# must stay 200 while seeded-random ids stay empty/not-found, benign args
# must stay stable under repetition, and audited config keys must survive
# re-read. Each registry id maps to the check matching its real service:
# node_query_sink asserts the JSON envelope of targets/node_query_sink/app.js
# while project_lookup_text asserts the plain-text contract of
# project-workflow demo apps (exact names for known ids, empty bodies for
# random ids). node_eval_service is not a registry key (registry.py keys are
# node_query_sink/php_command_sink/mysql_insecure_conf) so it is not listed.
_PROPERTY_FIXTURES = frozenset(
    {
        "node_query_sink",
        "project_lookup_text",
        "php_command_sink",
        "mysql_config_audit",
        "mysql_insecure_conf",
    }
)


def property_fixture_supported(fixture_id: str) -> bool:
    """True when a deterministic property script exists for this fixture id."""
    return fixture_id in _PROPERTY_FIXTURES


def _property_node_ids(seed: int) -> list[int]:
    import random

    rng = random.Random(seed)
    # Unknown-account range: far from the seeded accounts but still decimal.
    return [rng.randrange(10_000, 99_999) for _ in range(2)]


def project_property_script(fixture_id: str) -> str:
    """Build a bounded deterministic property script for one fixture id.

    Exit contract: 0 = every property held, 1 = a property failed (evidence
    in the message), 2 = inconclusive or unknown fixture. Output is bounded:
    only compact summaries, never response bodies.
    """
    if fixture_id not in _PROPERTY_FIXTURES:
        return (
            "import sys\n"
            f"print('Unknown property fixture: {fixture_id} (INCONCLUSIVE: no "
            "normal-contract properties defined; evidence: fixture id matched "
            "none of node_query_sink/project_lookup_text/php_command_sink/mysql_config_audit)')\n"
            "sys.exit(2)\n"
        )
    node_ids = _property_node_ids(20261029)
    if fixture_id == "node_query_sink":
        target = "node_query_sink"
    elif fixture_id == "project_lookup_text":
        target = "project_lookup_text"
    elif fixture_id == "php_command_sink":
        target = "php_command_sink"
    else:
        target = "mysql_config_audit"
    return r"""
import configparser
import json
import sys
import urllib.error
import urllib.request

SEED = 20261029
RANDOM_IDS = RANDOM_IDS_VALUE


def get(path):
    with urllib.request.urlopen('http://target-service:8080' + path, timeout=3) as response:
        assert response.status == 200
        return response.read(65537).decode('utf-8')


def fail(message):
    print('Property check failed: ' + message[:500])
    sys.exit(1)


try:
    target = TARGET_VALUE
    if target == 'node_query_sink':
        # Two known-good ids stay 200 and non-empty; seeded random ids must
        # return no rows (empty result set, not the 404 route).
        for account_id in (101, 102):
            try:
                response = json.loads(get('/lookup?id=' + str(account_id)))
            except urllib.error.HTTPError as error:
                fail('known id %d returned HTTP %d, want 200 with one row' % (account_id, error.code))
            if response.get('status') != 'ok' or not response.get('results'):
                fail('known id %d lost its result row' % account_id)
        for account_id in RANDOM_IDS:
            try:
                response = json.loads(get('/lookup?id=' + str(account_id)))
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    fail('random id %d hit the 404 route, want an empty lookup result' % account_id)
                fail('random id %d returned HTTP %d, want an empty result set' % (account_id, error.code))
            if response.get('count') != 0 or response.get('results') != []:
                fail('random id %d leaked rows, want an empty result set' % account_id)
    elif target == 'project_lookup_text':
        # Project-workflow plain-text shape: exact names for known ids,
        # empty body (200) for seeded random ids, never rows or an error page.
        for account_id, want in ((101, 'Alice'), (102, 'Bob')):
            try:
                body = get('/lookup?id=' + str(account_id))
            except urllib.error.HTTPError as error:
                fail('known id %d returned HTTP %d, want 200 with its exact name' % (account_id, error.code))
            if body != want:
                fail('known id %d returned %r, want %r' % (account_id, body[:60], want))
        for account_id in RANDOM_IDS:
            try:
                body = get('/lookup?id=' + str(account_id))
            except urllib.error.HTTPError as error:
                if error.code == 400:
                    fail('random id %d was blocked with HTTP 400, want an empty 200 body' % account_id)
                fail('random id %d returned HTTP %d, want an empty body' % (account_id, error.code))
            if body != '':
                fail('random id %d leaked rows %r, want an empty body' % (account_id, body[:60]))
    elif target == 'php_command_sink':
        # Benign hosts stay successful and byte-stable under repetition.
        seen = {}
        for host in ('localhost', '127.0.0.1'):
            try:
                first = get('/?host=' + host)
            except urllib.error.HTTPError as error:
                fail('benign host %s returned HTTP %d, want 200 ok' % (host, error.code))
            try:
                payload = json.loads(first)
            except ValueError:
                fail('benign host %s returned non-JSON output' % host)
            if payload.get('status') != 'ok' or payload.get('diagnostic') != host:
                fail('benign host %s lost its diagnostic echo' % host)
            seen[host] = first
        for host in ('localhost', 'localhost', '127.0.0.1'):
            try:
                repeated = get('/?host=' + host)
            except urllib.error.HTTPError as error:
                fail('repeated host %s returned HTTP %d, want stable 200 ok' % (host, error.code))
            if repeated != seen[host]:
                fail('repeated host %s was unstable across reads' % host)
    elif target == 'mysql_config_audit':
        # Audited keys survive idempotent re-read.
        first = get('/my.cnf')
        second = get('/my.cnf')
        if first != second:
            fail('config changed across re-reads, want idempotent content')
        parser = configparser.ConfigParser()
        try:
            parser.read_string(first)
        except configparser.Error as error:
            fail('config failed to parse: %s' % str(error)[:200])
        for section, key in (('mysqld', 'port'), ('mysqld', 'max_connections')):
            try:
                value = parser.get(section, key)
            except (configparser.NoSectionError, configparser.NoOptionError):
                fail('config key [%s] %s missing on re-read' % (section, key))
            if not value.strip():
                fail('config key [%s] %s is empty on re-read' % (section, key))
    else:
        print('Unknown property fixture (INCONCLUSIVE: no properties defined)')
        sys.exit(2)
except AssertionError as error:
    fail('helper contract broke: %s' % str(error)[:200])
except Exception as error:
    print('Property check inconclusive: %s: %s' % (type(error).__name__, str(error)[:200]))
    sys.exit(2)
print('Property checks passed for ' + target + ' (PASS: random-id emptiness, host stability, and config re-read held)')
sys.exit(0)
""".replace("RANDOM_IDS_VALUE", repr(node_ids)).replace("TARGET_VALUE", json.dumps(target))


# SPEC 14.8 item 4 (Wave 2.2-5, PHP + MySQL portion): bounded mutation-count
# probes. Competitor snapshot fuzzers do open-ended mutation storms outside the
# verify loop; we run N deterministic seeded mutations per fixture contract in
# the same capped container as regression, recorded as evidence — proving
# config/arg robustness as part of the retain verdict. Unknown fixture id
# MUST exit 2. Shapes match each target's REAL response: php returns
# status/host/diagnostic text for a host arg (not the node JSON envelope);
# mysql serves /my.cnf for config re-read (no JSON envelope at all).
MUTATION_SEED = 20261029
MUTATION_COUNT = 4

_MUTATION_FIXTURES = frozenset(
    {
        "php_command_sink",
        "mysql_insecure_conf",
    }
)


def mutation_fixture_supported(fixture_id: str) -> bool:
    """True when a deterministic mutation script exists for this fixture id."""
    return fixture_id in _MUTATION_FIXTURES


def _mutation_php_hosts() -> list[str]:
    import random

    rng = random.Random(MUTATION_SEED)
    pool = [";id", "$(id)", "`id`", "|id", "&&id", "$HOME", "${HOME}", "a b"]
    return sorted(rng.sample(pool, MUTATION_COUNT))


def _mutation_mysql_paths() -> list[str]:
    import random

    rng = random.Random(MUTATION_SEED)
    tokens = rng.sample(range(1000, 9999), MUTATION_COUNT - 1)
    return ["/my.cnf"] + [f"/my.cnf?mutation={token}" for token in tokens]


_PHP_MUTATION_TEMPLATE = r"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

MUTATIONS = MUTATIONS_VALUE
WANT_COUNT = MUTATION_COUNT_VALUE


def get_raw(path):
    with urllib.request.urlopen('http://target-service:8080' + path, timeout=3) as response:
        assert response.status == 200
        return response.read(65537).decode('utf-8')


def fail(message):
    print('Mutation check failed: ' + message[:500])
    sys.exit(1)


try:
    if len(MUTATIONS) != WANT_COUNT:
        fail('mutation contract drift: want exactly WANT_COUNT seeded mutations')
    for host in MUTATIONS:
        path = '/?host=' + urllib.parse.quote(host, safe='')
        try:
            body = get_raw(path)
        except urllib.error.HTTPError as error:
            if 400 <= error.code < 500:
                continue
            fail('mutation host was mishandled with HTTP %d, want exact echo or clean 4xx reject' % error.code)
        try:
            payload = json.loads(body)
        except ValueError:
            fail('mutation host returned non-JSON output, want status/host/diagnostic text')
        if payload.get('status') != 'ok' or payload.get('diagnostic') != host:
            fail('mutation host was not echoed exactly nor cleanly rejected')
except AssertionError as error:
    fail('helper contract broke: %s' % str(error)[:200])
except Exception as error:
    print('Mutation check inconclusive: %s: %s' % (type(error).__name__, str(error)[:200]))
    sys.exit(2)
print('Mutation checks passed (PASS: every seeded host-arg mutation echoed exactly or rejected cleanly)')
sys.exit(0)
"""

_MYSQL_MUTATION_TEMPLATE = r"""
import configparser
import sys
import urllib.request

PATHS = PATHS_VALUE
WANT_COUNT = MUTATION_COUNT_VALUE


def get(path):
    with urllib.request.urlopen('http://target-service:8080' + path, timeout=3) as response:
        assert response.status == 200
        return response.read(65537).decode('utf-8')


def fail(message):
    print('Mutation check failed: ' + message[:500])
    sys.exit(1)


try:
    if len(PATHS) != WANT_COUNT:
        fail('mutation contract drift: want exactly WANT_COUNT seeded re-reads')
    bodies = [get(path) for path in PATHS]
    first = bodies[0]
    for path, body in zip(PATHS[1:], bodies[1:]):
        if body != first:
            fail('config changed across mutation re-reads, want byte-identical content')
    parser = configparser.ConfigParser()
    try:
        parser.read_string(first)
    except configparser.Error as error:
        fail('config failed to parse: %s' % str(error)[:200])
    for section, key in (('mysqld', 'port'), ('mysqld', 'max_connections')):
        try:
            value = parser.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            fail('config key [%s] %s missing on mutation re-read' % (section, key))
        if not value.strip():
            fail('config key [%s] %s is empty on mutation re-read' % (section, key))
except AssertionError as error:
    fail('helper contract broke: %s' % str(error)[:200])
except Exception as error:
    print('Mutation check inconclusive: %s: %s' % (type(error).__name__, str(error)[:200]))
    sys.exit(2)
print('Mutation checks passed (PASS: every seeded config re-read byte-identical with audited keys present)')
sys.exit(0)
"""


def project_mutation_script(fixture_id: str) -> str:
    """Build a bounded deterministic mutation script for one fixture id.

    Exit contract: 0 = every seeded mutation held, 1 = a mutation mishandled
    the input (evidence in the message), 2 = inconclusive or unknown fixture.
    Output is bounded: only compact summaries, never response bodies.
    """
    if fixture_id not in _MUTATION_FIXTURES:
        return (
            "import sys\n"
            f"print('Unknown mutation fixture: {fixture_id} (INCONCLUSIVE: no "
            "mutation contract defined; evidence: fixture id matched "
            "neither php_command_sink nor mysql_insecure_conf)')\n"
            "sys.exit(2)\n"
        )
    if fixture_id == "php_command_sink":
        return _PHP_MUTATION_TEMPLATE.replace(
            "MUTATIONS_VALUE", json.dumps(_mutation_php_hosts())
        ).replace("MUTATION_COUNT_VALUE", str(MUTATION_COUNT))
    return _MYSQL_MUTATION_TEMPLATE.replace(
        "PATHS_VALUE", json.dumps(_mutation_mysql_paths())
    ).replace("MUTATION_COUNT_VALUE", str(MUTATION_COUNT))


_FORBIDDEN_MODULES = frozenset(
    {"subprocess", "pty", "ctypes", "multiprocessing", "shutil", "resource", "signal"}
)


def validate_verifier_script(script: str) -> None:
    """Validate that a verifier script is safe and explicitly exits with 0/1/2."""
    if "\x00" in script:
        raise ValueError(
            "Verifier script contains NUL bytes (REJECT: embedded NUL makes source unsafe to parse; evidence: \\x00 byte present in submitted script)."
        )
    try:
        tree = ast.parse(script, filename="verify.py")
    except SyntaxError as exc:
        raise ValueError(
            f"Verifier script has invalid Python syntax (REJECT: AST parse failed so the exit-code verdict contract cannot be checked; evidence: {exc})"
        ) from exc
    # Check forbidden imports.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _FORBIDDEN_MODULES:
                    raise ValueError(
                        f"Verifier script imports forbidden module: {root} (REJECT: sandbox-escape guard bans subprocess/pty/ctypes/multiprocessing/shutil/resource/signal; evidence: AST scan found import of '{root}')"
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in _FORBIDDEN_MODULES:
                    raise ValueError(
                        f"Verifier script imports forbidden module: {root} (REJECT: sandbox-escape guard bans subprocess/pty/ctypes/multiprocessing/shutil/resource/signal; evidence: AST scan found import of '{root}')"
                    )
        # Also detect __import__('subprocess') as Call
        if isinstance(node, ast.Call):
            # Detect __import__('forbidden')
            func = node.func
            is_import = False
            if isinstance(func, ast.Name) and func.id == "__import__":
                is_import = True
            elif isinstance(func, ast.Attribute) and func.attr == "__import__":
                is_import = True
            if is_import and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    root = arg.value.split(".")[0]
                    if root in _FORBIDDEN_MODULES:
                        raise ValueError(
                            f"Verifier script imports forbidden module: {root} (REJECT: sandbox-escape guard bans subprocess/pty/ctypes/multiprocessing/shutil/resource/signal; evidence: AST scan found import of '{root}')"
                        )
    # Check for explicit exit call.
    has_exit = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                # sys.exit(...) or SystemExit(...)
                if (
                    func.attr == "exit"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "sys"
                ):
                    has_exit = True
                    break
            elif isinstance(func, ast.Name):
                if func.id in ("exit", "quit"):
                    has_exit = True
                    break
        elif isinstance(node, ast.Raise):
            exc = node.exc
            if exc is None:
                continue
            # raise SystemExit(...) or raise SystemExit
            if isinstance(exc, ast.Call):
                if isinstance(exc.func, ast.Name) and exc.func.id == "SystemExit":
                    has_exit = True
                    break
                if isinstance(exc.func, ast.Attribute) and exc.func.attr == "SystemExit":
                    has_exit = True
                    break
            elif isinstance(exc, ast.Name) and exc.id == "SystemExit":
                has_exit = True
                break
    if not has_exit:
        raise ValueError(
            "Verifier script must explicitly call sys.exit(0|1|2) (REJECT: no verdict exit found; contract is exit 0=boundary reached, 1=blocked, 2=inconclusive; evidence: AST scan found no sys.exit/exit/quit/SystemExit call)."
        )
