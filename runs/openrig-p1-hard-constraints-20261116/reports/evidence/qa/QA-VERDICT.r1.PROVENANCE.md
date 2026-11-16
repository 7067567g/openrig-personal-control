# Provenance — QA-VERDICT.r1.md

- **Not the active verdict.** `reports/QA-VERDICT.md` (r2, 14421 bytes, sha256
  `df7588116c45d571b6ea190ec1df1b94951b9d2bd59560e9d881c65868e4944d`) supersedes this file.
- **What this file is:** the exact bytes of QA-VERDICT r1 as handed off at
  `qitem-20261115170024-c98f0ab1`'s closure transition `2026-11-15T17:05:23.494Z`.
- **Why it exists:** the `qa_final` closure recorded evidence digest
  `bbde1ad1696fae0c6e53b11ac9a70f4e8d4a1e4ead0f2df739ca1b13ec84e5fa`. That digest is verifiable only against
  byte-identical r1 content, so no note is inlined here — an inlined note would change the bytes and
  invalidate the digest. This sidecar carries the note instead.
- **Verification:**
  `sha256sum reports/evidence/qa/QA-VERDICT.r1.md` → `bbde1ad1…84e5fa` (11998 bytes).
- **How r1 was recovered:** reverse-applying the six documented r2 edits (r2 section 1.1 insert,
  header/version block, live-drift note, F-2/F-6 row rewrite, §1.2 → §1 rename, evidence-index line).
  Script: `/tmp/opencode/qa-p1/reconstruct-r1.py` (QA workspace, not part of the repo).
- **Use:** audit retrieval only. Do not cite it as the current QA verdict, and do not overwrite r2 with it.
