# Protocol supporting artifact: fixed bootstrap resample indices

`participant_resamples.npy` is the fixed participant-resampling matrix that the reported execution used for its percentile-bootstrap robustness check (the run configuration names it under `bootstrap`). It was created before that execution and was reused unchanged; the executed statistics code refuses to generate a new matrix.

| Property | Value |
|---|---|
| Format | NumPy `.npy`, format version 1.0, no pickled objects |
| dtype / shape | `int64`, 10000 × 9 (C order) |
| Values | participant positions 0–8 only; no EEG, label, prediction or weight values |
| Bytes | 720128 |
| SHA-256 | `877f8ecdebb5af1206404f9bea1a7a7281cad335ca113c71fc87edaceebe08b6` |

Each row is one bootstrap draw of nine participant positions with replacement. The bootstrap result can only downgrade the primary conclusion (`robustness_status`), never upgrade it; the saved intervals are listed in [results/decision_criteria.csv](../results/decision_criteria.csv).

Load it with `numpy.load("protocol/participant_resamples.npy", allow_pickle=False)`. Its identity matches the size and hash pinned in the [run configuration](../code/pilot/candidate/config/RUN_CONFIG_v1.json) (`RUN_CONFIG_v1.json`). The original file was copied unchanged and checked by its size, schema, value range and hash. A separately regenerated in-memory index matrix was compared only for identity; it was neither saved nor applied to any results.
