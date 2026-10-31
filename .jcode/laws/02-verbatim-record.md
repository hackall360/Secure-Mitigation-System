# LAW 2 (mirror of repo-root LAWS.md — canonical source stays at root per LAW 0)

### LAW 2 — Verbatim record: write down exactly what the user said

When the user gives a task, brief, correction, or new requirement, FIRST
write their words down verbatim — no paraphrase, no trimming — in a
git-ignored log, then decompose without dropping anything:

1. Append a dated file under `.jcode/briefs/` (e.g.
   `.jcode/briefs/2026-10-28-topic.md`) containing the user's full message
   in a blockquote, followed by your decomposition: one numbered item per
   distinct ask, constraint, or fact.
2. `.jcode/briefs/` is git-ignored. The verbatim record lives for agents,
   not for the repo. (The user once wrote `.jode`; the repo convention is
   `.jcode`. Honor the intent — git-ignored agent log — under the real path,
   and note the mapping in the brief.)
3. If a later message contradicts or supersedes an earlier brief, add a new
   brief file that cites the old one. Never silently edit a past verbatim.

