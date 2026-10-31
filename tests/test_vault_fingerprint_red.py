# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""RED: fingerprint_source must not equate vacuous inputs or case variants.

fingerprint_source() feeds query_vault()'s KNOWN/NOVEL verdict, which gates
whether Red skips a full analysis round. Two collisions would corrupt that
gate:
- empty source vs comment-only source share the sha256-of-empty digest,
  so a novel empty target recalls as KNOWN the moment any vacuous source
  was ever committed.
- identifier case is folded away nowhere, yet language keywords/functions
  are case-sensitive: `Eval(X)` vs `eval(x)` must differ (they do today;
  pinned against regression).
"""

from modules.intel.sms_vault import fingerprint_source


def test_empty_source_is_not_equivalent_to_comment_only():
    empty = fingerprint_source("")
    assert empty != fingerprint_source("# nothing but a comment\n")
    assert empty != fingerprint_source("   \n")


def test_identifier_case_changes_fingerprint():
    assert fingerprint_source("eval(x)") != fingerprint_source("Eval(X)")


def test_statement_order_is_stable_but_content_sensitive():
    a = "eval(alpha)\nopen(beta)\n"
    b = "eval(alpha)\nopen(gamma)\n"
    assert fingerprint_source(a) == fingerprint_source(a)
    assert fingerprint_source(a) != fingerprint_source(b)
