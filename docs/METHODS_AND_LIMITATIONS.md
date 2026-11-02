# Methods and limitations

This document describes the reported execution (2026-10-27) as implemented in the [code folder](../code/pilot/candidate/) (a release copy with neutral names) and recorded in its saved outputs. File references point to that directory. At run time the launcher puts `runtime_modules/`, then `frozen/`, then the candidate root on the import path. Where a module exists in both `runtime_modules/` and `frozen/`, the `runtime_modules/` copy is the one that ran ([code map](CODE_AND_EVIDENCE_MAP.md)). A shorter guided path through the same steps is in the [method walkthrough](METHOD_WALKTHROUGH.md).

## 1. Question and design

For each of nine people, a decoder trained on one recording session is reused in a later session. With only ten labelled trials from the new session, is recalibrating the decoder's confidence (**T**) non-inferior to updating its classification head (**H**), that is, not worse by more than 0.02 in decision loss? Are T's selective decisions also useful by fixed criteria, so that T could substitute for H? The comparison is offline, on a public dataset, with a protocol and thresholds fixed before this execution (§9).

## 2. Data and partitions

- **Recordings.** BCI Competition IV dataset 2b, in its BNCI Horizon 2020 MAT release ([data/README.md](../data/README.md)). Each recording has three EEG and three EOG channels at 250 Hz. Classes are left hand and right hand. For each participant, physical session 3 (group 2 of `B0xT.mat`) is the *source* session and physical session 4 (group 0 of `B0xE.mat`) is the *target* session. Before loading, each file's size and SHA-256 must match the manifest (`data_service.py`).
- **Trials.** Each trial is epoched from its cue (trial start + 3.0 s): 4.5 s of signal after the cue. Source sessions have 160 trials. Target sessions have 160 trials, except participant 2 with 120.
- **Source partitions** (trial positions in session 3, `frozen/science_contract.py`): S-fit 0–79 (training), D0 80–99, D1 100–119 (only its first 10 labels are used), D2 120–139, S-cal 140–159.
- **Target partitions** (session 4): the prefix P is positions 0–39, and the evaluation segment Q is position 40 to the end (120 trials, or 80 for participant 2). The adaptation labels come only from positions 0–9 of P. Positions 10–39 are never released to any method; the 40-trial prefix only fixes where Q starts.
- **Invalid trials.** A trial whose epoch is out of bounds, non-finite, or has zero energy after preprocessing is marked invalid. It is not replaced by a later trial ("no refill"). An invalid Q trial counts as a deferral (§7).

## 3. Preprocessing (fitted on the source training partition only)

Each epoch is processed inside its own completed buffer (`frozen/signal_recipe.py`):

1. remove each channel's mean; apply a 4th-order Butterworth band-pass filter, 8–32 Hz, forward and backward (zero-phase `sosfiltfilt`); remove the mean again;
2. regress the three EOG channels out of the three EEG channels, using ridge-regularized weights fitted on 2-s pre-cue windows of the S-fit trials only;
3. resample 250 → 128 Hz and keep 0.5–4.5 s after the cue (3 channels × 512 samples); remove each channel's mean;
4. standardize each channel with the mean and standard deviation of the transformed S-fit epochs.

The fitted transform is then frozen and applied unchanged to every other partition, including the target prefix and Q. Nothing is fitted on target-session data. Because filtering runs forward and backward over a completed epoch, this is an offline transform, not causal streaming.

## 4. Source decoder

- **Network** (`frozen/neural_recipe.py`): a compact EEGNet-style convolutional network (temporal convolution with 8 filters of length 64; depthwise spatial convolution over the 3 channels, giving 16 maps; separable convolution; batch normalization, ELU, average pooling, dropout 0.5) producing 256 features, followed by a linear head with 2 outputs. Training is deterministic, single-threaded, on CPU.
- **Seeds.** Three seed bases (1103, 2207, 3301), with effective seed 10000 × participant + base.
- **Training** (`runtime_modules/source_recipe_e3prep.py`): S-fit only, 100 epochs, mini-batches of 32, AdamW (learning rate 0.001, weight decay 0.0001), cross-entropy loss.
- **Checkpoint choice.** At epochs 25, 50 and 100, batch-normalization statistics are recomputed over S-fit, and the checkpoint with the lowest mean D2 negative log-likelihood across the three seeds is kept (earliest on ties). One checkpoint is chosen per participant. Nothing is refitted afterwards.

## 5. Settings fixed on the source session, before any target labels reached the methods

Each method has a small, predeclared grid of settings, chosen on source data only (`frozen/source_selection.py`). The trusted data service had already loaded the target-session files at qualification (§7), but no target data were released to any method at this stage:

- a provisional temperature T0 is fitted on D0;
- **T settings**: search range factor R ∈ {2, 4} and penalty ∈ {0.1, 1.0}. Each candidate fits a temperature on the 10 labelled D1 trials, starting from T0, and is scored by D2 negative log-likelihood;
- **H settings**: regularization λ ∈ {0.01, 0.1, 1.0}. Each candidate refits the head on the same 10 D1 trials and is scored on D2;
- scores are averaged over the three seeds, with fixed tie rules (T: stronger penalty, then smaller R; H: larger λ). One choice per method and participant is **frozen** (recorded with the seed states);
- only after that freeze is S-cal released. It is used once, to fit the source temperature Ts of each seed.

The source state carried into session 4 is the chosen checkpoint, its head (W, b) and Ts.

## 6. Target updates (54 instances)

One instance is a participant × seed × method (9 × 3 × 2 = 54). Each instance starts from a copy of its source state and receives the labelled trials among positions 0–9 of the session-4 prefix (`runtime_modules/composition.py`, `frozen/solvers_recipe.py`).

- **T: temperature recalibration.** It fits one temperature T = Ts · e^u over a 401-point grid with T ∈ [Ts/R, Ts·R], minimizing the negative log-likelihood of the 10 labelled trials plus penalty · u². Only the temperature changes.
- **H: regularized classification-head update.** It refits the 2 × 256 head weights and 2 biases with L-BFGS-B, minimizing the negative log-likelihood (at the source temperature Ts) plus λ/2 times the squared distance from the source head. Only the head changes.
- **Frozen parts.** The encoder, batch normalization, preprocessing and source choices are frozen for both methods. After each update, the program compares state fingerprints before and after: T may change only `temperature` (and its status), H only `head_W`, `head_b` (and status). Any other change stops the run.
- **Fallbacks.** If the labelled set is not eligible (fewer than 4 trials, or a single class), or the solver fails, the method keeps its source values and reports a fallback status. The protocol's "active fit" guard (§8) counts only completed, non-fallback fits.
- **What happened in the reported execution.** In all 54 instances, all ten positions 0–9 were valid, so each update received exactly 10 trial–label pairs; the no-refill rule was never triggered. All 54 instances completed without fallback. H changed its head in all 27 instances. T changed its temperature in 22 of 27 instances; in the other 5, the fitted temperature equalled the source temperature, so only the status field changed.

## 7. Feedback access, sealing and scoring

**Feedback (label) access.** Labels reach an update method only through one recorded path (`audit_core.py`, `data_service.py`, `account.py`). For each instance, the run records:

1. a request for positions 0–9 of session 4 (one request per instance; repeats are refused);
2. the trusted data service's reply: which positions were valid, their labels, the session-4 file hash, the trial onsets, and a fingerprint of the exact view;
3. receipt of that reply, bound to the recipient instance and call;
4. each use of the labels during the update, with its purpose (`schema_validation`, `class_gate`, `optimizer`). Each use is checked against the receipted labels' fingerprint;
5. the end of access for that instance, after its Q predictions are saved. After that, further use is refused.

The Q view given to a method carries no labels. Prediction refuses to run if any are present.

**Predictions and seal.** For each instance, the adapted state and the Q predictions (the logit difference of each trial and the temperature) are saved. After all 54 instances, the program re-verifies every saved state and prediction file. It then writes a **seal**: a canonical-JSON SHA-256 over the code identity, the event-ledger head and the 54 rows.

**Scoring.** Only after the seal does the scoring interface obtain the Q labels. The data service first re-checks the seal and the files. A trial is accepted when |logit difference| / T ≥ ln 3, which for two classes equals a top-class probability of at least 0.75; otherwise it is deferred. Per instance:

- **decision loss** J = (accepted errors + 0.25 × deferrals) / Q-size;
- **coverage** C = accepted / Q-size.

Invalid trials count as deferrals and stay in the denominator. The 0.75 threshold is Chow's cost-optimal rule for unit error cost and deferral cost 0.25 *when true class probabilities are known*. Here the probabilities are model estimates, and J and C are proxies, not measurements of human burden or harm.

**What this boundary is.** The trusted data service loaded each participant's complete MAT containers, including all labels, at the start of the run, inside the same Python process. The restrictions above are enforced by program interfaces and recorded in a hash-chained event ledger. An audit hook also blocks file writes outside the run directory and network access. These are program-level controls and records, not operating-system isolation. They support restricted label access *by the update methods*, not a claim that no component held evaluation labels before sealing.

## 8. Aggregation and decision criteria

- **Aggregation** (`scorer.py`): for each participant and method, J and C are averaged over the three seeds; the nine participants are then weighted equally. This averages scores, not probabilities. n = 9.
- **Intervals** (`runtime_modules/statistics_recipe.py`): ordinary two-sided 95% t intervals with df = 8 over the nine participant values, for T's and H's J and C and for the T − H difference in J.
- **Non-inferiority** of T to H: upper bound of the T − H J interval < 0.02.
- **Usefulness** of a method requires all three: J ≤ 0.20 and C ≥ 0.50 in at least 7 of 9 participants; group J upper bound < 0.20; group C lower bound > 0.50.
- **Active fit**: at least 2 of 3 seeds completed without fallback in at least 6 of 9 participants. A completed fit counts even when the fitted value equals the source value.
- **Primary hypothesis (T can substitute for H)**: requires non-inferiority, T usefulness and T active fit. Whether H itself qualifies as a useful fitted reference is reported separately; it is not a fourth condition.
- **Robustness**: a percentile bootstrap over a fixed, pre-existing 10000 × 9 participant-resample matrix ([protocol/](../protocol/README.md)). It can only downgrade the primary conclusion, never upgrade it. The executed code refuses to generate a new matrix.
- **Second implementation**: a separate pure-Python implementation recomputes the inferential outputs from the same participant values; the run required agreement within 1e-10.

Results: [results/README.md](../results/README.md).

## 9. What was fixed before this execution

The study protocol document (not published here; its SHA-256 is recorded in `config/RUN_CONFIG_v1.json`), the run configuration, the data manifest and the exact 45-object code identity were fixed and hash-bound before the run started. The launcher refused to start unless every code file matched that identity and the author's own pre-run sign-off record named it. That record is an administrative step of the author's workflow, not an ethics, institutional or external approval. Thresholds, budgets, seeds, grids and statistics are constants in the code listed above. Being fixed before *this execution* does not mean fixed before any contact with this dataset: the same data had been analysed earlier (see [§10](#10-limitations)).

## 10. Limitations

- **Small and narrow.** Nine people, one public dataset, one session pair (3 → 4), one decoder recipe, one label budget (10), one cost (0.25), two update methods.
- **Not a fresh blind test.** The dataset is public and had been analysed before in this project, in an earlier, broader analysis with additional comparators. That analysis is not part of the results reported here and is not re-certified by this pilot; its earlier status, including its missing and inconclusive parts, is unchanged. The pilot's summary values for the T/H quantities coincide with values saved by that analysis; agreement between two executions of the same deterministic pipeline on the same data is not treated as independent confirmation or as additional samples, and the earlier values were not used in any check (`old_DREC_values_compared` is false in [`primary_results.json`](../results/primary_results.json)). This pilot is a new execution of a fixed pipeline, not an independent replication or a preregistered external study.
- **Offline and non-causal.** Preprocessing used completed epoch buffers with zero-phase filtering. No real-time or causal-streaming claim is made.
- **Program-level label boundary.** See §7. The run records support restricted label access by the update methods. They do not prove the absence of every conceivable side channel, and they are not operating-system isolation.
- **Proxy outcomes.** J and C are artificial decision-cost proxies. They do not measure human effort, setup time, clinical harm, or robot or interaction benefit.
- **No label-saving claim.** Both methods used the same ten labels, so the result does not show that T needs fewer labels or shortens setup.
- **Not tested.** Multimodal sensing, combined motor-imagery and error-potential use, the added value of neural feedback, other budgets or costs, the unchanged, normalization-update and alignment-based comparators of the earlier analysis, and any live human or robot study.
- **Verification depth.** The run's own records and saved-count arithmetic were checked, but the run has not been independently reproduced ([VALIDATION_SCOPE.md](VALIDATION_SCOPE.md)).

## Terms

- **Coverage C**: the share of evaluation trials on which the decoder made a decision instead of deferring.
- **Decision loss J**: the average per-trial cost, where an accepted error costs 1, a deferral costs 0.25 and a correct accepted decision costs 0.
- **Deferral**: declining to decide on a trial (here, top-class probability below 0.75).
- **Non-inferiority**: the new method is not worse than the reference by more than a fixed margin (0.02 in J). It does not mean equivalence or superiority.
- **Seal**: a hash that fixes all 54 sets of predictions and states before any evaluation label is released to scoring.
- **Temperature scaling**: dividing the decoder's output scores by a positive temperature, which changes confidence but not the predicted class.
