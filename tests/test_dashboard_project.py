# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Execute dashboard intake/readiness JavaScript without a browser or inference server."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "static" / "app.js"
INDEX = SCRIPT.with_name("index.html")
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node is needed for JavaScript checks")


def evaluate(body):
    script = SCRIPT.read_text()
    constants = script[script.index("const SCAN_PROFILE_CYCLES") : script.index("let targets")]
    functions = script[
        script.index("function parseArgv(") : script.index("function lockProjectForm(")
    ]
    initialize = script[
        script.index("async function initialize(") : script.index("function startScan(")
    ]
    summary = script[
        script.index("function summaryEvidence(") : script.index("function showResult(")
    ]
    usage = script[script.index("function formatCost(") : script.index("function renderCycles(")]
    render_cycles = script[
        script.index("function renderCycles(") : script.index("function summaryEvidence(")
    ]
    harness = r"""
const assert = require('node:assert/strict');
const nodes = new Map();
function el(id) {
  if (!nodes.has(id)) nodes.set(id, {
    value: '', checked: false, hidden: false, required: true, disabled: false,
    textContent: '', readOnly: false, dataset: {}, label: {hidden: false},
    setAttribute() {}, removeAttribute() {}, querySelectorAll() { return []; },
    closest() { return this.label; }
  });
  return nodes.get(id);
}
let inferenceMode = 'hosted';
let configured = false;
let targets = {};
function renderTargets() {}
function renderProfiles() {}
function chip() {}
function status() {}
function fill() {
  el('project-path').value = '/tmp/project';
  el('project-image').value = 'purplebox-target-base:latest';
  el('project-contract').value = 'Preserve API';
  el('project-command').value = '["python3", "app.py"]';
  el('project-test-command').value = '["python3", "-m", "unittest"]';
  el('project-scan-profile').value = 'extra_light';
  el('project-cycles').value = '1';
  el('project-red-agents').value = '5';
  el('project-blue-agents').value = '5';
  el('project-budget').value = '32768';
}
"""
    subprocess.run(
        [
            NODE,
            "-e",
            harness + constants + functions + initialize + summary + usage + render_cycles + body,
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_hosted_intake_requires_consent_and_local_intake_never_grants_it():
    evaluate("""
fill();
assert.equal(projectSpec(), null);
el('allow-remote').checked = true;
assert.equal(projectSpec().allow_remote_inference, true);
inferenceMode = 'local';
el('allow-remote').checked = false;
assert.equal(projectSpec().allow_remote_inference, false);
el('allow-remote').checked = true;
assert.equal(projectSpec().allow_remote_inference, false);
""")


@pytest.mark.parametrize("budget", [1, 1023, 131073, 32768.5])
def test_context_budget_matches_backend_bounds(budget):
    evaluate(f"""
fill();
inferenceMode = 'local';
el('project-budget').value = {json.dumps(str(budget))};
assert.equal(projectSpec(), null);
assert.match(el('project-errors').textContent, /1024 to 131072/);
    """)


def test_scan_intensity_derives_cycles_and_custom_restores_legacy_editing():
    evaluate("""
fill();
inferenceMode = 'local';
updateScanProfile();
assert.equal(el('project-cycles').readOnly, true);
assert.equal(el('project-red-agents').disabled, true);
assert.equal(el('project-blue-agents').disabled, true);
assert.equal(projectSpec().scan_profile, 'extra_light');
assert.equal(projectSpec().cycles, 1);
assert.equal(projectSpec().red_agents, 5);
assert.equal(projectSpec().blue_agents, 5);
el('project-scan-profile').value = 'ultra_heavy';
updateScanProfile();
assert.equal(el('project-cycles').value, '12');
assert.equal(el('project-red-agents').disabled, false);
assert.equal(el('project-blue-agents').disabled, false);
assert.match(el('project-scan-description').textContent, /Red, Blue, Red, Blue/);
assert.match(el('project-scan-description').textContent, /bounded automatic discovery/);
el('project-scan-profile').value = 'custom';
updateScanProfile();
assert.equal(el('project-cycles').readOnly, false);
el('project-cycles').value = '9';
assert.equal(projectSpec().cycles, 9);
    """)


def test_dashboard_markup_defaults_to_extra_light_and_five_agent_teams():
    markup = INDEX.read_text()
    assert '<option value="extra_light" selected>' in markup
    assert 'id="project-cycles"' in markup and "readonly" in markup
    assert 'id="project-red-agents"' in markup and 'name="red_agents"' in markup
    assert 'id="project-blue-agents"' in markup and 'name="blue_agents"' in markup
    assert markup.count("Ultra heavy only") == 2
    assert markup.count('max="12" value="5"') >= 2


def test_cycle_result_label_includes_named_profile_pass_number():
    evaluate("""
const list = el('cycle-list');
list.children = [];
list.replaceChildren = () => { list.children = []; };
list.append = (node) => list.children.push(node);
global.document = {createElement: (tag) => ({
  tagName: tag, className: '', open: false, textContent: '', children: [],
  append(...nodes) { this.children.push(...nodes); }
})};
renderCycles([{cycle: 2, pass_number: 1, status: 'retained'}]);
assert.equal(list.children[0].children[0].textContent, 'Cycle 2 · pass 1 · retained');
""")


@pytest.mark.parametrize("field,value", [("project-red-agents", 0), ("project-blue-agents", 13)])
def test_team_sizes_match_backend_bounds(field, value):
    evaluate(f"""
fill();
inferenceMode = 'local';
el({json.dumps(field)}).value = {json.dumps(str(value))};
assert.equal(projectSpec(), null);
assert.match(el('project-errors').textContent, /agents must be a whole number from 1 to 12/);
""")


@pytest.mark.parametrize(
    "mode,key,ready", [("local", False, True), ("hosted", False, False), ("hosted", True, True)]
)
def test_dashboard_readiness_and_consent_visibility(mode, key, ready):
    health = json.dumps(
        {
            "inference_mode": mode,
            "api_key_configured": key,
            "inference_ready": ready,
            "docker": {"state": "ready"},
        }
    )
    evaluate(f"""
global.fetch = async (url) => ({{ok: true, json: async () => url === '/api/health' ? {health} : {{}}}});
(async () => {{
  await initialize();
  assert.equal(configured, {str(ready).lower()});
  assert.equal(el('run-btn').disabled, {str(not ready).lower()});
  assert.equal(el('allow-remote').label.hidden, {str(mode == "local").lower()});
  assert.equal(el('allow-remote').required, {str(mode != "local").lower()});
}})().catch(error => {{ console.error(error); process.exitCode = 1; }});
""")


def test_project_summary_counts_observed_cycle_evidence_without_inventing_checks():
    evaluate("""
const good = {fresh_target:true, probe:{exit_code:1}, regression:{exit_code:0}};
const pre = {...good, probe:{exit_code:0}};
const cycle = {evidence:{pre_verification:pre, patched_verification:good}};
const result = summaryEvidence({baseline_verification:good, cycle_reports:[cycle,cycle]});
assert.equal(result.baseline_passed, true);
assert.equal(result.regression_passed, true);
assert.equal(result.pre_summary, '2/2 reachable');
assert.equal(result.post_summary, '2/2 blocked');
const failed = summaryEvidence({cycle_reports:[cycle,{evidence:{patched_verification:{...good, probe:{exit_code:2}, regression:{exit_code:1}}}}]});
assert.equal(failed.post_summary, '1/2 blocked');
assert.equal(failed.post_good, false);
assert.equal(failed.regression_passed, false);
const absent = summaryEvidence({cycle_reports:[]});
assert.equal(absent.baseline_passed, undefined);
assert.equal(absent.regression_passed, undefined);
assert.equal(absent.pre_exit_code, undefined);
assert.equal(absent.post_exit_code, undefined);
const fixture = {baseline_passed:true, post_exit_code:1};
assert.equal(summaryEvidence(fixture), fixture);
""")


def test_project_model_usage_identifies_blue_roles():
    evaluate("""
const document = {createElement: () => ({dataset:{}, children:[], append(...nodes) {this.children.push(...nodes);}})};
const list = el('usage-calls');
list.children = [];
list.replaceChildren = () => { list.children = []; };
list.append = (node) => list.children.push(node);
const roles = ['red','blue','project_red_initial_report_cycle_1','project_blue_proposal_cycle_1_batch_0','project_blue_final_report_cycle_1'];
renderUsage({usage:{calls: roles.map(role => ({role,model:'muse-spark-1.3',prompt_tokens:1,completion_tokens:1,reasoning_tokens:0,seconds:0,cost_usd:0}))}});
assert.deepEqual(list.children.map(node => node.dataset.team), ['red','blue','red','blue','blue']);
assert.deepEqual(list.children.map(node => node.children[0].textContent), ['Red','Blue','Red','Blue','Blue']);
""")
