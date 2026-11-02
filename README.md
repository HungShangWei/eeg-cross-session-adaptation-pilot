# EEG Cross-Session Selective Adaptation — Pilot

**Shang-Wei Hung · offline pilot on public EEG · executed 27 October 2026**

When an EEG decoder is reused in a new session, a few labelled trials may be available to adapt it. Is it enough to recalibrate the decoder's confidence, or does the classifier itself need updating? And does either update make the decoder's accept-or-defer decisions useful? This repository reports one fixed, offline pilot of that question: its code, configuration, saved results, and the limits of what it shows.

## What was tested

- **Data.** Left- versus right-hand motor-imagery EEG from the nine participants of BCI Competition IV dataset 2b. For each person, a decoder trained on physical session 3 was adapted to physical session 4 ([data/README.md](data/README.md)).
- **Two updates.** **T** rescales the decoder's confidence with a single temperature. **H** refits the regularized classification head. Everything else in the decoder stays frozen.
- **Feedback budget.** Each update received and used the 10 permitted trial–label pairs at the first ten positions of a fixed 40-trial session-4 prefix. Evaluation used the same fixed trials for both methods, from trial index 40 onward. The 40-trial prefix only fixes where evaluation starts; neither method saw 40 labels.
- **Decision rule.** A prediction is accepted when its top-class probability is at least 0.75 and deferred otherwise. **Decision loss J** counts each accepted error as 1 and each deferral as 0.25, averaged over all evaluation trials; technically invalid outputs count as deferrals. **Coverage C** is the accepted share. These are proxy scores, not measures of human burden or harm.
- **Statistical unit.** Nine participants. Each person's three seeds (1103, 2207, 3301) were averaged first, then people were weighted equally. The 54 method instances (9 people × 3 seeds × 2 methods) are not 54 independent samples.

The protocol, thresholds and decision rules were fixed before this execution ([methods and limitations](docs/METHODS_AND_LIMITATIONS.md)).

## Saved results

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

![Saved T minus H decision-loss difference with its ordinary two-sided 95% t interval, zero line and 0.02 non-inferiority margin](results/figures/loss_difference.png)

Saved values from the reported execution, displayed without a new analysis: T − H in decision loss J, with the ordinary two-sided 95% t interval (nine participants; three seeds averaged within each person). The numerical non-inferiority criterion was met; equivalence was not tested and usefulness criteria were not met.

![Participant-level decision loss and coverage for T and H, with the individual thresholds J ≤ 0.20 and C ≥ 0.50; the same five participants meet both thresholds under both methods](results/figures/participant_results.png)

**What this supports.** On the pre-specified numerical criterion, recalibration (T) was non-inferior to the head update (H): the upper end of the interval for the J difference lies well below the 0.02 margin. Equivalence was not tested. The protocol also required usefulness before T could be said to substitute for H: J ≤ 0.20 and C ≥ 0.50 in at least 7 of 9 participants, and group bounds below 0.20 for J and above 0.50 for C. Each method met the individual thresholds in only 5 of 9 participants and missed both group bounds. Usefulness was therefore not established (nor refuted), and substitution was not supported. The head update also failed to qualify as a useful fitted reference. Because both updates used the same ten labels, this pilot does not show that either one saves labels or shortens setup.

Exact values with their source fields, the nine-participant table, and the decision criteria are in [results/README.md](results/README.md).

## What the run records support, and what they do not

The fixed offline pipeline rebuilt the session-3 source models and, for each of the 54 adaptations, recorded the request, receipt and use of its permitted labels, the end of that access, the adapted state and the predictions. All predictions were sealed before the scorer obtained the evaluation labels, and the reported statistics were checked against the saved counts. A trusted data loader had loaded the complete data containers, including all labels, earlier in the same run, so these records support restricted label access *by the update methods* through the program's interfaces, not system-wide or operating-system isolation. Preprocessing used completed offline buffers rather than causal streaming. The public dataset had been analysed earlier in this project, so this is not a fresh blind test; that earlier, broader analysis is not part of these results and is not re-certified by them ([methods §10](docs/METHODS_AND_LIMITATIONS.md#10-limitations)). The run has not been independently reproduced, and the pilot did not test multimodal sensing, the added value of neural feedback, or benefit in a real human–AI interaction ([validation scope](docs/VALIDATION_SCOPE.md)).

## How to read and check

| Page | Contents |
|---|---|
| [Method walkthrough](docs/METHOD_WALKTHROUGH.md) | Short guided path from the data split to J and C, with code locations |
| [Methods and limitations](docs/METHODS_AND_LIMITATIONS.md) | Data split, source models, T/H updates, feedback and sealing rules, metrics, aggregation, limitations |
| [Results](results/README.md) | Saved `primary_results.json`, group and participant tables (CSV), decision criteria, figures |
| [Code and evidence map](docs/CODE_AND_EVIDENCE_MAP.md) | The executed code (folder `candidate/`) by role, which files differ from the executed ones, and where each claim is supported |
| [Reproducibility](docs/REPRODUCIBILITY.md) | Saved results → tables and figures (checked); fitted states → predictions (not provided); raw data → full re-run (public copy not run) |
| [Validation scope](docs/VALIDATION_SCOPE.md) | What was checked, by whom, and what has not been independently reproduced |
| [Data](data/README.md) | Where to obtain the dataset and which files and sessions were used |
| [Third-party notices](THIRD_PARTY_NOTICES.md), [rights and dependencies](docs/RIGHTS_AND_DEPENDENCIES.md) | Licence scope, dependencies, dataset terms |

To check the tables against the saved results, and the code files against their release manifest (standard-library Python only; the manifest records file identity, not an approval to run):

```bash
python scripts/make_result_tables.py --check
python tools/code_identity.py verify --candidate code/pilot/candidate --manifest code/pilot/RELEASE_CODE_IDENTITY.json
```

No raw EEG, labels, trial-level predictions or model weights are included. This release copy has neutral names; saved values are unchanged; the executed originals are kept privately ([code map](docs/CODE_AND_EVIDENCE_MAP.md#how-this-release-copy-relates-to-the-executed-files)).

## My contribution

I framed the research question, selected the comparisons, coordinated execution, and reviewed the results; AI tools assisted with code integration and debugging. The record checks described in [docs/VALIDATION_SCOPE.md](docs/VALIDATION_SCOPE.md) were also AI-assisted, as was the preparation of this public copy (documentation, renaming, comment corrections and display checks).

**Licence.** The code in the [pilot code folder](code/pilot/) and the two scripts in `scripts/` are released under the MIT License ([code licence](code/pilot/LICENSE), [scripts licence](scripts/LICENSE)). This does not cover every file in the repository; the dataset and third-party packages keep their own terms. See [docs/RIGHTS_AND_DEPENDENCIES.md](docs/RIGHTS_AND_DEPENDENCIES.md).
