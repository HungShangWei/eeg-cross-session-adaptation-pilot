# Method walkthrough

This page follows one path through the pilot, from the data split to the saved scores. It adds no analysis; full details and limits are in [methods and limitations](METHODS_AND_LIMITATIONS.md), and every file is described in the [code and evidence map](CODE_AND_EVIDENCE_MAP.md). Code paths are relative to `code/pilot/candidate/`. At run time `launch.py` (`worker_startup`) puts `runtime_modules/` before `frozen/` on the import path, so where a module exists in both folders, the `runtime_modules/` copy is the one that ran.

## 1. Four numbers with different jobs

For each of the nine people, `data_service.py` (`DataService.qualify`) loads physical session 3 as the source and physical session 4 as the target, and `frozen/science_contract.py` (`split`) fixes the partitions.

| Item | Job |
|---|---|
| Session 3 → 4, same person | Source models are trained and calibrated on session 3 only; session 4 is the new session. |
| 40-trial prefix (positions 0–39) | Fixes where evaluation starts; positions 10–39 are never released to any method. |
| Ten permitted labels (positions 0–9) | The only target labels an update may receive (`DataService.prefix`). |
| Evaluation segment Q (position 40 onward) | Scores both methods on the same trials; its view carries no labels (`DataService.q_features`). |

## 2. Choices fixed on source data

Preprocessing is fitted on the source training partition only (`runtime_modules/trusted_ingress.py`, `preprocess_development`, using `frozen/signal_recipe.py`). `runtime_modules/source_recipe_e3prep.py` (`prepare_full_source`) trains three seeds, chooses one checkpoint and chooses the T and H settings on source partitions. `runtime_modules/contracts.py` (`StagedSourceBroker`) freezes these choices before the last source partition (S-cal) is released to fit each seed's source temperature Ts. No target data reach any method at this stage.

## 3. Target feedback and the two updates

`flow.py` (`execute_core`) runs 54 instances (9 people × 3 seeds × 2 methods). For each, `audit_core.py` (`Feedback`) records the request for positions 0–9, the receipt, each label use and the end of access, and `account.py` checks every use against the receipted labels. `runtime_modules/composition.py` (`adapt_core`) then applies one update from `frozen/solvers_recipe.py`:

- **T** (`temperature`) chooses one positive temperature on a fixed grid around Ts. Dividing both class scores by the same positive number cannot change which class is larger, so predicted classes stay the same, but the confidence used to accept or defer can change.
- **H** (`fit_head`) refits the 2 × 256 head weights and the biases, regularized towards the source head.

Everything else stays frozen: `audit_core.state_change` stops the run if any other state field changes.

## 4. Prediction, seal and scoring

Each instance predicts Q (`predict_core`), and its prediction file is saved before label access ends. After all 54, `audit_core.Cohort.finish` writes a seal over the saved states and predictions; only then does `DataService.scoring_labels` re-check the seal and return the Q labels. This boundary is enforced by program interfaces within one process, and the trusted loader had already read the complete files, including all labels: it is not operating-system isolation. Preprocessing used completed offline buffers, not causal streaming, and the public data had been analysed before, so this is not a fresh blind test.

## 5. From counts to J and C

`scorer.py` (`score`) accepts a trial when |logit difference| / T ≥ ln 3, which equals a top-class probability of at least 0.75; otherwise it defers. Invalid trials count as deferrals.

- J = (accepted wrong + 0.25 × deferred) / Q-size
- C = accepted / Q-size

To illustrate the arithmetic only: one stored row of `instance_metrics` in [`primary_results.json`](../results/primary_results.json) (participant 6, seed 1103, T) has Q-size 120, 73 accepted (11 wrong) and 47 deferred, so J = (11 + 0.25 × 47) / 120 ≈ 0.190 and C = 73 / 120 ≈ 0.608. These are existing counts, not a new result.

`scorer.aggregate` averages the three seeds within each person and then weights the nine people equally, so n = 9, not 54. `frozen/inference_contract.py` (`hp1`), with `runtime_modules/statistics_recipe.py`, gives the t intervals and decisions; `independent_statistics.py` recomputes them separately.

## 6. Three questions kept apart

- **Non-inferiority** (a numerical criterion): the upper bound of the T − H difference in J is below 0.02. Met.
- **Equivalence**: not tested.
- **Usefulness**: J ≤ 0.20 and C ≥ 0.50 in at least 7 of 9 people, plus group bounds. Not established for either method, which is not the same as refuted.

The saved results therefore do not support T substituting for H. Exact values are in the [results](../results/README.md).
