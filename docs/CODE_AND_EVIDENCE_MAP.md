# Code and evidence map

The [code folder](../code/pilot/candidate/) holds a release copy of the source files of the code identity that ran in the reported execution on 2026-10-27. That identity is a manifest of 45 objects, SHA-256 `bdc2c4cd778b0c601ea7ff08b20c6272fd27187421cc2850bf32f62ac1353b4c`. The launcher checked it before the run started, and a close-out check after the run found all 45 objects unchanged ([VALIDATION_SCOPE.md](VALIDATION_SCOPE.md)). The release copy keeps the folder structure of the executed code; folder, file, module and run identifiers carry neutral names.

## How this release copy relates to the executed files

- **14 Python files are byte-identical** to the executed files (one of them under a new file name).
- **25 Python files differ in names or comments only.** In 23 of them, module and file names, one local variable and a few docstring labels were renamed; in 8 (6 of which were also renamed), comments or docstrings that read as if the code had not yet run were corrected. Code statements, numerical constants and control flow are otherwise unchanged. These files were not re-executed.
- **3 configuration files.** `RUN_CONFIG_v1.json` is a derived configuration: the local project path is replaced by `<PROJECT_ROOT>`, the run identifier and local folder names by neutral aliases or role names, and a `public_projection` note marks the change. Non-runtime setup metadata is omitted from this release copy; the omitted fields and the full name mapping are retained privately. `DATA_MANIFEST_v1.json` and `ENVIRONMENT_METADATA_v1.json` are copies in which only the local project path was replaced. All three differ from the executed files (hashes below).
- **3 identity objects are not included**: the execution-command record (a pre-run administrative record holding local paths), and two internal planning records (`SOURCE_REUSE_DECISION_v1.json`, `WORKLOAD_AND_FEASIBILITY_v1.json`) that hold local paths and are not read by the code.
- **Release identity tooling (outside `candidate/`)**: `code/pilot/RELEASE_CODE_IDENTITY.json` lists the size and SHA-256 of the 42 files in `candidate/` of this release copy, `tools/code_identity.py` writes and checks such manifests, and `tools/tests/` holds its tests. They were added for this release, took no part in the reported execution, and the manifest is not the original identity manifest.

The [provenance record](PROVENANCE.json) and the results file are public projections: identifier fields hold neutral aliases and a `public_projection` note marks the change, while every count, value, flag, state and ordering is unchanged. The executed originals and the full correspondence between executed and release-copy names are kept privately by the author and are not part of this repository. The [public source map](PUBLIC_SOURCE_MAP.json) lists, for every file here, its original SHA-256 values (the recorded hash of the executed object, and that of the public copy of 2026-10-27 from which this copy was prepared), its current SHA-256, the type of change and the evidence it supports.

## How the import path works

The launcher sets the import path to `runtime_modules/`, then `frozen/`, then the candidate root. Six modules exist in both folders; for those, the `runtime_modules/` copy is the one that ran. The `frozen/` copies are kept because they are part of the bound identity and show what was changed for the reported execution:

| Module | Effective copy | What the effective copy changes relative to `frozen/` |
|---|---|---|
| `composition.py` | `runtime_modules/` | records a `schema_validation` label use before T/H adaptation |
| `contracts.py` | `runtime_modules/` | the source freeze requires only the T, H and checkpoint choices (the frozen copy also required N and EA choices) |
| `numeric_dependencies.py` | `runtime_modules/` | records `class_gate` and `optimizer` label uses during target fitting |
| `source_recipe_e3prep.py` | `runtime_modules/` | develops only T and H on the source session (no N or EA branches) |
| `statistics_recipe.py` | `runtime_modules/` | refuses to generate a new bootstrap matrix; only the existing matrix may be used |
| `trusted_ingress.py` | `runtime_modules/` | adds audit records around source preprocessing |

## Files by role

The files are grouped by what they do in the run. A module can serve more than one role, and is then listed where its main role lies, with a note. The evidence controls in group 2 are part of the method, not decoration: they decide which labels an update may see and when scoring may begin. The local operation in group 3 was a precondition of the run as executed. Paths are relative to `code/pilot/candidate/`; the [method walkthrough](METHOD_WALKTHROUGH.md) follows the same code in run order.

**1. Scientific computation: partitions, preprocessing, source models, T/H, scoring and statistics**

| File | Role |
|---|---|
| `frozen/science_contract.py` | Constants (prefix 40, budgets, primary budget 10, seed bases) and the source and target partitions (`split`) |
| `data_service.py` | Verifies and loads the MAT files, partitions trials and applies the frozen preprocessing (also group 2) |
| `frozen/signal_recipe.py`, `runtime_modules/trusted_ingress.py` | Preprocessing (8–32 Hz zero-phase band-pass, EOG regression, resampling to 128 Hz, crop, standardization), fitted on the source training partition only |
| `frozen/neural_recipe.py` | EEGNet-style network, deterministic setup, feature extraction, batch-normalization moment recomputation |
| `runtime_modules/source_recipe_e3prep.py`, `frozen/source_selection.py` | Source training for three seeds, checkpoint choice, T/H setting grids with their tie rules, and the source temperature fitted on S-cal |
| `model_adapter.py`, `runtime_modules/composition.py` | T/H adapter: builds source states, copies them per instance, applies one update (`adapt_core`) and predicts Q (`predict_core`); `score_sealed` scores the sealed outputs and writes `primary_results.json` (also group 2) |
| `frozen/solvers_recipe.py`, `frozen/operations.py` | Temperature grid search, regularized head refit (L-BFGS-B), grid construction, candidate checks |
| `scorer.py` | Per-instance J and C; aggregation (3 seeds, then 9 participants); call to the primary inference |
| `frozen/inference_contract.py`, `runtime_modules/statistics_recipe.py` | Composite primary-hypothesis logic: t intervals, non-inferiority, usefulness, active-fit guard, bootstrap robustness on the existing matrix |
| `independent_statistics.py` | Second, pure-Python implementation of the inferential outputs, compared with the primary one at tolerance 1e-10 (also group 2) |

**2. Validity and evidence control: permitted labels, state checks, seal and scoring order, records**

| File | Role |
|---|---|
| `audit_core.py` | Hash-chained event ledger; `Feedback` (request, receipt, use, end of access); `state_change` (only the allowed fields may change); `Cohort` (seal and post-seal label release) |
| `account.py`, `runtime_modules/numeric_dependencies.py` | Checks each label use against the receipted view and records its purpose; operation caps |
| `data_service.py` | Serves only positions 0–9 with labels, a label-free Q view, and Q labels only after re-checking the seal; enforces the source freeze and the one-time S-cal release |
| `runtime_modules/contracts.py` | Indexed blocks and partition checks; `StagedSourceBroker` freezes the source choices before S-cal is released |
| `content_identity.py`, `frozen/accounting.py` | Content hashes, state fingerprints, stored artifacts, array fingerprints |
| `flow.py` | Order of operations: all nine participants qualified before any fitting; per instance request → receipt → adaptation → saved state → Q prediction → end of label access; then seal, label release and scoring (also group 1) |

**3. Local operation: run permission, path and environment checks, resource guards, supervision**

| File | Role |
|---|---|
| `supervise.py` | Formal entry point. Checks the code identity, the local approval record, the Python environment and a new run directory. Starts `launch.py` as a child process, enforces a time cap and keeps a separate supervisor ledger. |
| `launch.py` | Worker entry. Repeats the identity, approval and environment checks, and requires the supervisor's handoff record. Installs an audit hook that blocks writes outside the run directory and all network access. Sets the import path and runs `flow.execute_core`. |
| `resource_guard.py`, `native_helper.py` | Resource checks during the run (memory pressure, available memory, process memory, free disk, allocated bytes), using three allow-listed macOS tools (`vm_stat`, `sysctl`, `ps`). |
| `config/` | Run configuration, data manifest and environment pins (below), read by the entry points and the data service |

These guards are kept as they ran; this repository provides no reduced entry point that skips them ([reproducibility](REPRODUCIBILITY.md)).

**Outside the T/H path.** `frozen/inference_audit.py`, `frozen/ea_recipe.py` and `frozen/array_edges.py` are part of the bound identity but hold code for comparisons outside the reported execution (H-P2 checks, alignment-based features); they are not called on the T/H path.

**Tests (`tests/`)**: synthetic engineering tests of the boundaries, the integration path and the start-up guards. They need the original directory layout, the original environment and a local scratch directory, and **were not run for this showcase**.

**Configuration (`config/`)**: `RUN_CONFIG_v1.json` (protocol hash, design constants, recipe, decision rule, resource policy), `DATA_MANIFEST_v1.json` (MAT files and their sessions, sizes and hashes), `ENVIRONMENT_METADATA_v1.json` (interpreter and five package versions). Two fields record the pre-run administrative state: `preparation_status` is checked by the entry points, and `formal_execution_authorized` (false) is not read by them (only an engineering test reads it). Both are kept unchanged.

**Comments and flags from code preparation.** Some docstrings, comments and module constants were written while the code was being prepared. In eight files, wording that read as if the code had not yet run was corrected in comments and docstrings only. Constants, flags and strings were not changed because they are code: for example `FLAGS` in `frozen/science_contract.py` and both copies of `contracts.py` (`non_formal=True`, `formal_execution_authorized=False`, `publishable_as_pilot_results=False`; no module reads these), `formal_source_plan()` in `frozen/source_selection.py`, and error codes such as `PREP_BLOCKED`. The shadowed `frozen/` copies keep their original wording. These items describe the preparation stage, not the reported execution, which did execute this code on real data on 2026-10-27.

| Config file | Executed SHA-256 | This release copy SHA-256 |
|---|---|---|
| `RUN_CONFIG_v1.json` | `388e2172e0ae8a803451dd7e50dee8af2b5d3a1aecac7154eb6317744c7d6bed` | `3ed6a42a724ec0ac46047501b2f79db8d589d308f7484c60e2a0c712d9d5e9f8` |
| `DATA_MANIFEST_v1.json` | `d547ea29c8f64363aa68c0e43178e5c3609155fae43cbb224224bf85c12d80e3` | `8cf7112a2bb38255c0cc82caa2b5852fcb4089972ff6930aeb7a054014501538` |
| `ENVIRONMENT_METADATA_v1.json` | `6a16b2bcf0571a16e2a6df925b974805c530b9a5376ce5d3bc0c358897436511` | `42970ac30f9d42448783decc304a6f357e714274218172bb645b0d1aeb24c492` |

## Internal labels you will meet in the code

| Label | Meaning |
|---|---|
| `DREC01` | the project's internal name for this cross-session T-versus-H study (an earlier, broader analysis in this project used the same name; see [methods §10](METHODS_AND_LIMITATIONS.md#10-limitations)) |
| `DREC01_CORE_VALIDATION_PUBLIC_ALIAS_PILOT` | public alias used in this release copy for the run identifier of the reported execution; it does not indicate additional results, and the original identifier is kept privately |
| `candidate` | the frozen code folder whose executed bytes the identity manifest bound; this repository holds a release copy of it |
| `B2R`, `B2_R` | internal name of the code revision used for the reported execution (appears in schema names, error codes and local folder names) |
| `PREP`, `prep_root`, `parent_prep_root` | the code-preparation stage before the run and its local folders; at run time the disk guard only measures their size |
| `grant`, `approval` | the author's own pre-run sign-off record that the entry points require (not an ethics, institutional or external approval) |
| `E1`, `E2`, `E3`, `OPS01`, `H-P1`, `H-P2` | stage and hypothesis labels from earlier protocol documents; in the reported execution only the H-P1 logic (T substitutes for H) is evaluated |
| `K`, `N`, `EA`, `EA_source`, `EA_L` | comparators of the earlier, broader analysis; present in shadowed or unused code, not run in the reported execution |

## Where each claim is supported

| Claim | Code | Saved evidence (public) |
|---|---|---|
| Each update received and used only valid pairs from positions 0–9 of session 4 | `data_service.py` (prefix), `audit_core.py` (Feedback), `account.py`, `runtime_modules/numeric_dependencies.py`, `runtime_modules/composition.py` | aggregate feedback counts in the [provenance record](PROVENANCE.json) (`feedback`) |
| Only the temperature (T) or the head (H) changed | `audit_core.state_change`, `content_identity.py` | `state_changes` in the provenance record |
| Predictions were sealed before the scorer obtained Q labels | `audit_core.Cohort`, `data_service.scoring_labels`, `flow.py` | `ordering` in the provenance record |
| J, C, intervals and decisions | `scorer.py`, `runtime_modules/statistics_recipe.py`, `frozen/inference_contract.py`, `independent_statistics.py` | [results/primary_results.json](../results/primary_results.json) |
| Preprocessing and models fitted on source data only | `frozen/signal_recipe.py`, `runtime_modules/trusted_ingress.py`, `runtime_modules/source_recipe_e3prep.py` | code only (no fitted parameters are published) |

The event ledger itself (about 79 MB, which includes label values), the seal file, the saved states and the per-trial predictions are **not** published. The public evidence is limited to aggregate counts and ordering facts taken from the run's own summaries. See [VALIDATION_SCOPE.md](VALIDATION_SCOPE.md).
