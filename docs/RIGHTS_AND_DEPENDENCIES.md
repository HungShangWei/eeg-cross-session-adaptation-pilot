# Rights and dependencies

This page states which terms apply to which files. It is a description, not legal advice.

## Licences chosen by the author

All three licence files below contain the same standard MIT License text, `Copyright (c) 2026 Shang-Wei Hung`. MIT permits use, copying, modification, distribution, sublicensing and sale, provided the copyright and permission notice is kept.

- **[`code/LICENSE`](../code/LICENSE)** is carried over unchanged from an earlier public snapshot of this project, where it was included for seven source modules published on 2026-10-21. Four of those modules correspond to `code/pilot/candidate/frozen/contracts.py`, `frozen/inference_contract.py`, `frozen/inference_audit.py` and `frozen/statistics_recipe.py`: two are byte-identical to them, and in this release copy the other two differ only by neutral renames (file and module names and a docstring label). Those four files continue under that existing licence.
- **[Executed-code MIT License](../code/pilot/LICENSE)**: on 2026-10-27 the copyright holder chose to release under the MIT License all software, configuration files and the accompanying README in this code folder (`code/pilot/` in this release copy), to the extent the copyright holder has the right to license them. This covers the whole `code/pilot/candidate/` tree, not only the four files above.
- **[`scripts/LICENSE`](../scripts/LICENSE)**: in a separate choice on the same date, the two display scripts `scripts/make_result_tables.py` and `scripts/plot_participant_results.py` are also released under the MIT License.

These choices do not transfer copyright, and they do not cover any other or future work of the author. The release tooling added after 2026-10-27 (`tools/` and `code/pilot/RELEASE_CODE_IDENTITY.json`) is not covered by these licence choices, and no licence is granted for it here.

**Not covered by these licences.** The MIT choices above do not apply to every kind of content in this repository. No licence is selected here for the root and `docs/` documentation, the result files and figure under `results/`, the bootstrap index matrix under `protocol/`, the data and environment notes, or the `.gitignore`; any rights that otherwise apply to them are unaffected. Third-party packages, the EEG dataset and other source materials keep their own terms, and nothing here relicenses them. The configuration files in `code/pilot/candidate/config/` refer to dataset files by name and hash; the dataset itself is not included and is not relicensed.

Nothing in this repository extends a software licence to the EEG dataset.

## Dataset

The recordings (BCI Competition IV dataset 2b, BNCI Horizon 2020 entry 004-2014) are **not included**. The source page states CC BY-ND 4.0 terms with Graz University of Technology as licensor. This repository publishes only aggregate statistics computed from the recordings and a matrix of participant indices; it does not redistribute the recordings or any modified version of them. See [data/README.md](../data/README.md) and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Dependencies

No dependency source code or binary is bundled. The code imports NumPy, SciPy, PyTorch, scikit-learn and pyRiemann, plus the Python standard library. The optional figure script imports Matplotlib. Versions of the original run environment are pinned in [environment/](../environment/); licence identifiers are listed in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Installing these versions was not tested for this showcase.

## What is deliberately not published

Raw EEG and MAT files, per-trial labels, per-trial predictions, model states and weights, the run's full event ledgers (they contain label values), the seal file, the local approval record, internal planning and review documents, and any personal correspondence. The `.gitignore` file is a convenience only. It cannot remove anything from Git history or authorize sharing a file.
