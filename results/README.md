# Results: group estimates, participant-level results, decision criteria

All numbers on this page come from one file, [`primary_results.json`](primary_results.json), a public projection of the scoring output of the reported execution on 2026-10-27. It differs from the saved output only in the run identifier field, which holds a public alias, and in a `public_projection` note that records the change and the original file's size and SHA-256 (16937 bytes, `55fdcec96d44fd73411f7c23b183cad7799a5fb5bbbd125cce8dc7224dde3152`). The projection is 17363 bytes, SHA-256 `3f8f341d4fb638a994e8a9a33af9767934fdc48a01e24a8bdd3020036d259184`; the saved original is kept privately by the author. The file holds aggregate counts and statistics only: no EEG, labels or per-trial predictions.

The tables below and the CSV files beside them are deterministic projections of that file made by [`scripts/make_result_tables.py`](../scripts/make_result_tables.py). Nothing was re-estimated. The CSV files keep the saved full precision, and the tables here round for reading.

## Definitions

- **T**: temperature recalibration. **H**: regularized classification-head update. Both used 10 permitted labels (budget d10).
- **Acceptance rule**: accept a prediction if its top-class probability is ≥ 0.75, otherwise defer.
- **Decision loss J** = (accepted errors + 0.25 × deferrals) / number of evaluation trials. Technically invalid outputs count as deferrals and stay in the denominator. Lower is better.
- **Coverage C** = accepted predictions / number of evaluation trials. Higher is better.
- **Aggregation**: for each participant, the three seeds are averaged with equal weight; then the nine participants are weighted equally. This averages scores, not probabilities (it is not an ensemble). The independent unit is the participant (n = 9).
- **Intervals**: ordinary two-sided 95% t intervals with 8 degrees of freedom, computed in the run from the nine participant values.

## Group estimates

<!-- BEGIN GENERATED: group_table -->
| Quantity | Mean | 95% t interval (df = 8) | Pre-specified criterion | Met |
|---|---:|---:|---|---|
| T decision loss J | 0.1838 | [0.1069, 0.2608] | group upper bound < 0.20 | **no** |
| T coverage C | 0.5764 | [0.3240, 0.8288] | group lower bound > 0.50 | **no** |
| H decision loss J | 0.1845 | [0.1063, 0.2628] | group upper bound < 0.20 | **no** |
| H coverage C | 0.5995 | [0.3513, 0.8478] | group lower bound > 0.50 | **no** |
| T − H difference in J | −0.00069 | [−0.00522, 0.00383] | non-inferiority: upper bound < 0.02 | yes |
| Participants meeting J ≤ 0.20 and C ≥ 0.50 (T / H) | 5 / 5 of 9 | — | at least 7 of 9 | **no** / **no** |
<!-- END GENERATED: group_table -->

Full precision: [`group_estimates.csv`](group_estimates.csv). For example, the T − H difference in J is −0.000694444444444447 with interval [−0.00522386433735302, 0.0038349754484641252] (`/primary/delta`).

The file stores group means in two places, `/primary/...` (used with the intervals) and `/summary/group/...`; they differ only in the last floating-point digits (for example 0.1838348765432099 and 0.18383487654320987 for T's J). Both are kept in the CSV, and neither was overwritten.

## Saved T − H comparison

![Saved T minus H decision-loss difference, ordinary two-sided 95% t interval, zero and the 0.02 non-inferiority margin](figures/loss_difference.png)

Saved values from the reported execution, displayed without a new analysis: T − H in decision loss J, with the ordinary two-sided 95% t interval (nine participants; three seeds averaged within each person). The numerical non-inferiority criterion was met; equivalence was not tested and usefulness criteria were not met. The point and interval come directly from `/primary/delta/mean` and `/primary/delta/two_sided95`; the 0.02 margin is `/NI_margin` in the frozen run configuration. Negative T − H values indicate lower proxy loss for T.

## Participant-level results

Participant numbers are the dataset's anonymous identifiers (B01–B09). Each value is that participant's mean over three seeds.

<!-- BEGIN GENERATED: participant_table -->
| Participant | Evaluation trials (Q) | T: J | H: J | T − H: J | T: C | H: C | T meets J ≤ 0.20 & C ≥ 0.50 | H meets J ≤ 0.20 & C ≥ 0.50 |
|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|
| 1 | 120 | 0.3312 | 0.3312 | 0.0000 | 0.3972 | 0.5083 | no | no |
| 2 | 80 | 0.2969 | 0.3052 | −0.0083 | 0.1625 | 0.1958 | no | no |
| 3 | 120 | 0.2486 | 0.2507 | −0.0021 | 0.0056 | 0.0083 | no | no |
| 4 | 120 | 0.0160 | 0.0167 | −0.0007 | 0.9806 | 0.9778 | yes | yes |
| 5 | 120 | 0.1382 | 0.1375 | 0.0007 | 0.8361 | 0.8833 | yes | yes |
| 6 | 120 | 0.2056 | 0.2146 | −0.0090 | 0.5667 | 0.5639 | no | no |
| 7 | 120 | 0.1958 | 0.1847 | 0.0111 | 0.7500 | 0.7500 | yes | yes |
| 8 | 120 | 0.1083 | 0.1069 | 0.0014 | 0.8333 | 0.8500 | yes | yes |
| 9 | 120 | 0.1139 | 0.1132 | 0.0007 | 0.6556 | 0.6583 | yes | yes |
<!-- END GENERATED: participant_table -->

Full precision: [`participant_results.csv`](participant_results.csv), taken directly from `/summary/participants`. The evaluation-trial count comes from `/instance_metrics` (the same for all six instances of a participant). The "meets" columns apply the fixed individual rule to the saved values; their totals (5 and 5) equal the saved counts `/primary/T_usefulness/participant_guard` and `/primary/H_usefulness/participant_guard`, which the script checks.

![Participant-level decision loss and coverage for T and H with the individual thresholds](figures/participant_results.png)

The participant figure ([`scripts/plot_participant_results.py`](../scripts/plot_participant_results.py)) plots the same nine rows. It is a display of saved values, not an additional analysis. The stacked panels use larger labels for narrow displays. Extra space beyond the scale endpoints prevents marker clipping (including participant 3 near zero coverage); it does not represent negative coverage. T/H values, horizontal method offsets and the shaded participants are unchanged.

## Decision criteria and how the conclusion follows

| Requirement (fixed before the run) | T | H |
|---|---|---|
| Individual: J ≤ 0.20 and C ≥ 0.50 in at least 7 of 9 participants | 5 of 9: not met | 5 of 9: not met |
| Group: upper bound of J < 0.20 | 0.2608: not met | 0.2628: not met |
| Group: lower bound of C > 0.50 | 0.3240: not met | 0.3513: not met |
| Active fit: at least 2 of 3 seeds with a completed, non-fallback fit in at least 6 of 9 participants (the fitted value may equal the source value) | 9 of 9: met | 9 of 9: met |
| Non-inferiority of T to H: upper bound of T − H J difference < 0.02 | 0.0038: met | — |

- **Non-inferiority (numerical criterion)**: met (`/primary/NI` = `ESTABLISHED`). Equivalence was not tested, and this is not a superiority result.
- **Usefulness of T**: not established (`/primary/T_usefulness/established` = false; reasons `J_bound_failed`, `C_bound_failed`, `7_of_9_failed`). Not established does not mean refuted.
- **H as a useful fitted reference**: not qualified (`/primary/H_useful_fitted_reference` = false). This is reported alongside the result; it is not a fourth success condition.
- **Overall**: the composite hypothesis that T can substitute for H (non-inferior and useful) is not supported. Saved composite label: `NI_T_USEFUL_NOT_ESTABLISHED__T0_H0_A1`. The suffix encodes T usefulness established = 0, H usefulness established = 0, T active-fit guard met = 1. It is unrelated to the provisional temperature called T0 in the methods.
- **Robustness**: a percentile bootstrap over the fixed participant-resample matrix ([protocol/](../protocol/README.md)) could only downgrade the conclusion; its status is `no_bootstrap_upgrade`. Its saved intervals are listed in [`decision_criteria.csv`](decision_criteria.csv) and are a different interval type from the t intervals above.

All rows, with their JSON pointers: [`decision_criteria.csv`](decision_criteria.csv).

## What the 54 instance rows are

`/instance_metrics` holds 54 rows (9 participants × 3 seeds × 2 methods) with accepted, accepted-wrong and deferred counts, the evaluation denominator, and per-instance J and C. They show where the participant means come from; they are not 54 independent observations. Ninety distinct session-4 trials supplied labels (10 per participant), and the 540 method-instance label receptions (54 × 10) re-use those trials; neither count increases the sample size.

`/independent_primary_check` holds a second implementation of the same statistics computed by the run from the same saved values; it agrees with `/primary` within the run's stated tolerances.

## How to regenerate or verify

```bash
python scripts/make_result_tables.py           # rewrite the three CSV files, print the Markdown tables
python scripts/make_result_tables.py --check   # verify CSV files and the tables embedded in README.md and here
```

Both commands need only the Python standard library and refuse to run if `primary_results.json` does not have the pinned SHA-256. The two figures need Matplotlib; the same plotting command produces both PNG files. See [docs/REPRODUCIBILITY.md](../docs/REPRODUCIBILITY.md) for the other reproduction levels.

To draw both figures from the pinned saved JSON and frozen configuration (no research modules are imported):

```bash
python scripts/plot_participant_results.py
```

Outputs: `figures/participant_results.png` and `figures/loss_difference.png`.
