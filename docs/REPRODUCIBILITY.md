# Reproducibility

Three levels are listed separately, each with its inputs, environment, outputs and **tested status**. That the original command succeeded on the author's machine does not mean this release copy (derived configuration, renamed and comment-corrected files) has been run. It has not.

## Level 1 — saved results → tables and figures (tested)

| | |
|---|---|
| Input | `results/primary_results.json` (included; SHA-256 pinned in the scripts); figures also read the pinned `code/pilot/candidate/config/RUN_CONFIG_v1.json` for the non-inferiority margin |
| Environment | Tables: Python ≥ 3.9, standard library only. Figures: additionally Matplotlib |
| Commands | `python scripts/make_result_tables.py --check` (verify) · `python scripts/make_result_tables.py` (rewrite CSVs) · `python scripts/plot_participant_results.py` (both figures) |
| Outputs | `results/group_estimates.csv`, `results/participant_results.csv`, `results/decision_criteria.csv`, the tables embedded in `README.md` and `results/README.md`, `results/figures/participant_results.png`, `results/figures/loss_difference.png` |
| Status | Run for this showcase on 2026-10-27: the table script with Python 3.14.7, and the figure script with Matplotlib 3.11.2 from the original run environment. No statistic is recomputed; the scripts only project and format saved fields. |
| Visual update check | 2026-10-27 (Asia/Taipei): both PNGs generated with existing CPython 3.14.7, Matplotlib 3.11.2 and DejaVu Sans; the table check also passed. Only saved values and the frozen margin were read, with no new statistics or research execution. The original showcase record above is retained. |
| Display update | 2026-10-31 (UTC), Linux x86_64: four title and note strings in `scripts/plot_participant_results.py` were changed to drop an internal run label, and both PNGs were regenerated from the same pinned inputs with Python 3.13.17 and Matplotlib 3.11.2 (DejaVu Sans) in an environment holding only Matplotlib and its dependencies. Text anti-aliasing differs slightly from the earlier PNGs in this environment; values, marks and layout are unchanged. The table check also passed with Python 3.13.17. No statistic was recomputed and no research code was run. |
| Release copy check | 2026-11-01 (UTC), Linux x86_64: after file and identifier renaming, `python scripts/make_result_tables.py --check` passed on this release copy with Python 3.13.17. The two PNGs were renamed without being redrawn. |

```bash
python scripts/make_result_tables.py --check
```

## Level 2 — data and fitted states → predictions (not available)

The fitted source models and adapted states (network weights, heads, temperatures) are **not published**. The candidate has no separate inference entry point: predictions are produced only inside the full run (Level 3), by `ModelAdapter.predict` after an adaptation. Prediction from saved states is therefore not possible with this repository, and no command is offered for it.

## Level 3 — raw data → full re-run (code provided; public copy not run)

**What ran.** On 2026-10-27, the pilot was executed once on the author's machine with the command below, shown here with the local project path replaced by `<PROJECT_ROOT>` and the run directory by `<RUN_ROOT>`. The supervisor returned 0 after a process envelope of about 448 s.

```text
<PROJECT_ROOT>/.venv_mi_ops_e1_v1_1/bin/python -B \
  <CANDIDATE_PARENT>/candidate/supervise.py \
  --identity <CANDIDATE_PARENT>/CANDIDATE_IDENTITY_v2.json \
  --approval <path to the local approval record> \
  --run-root <RUN_ROOT>
```

`<CANDIDATE_PARENT>` was a directory inside the author's project; in this release copy it corresponds to `code/pilot/`, whose files carry neutral names. The working directory was `<CANDIDATE_PARENT>`.

**Requirements, as enforced by the code.** The entry points are deliberately strict and fail closed.

1. **Platform**: macOS. The resource guard calls `/usr/bin/vm_stat`, `/usr/sbin/sysctl -n kern.memorystatus_vm_pressure_level` and `/bin/ps` and parses their macOS output. It requires memory-pressure level 1, at least 16 GiB of available memory at start, and at least 15 GiB of free disk.
2. **Environment**: `config/ENVIRONMENT_METADATA_v1.json` must match `sys.executable`, `sys.version` and `sys.prefix` exactly. It must also match the five package versions in the [core requirements file](../environment/requirements-core.txt) (CPython 3.14.7, NumPy 2.5.3, SciPy 1.18.1, PyTorch 2.14.1, pyRiemann 0.12, scikit-learn 1.9.1). The other packages of the original environment are listed in [environment/venv-freeze-2026-10-27.txt](../environment/venv-freeze-2026-10-27.txt).
3. **Data**: the 18 MAT files listed in [data/README.md](../data/README.md), at the paths in `config/DATA_MANIFEST_v1.json`. Each must match its expected size and SHA-256, or loading stops.
4. **Bootstrap matrix**: `protocol/participant_resamples.npy`, at the path in `config/RUN_CONFIG_v1.json` (`bootstrap.path`), with the pinned size and hash.
5. **Paths**: every `<PROJECT_ROOT>` in the three configuration files must be replaced by a real directory. The run root must not exist beforehand and must equal `run_root` exactly. The resource guard also measures the folders in `parent_prep_root`, `prep_root`, `retained_accounted_roots` and `controlled_roots`; in this release copy their names describe roles. Map each role to the directory whose disk use must be counted, and keep the retained roots: a path that does not exist is counted as empty.
6. **Code identity**: the launcher refuses to start unless a manifest lists every file under `candidate/` (paths relative to the candidate's parent directory, with byte sizes and SHA-256). Because step 5 changes the configuration files, a new manifest must be written. The resulting code identity is new and differs from that of the reported execution. This release copy also renames files, modules and run identifiers and corrects some comments, so most file hashes differ from the executed ones ([source map](PUBLIC_SOURCE_MAP.json)); the executed files are not part of this repository. The original identity manifest cannot be reused. From the repository root, `python tools/code_identity.py verify --candidate code/pilot/candidate --manifest code/pilot/RELEASE_CODE_IDENTITY.json` checks the unmodified `candidate/` of this release copy against [`RELEASE_CODE_IDENTITY.json`](../code/pilot/RELEASE_CODE_IDENTITY.json) (standard library only; no data or run environment needed). After your own changes (step 5 and item 7), write a new local manifest outside `candidate/` with `python tools/code_identity.py generate --candidate code/pilot/candidate --output code/pilot/LOCAL_CODE_IDENTITY.json` and pass that file to `--identity`. In engineering tests on 2026-11-02, manifests written by this tool were accepted by the unmodified `identity_check()` in `launch.py`, and changed, added, removed or renamed files were rejected. A manifest records file identity only: it is not an approval, the other requirements on this page still apply, and no full re-run has been made.
7. **Approval record**: both entry points require a local JSON approval record. It must name the run ID, the manifest's SHA-256, the resource policy `FORMAL_NORMAL_REQUIRED` and the exact list of authorized operations in `RUN_CONFIG_v1.json`. It must also carry an `approved_by` value, which `launch.py` and `supervise.py` compare with the original author's name. This is an administrative gate of the author's own workflow, not a scientific step. No approval record is published, and none of the reported execution's authorization carries over to any other run. **Do not write an approval record in the author's name for your own run.** Instead, in your own copy, change that comparison in both files to your own name. Like the path edits in step 5, this changes the code identity (step 6), and the outputs are a new run, not the reported execution.

**Steps.** (1) Obtain the data and place the files. (2) Create an environment with the pinned versions. (3) Edit the paths in `config/`. (4) In your own copy, set the `approved_by` comparison to your own name (item 7), then write the identity manifest and a local approval record for your own run. (5) Start `supervise.py` with `--identity`, `--approval` and a new `--run-root`. The supervisor starts `launch.py` itself; do not start `launch.py` directly. Outputs (ledgers, states, predictions, seal, `scoring/primary_results.json`) are written only under the run root.

**Tested status.** The public copy was *not* run end to end, and its dependencies were not installed for this showcase. The steps above are derived from the code, not from a completed public re-run. Cross-platform runs are not supported as written. On the copy first published on 2026-10-27, the launcher was run only in its refusal modes, which stop before reading any data (shown with this release copy's path; not re-run on this release copy):

```bash
python -B code/pilot/candidate/launch.py --check-unapproved   # stops: EXECUTION_NOT_APPROVED: PREP_BLOCKED (exit 2)
python -B code/pilot/candidate/launch.py                      # stops: EXECUTION_NOT_APPROVED: EXACT_GRANT_REQUIRED (exit 2)
```

`--help` prints the options and then also exits with status 2, because the entry point's catch-all error handler intercepts the normal help exit.

**Engineering tests.** `code/pilot/candidate/tests/` contains the synthetic boundary, integration and start-up tests used while preparing the code. They need the original directory layout, environment and bootstrap path, and they write to a scratch directory beside the candidate. They were not run for this showcase.
