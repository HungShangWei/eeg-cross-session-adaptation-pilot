# Validation scope: what was checked, and what was not

This page separates four layers of evidence for the reported execution. They are not equivalent and none of them is an independent scientific reproduction.

Responsibility and tool use: [My contribution](../README.md#my-contribution).

## 1. What the run did (executed 2026-10-27, Asia/Taipei)

One supervised execution of the fixed code identity (45 objects, manifest SHA-256 `bdc2c4cd778b0c601ea7ff08b20c6272fd27187421cc2850bf32f62ac1353b4c`) ended normally (supervisor return code 0) after a measured process envelope of about 448 s on an Apple Silicon Mac, CPU only. In that execution:

- all nine participants were qualified before any preprocessing was fitted;
- 9 preprocessing pipelines, 27 source models (9 participants × 3 seeds, 100 epochs each), 9 frozen source-setting choices and 27 source temperatures were rebuilt from the raw files, with no earlier models reused;
- all 54 T/H instances completed, each with exactly 10 received trial–label pairs from session-4 positions 0–9;
- all predictions were sealed before the scorer obtained the evaluation labels.

The execution took place on 2026-10-27. It used an author sign-off bound to the exact candidate and a template version dated 2026-10-26; that version date is not presented as the timestamp of the author's approval. This was an administrative step, not an ethics, institutional or external approval.

## 2. Checks performed by the run itself

These checks were built into the code and executed as part of the run. Their outcome is recorded in the run's saved summaries (aggregate facts in the [provenance record](PROVENANCE.json)):

- **Code identity**: the launcher refused to start unless every candidate file matched the bound manifest.
- **Event ledger**: worker and supervisor events were written as hash chains (each event includes the previous event's hash).
- **Feedback chain**: for each instance, request → receipt → three recorded label uses → end of access, bound to one recipient and one call. Each use was checked against the fingerprint of the receipted labels.
- **State changes**: before/after fingerprints showed only allowed fields changed (T: temperature/status; H: head/status); no forbidden change in 54 of 54.
- **Seal and release**: all state and prediction files were re-verified before sealing and again before Q labels were released. In the worker's event sequence, the last end of label access (36351) precedes the seal (36359), which precedes the label release (36360–36361) and the completion of scoring (36369).
- **Scoring cross-check**: each instance was scored twice by separate code paths, with exact equality of counts and agreement of J and C within 1e-12. The inferential outputs were computed by two implementations, and the run required them to agree within 1e-10. Comparing the two saved outputs in `primary_results.json` after the run gives a largest difference of 2.2e-16.

## 3. Checks made after the run on its saved records

- **By the run's producer** (the same workflow that prepared and launched the code), at close-out: all 45 code objects still matched; both hash chains verified as valid on the full ledgers; an evidence index linked each instance's events, state and prediction records; and a follow-up check showed that a reported mismatch between saved and sealed source fingerprints was a JSON-versus-NumPy serialization difference (all 21,708 scalar fingerprints matched; arrays were not decoded).
- **In a separate internal check** (working only from the exported records and the exact code copy): a separately written checking script recomputed J and C from the saved counts for all 54 instances, the participant means, the five t intervals, the 5-of-9 counts and the decision logic. It also checked the event projections against the code. All 499 checks passed. This review read no EEG, label values, predictions, weights or the original ledgers, re-ran nothing, and did not recompute the hash chains or the bootstrap.

## 4. Checks made for this public showcase

When the showcase was first prepared (2026-10-27):

- The result tables and CSV files are deterministic projections of `results/primary_results.json`, verified value by value and against the saved counts (`python scripts/make_result_tables.py --check`).
- The figure was redrawn from the same file and inspected visually.
- The public code copies were hashed against the executed identity (39 identical, 3 path-projected configuration files).
- All Python files were parsed for syntax. The launcher was run only in its refusal modes; it stopped before reading any data.
- Relative links were checked, and the public files were scanned for local paths and personal or sensitive data.

For this release copy (2026-11-01, UTC):

- File, module and run identifiers carry neutral names, and in eight Python files comments that read as if the code had not yet run were corrected. Every Python file was compared statically with the executed file: once the renames are reversed, its syntax tree is unchanged apart from docstrings, and its tokens differ only in comments and docstrings. These files were not re-executed, and 25 of the 39 no longer match the executed hashes ([source map](PUBLIC_SOURCE_MAP.json)).
- The results file and the provenance record are public projections. Each was compared field by field with the saved original: every number (as written), flag, state, count and ordering is unchanged; only identifier fields differ, the provenance record gains fields describing this release copy, and a note marks each projection.
- `python scripts/make_result_tables.py --check` passed on this release copy (Python 3.13.17).
- The two figures were redrawn on 2026-10-31 from the same pinned values after four title and note strings were changed (Matplotlib 3.11.2), and inspected visually; this release copy renames their files without redrawing them.
- Relative links and anchors were checked, and all public files, paths and rendered pages were scanned for local paths, credentials and private material.

For the release identity tooling (2026-11-02, UTC):

- `python tools/tests/test_code_identity.py` passed (28 tests, Python 3.13.17). Manifests written by `tools/code_identity.py` were accepted by the unmodified `identity_check()` of `candidate/launch.py`, loaded in a separate process without running its entry point; changed, added, removed or renamed files were rejected by both. These tests concern file identity only; the environment, data, resources, approvals and a full run were not tested.

## What has not been done

- **No independent re-execution** of the pipeline by another person, machine or environment. This release copy (derived configuration, renamed and comment-corrected files) has not been run end to end.
- **No external review**, peer review or certification. The checks above were made within the author's own workflow and do not replace independent replication.
- **No recomputation from raw data** after the run: predictions, states and weights were not re-derived, and the original ledgers are not published (they contain label values).
- **No operating-system isolation.** The label boundary is a program-level boundary inside one process (see [METHODS_AND_LIMITATIONS.md §7](METHODS_AND_LIMITATIONS.md#7-feedback-access-sealing-and-scoring)).
- **No fresh blind test.** The dataset is public and had been analysed earlier in this project ([methods §10](METHODS_AND_LIMITATIONS.md#10-limitations)).
- **No extension beyond the run's scope**: no other budgets, costs, comparators, datasets, modalities or human-in-the-loop evaluation.
