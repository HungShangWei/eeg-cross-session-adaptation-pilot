# Third-party notices

This repository bundles **no** third-party source code, binaries, datasets or model weights. The items below are used by, or cited in, the pilot and keep their own terms when you obtain them. Licence identifiers for the Python packages were read from the installed package metadata of the original run environment on 2026-10-27; consult each project for authoritative terms. This file is informational, not legal advice.

## Dataset (not redistributed)

| Item | Source | Terms as stated by the source |
|---|---|---|
| BCI Competition IV dataset 2b (BNCI Horizon 2020 entry 004-2014, files `B01T.mat` … `B09E.mat`) | <https://bnci-horizon-2020.eu/database/data-sets> | Creative Commons Attribution No Derivatives 4.0 (CC BY-ND 4.0); licensor: Institute for Knowledge Discovery, Graz University of Technology (page read 2026-10-27) |

Please cite the dataset description: R. Leeb, C. Brunner, G. R. Müller-Putz, A. Schlögl, G. Pfurtscheller, *BCI Competition 2008 – Graz data set B*, 2008. See [data/README.md](data/README.md) for the files and sessions used.

## Python packages (not bundled)

| Package | Version in original run environment | Role | Licence (package metadata) |
|---|---|---|---|
| NumPy | 2.5.3 | arrays, statistics | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| SciPy | 1.18.1 | MAT loading, filtering, optimisation, t distribution | BSD licence (OSI classifier) |
| PyTorch | 2.14.1 | neural decoder training and inference | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT |
| pyRiemann | 0.12 | Riemannian mean in the alignment code (`frozen/ea_recipe.py`), which is outside the reported T/H path; listed because the launcher pins its version | BSD (3-clause) |
| scikit-learn | 1.9.1 | OAS covariance estimator in the same alignment code (outside the T/H path); version pinned by the launcher | BSD-3-Clause |
| Matplotlib | 3.11.2 | the optional results figure only (installed in the original run environment as a dependency) | Matplotlib licence (PSF-based) |

Exact pins: [environment/](environment/). Transitive dependencies are listed in [environment/venv-freeze-2026-10-27.txt](environment/venv-freeze-2026-10-27.txt).

## Methods cited

The code implements published methods; these citations are attributions, not licences.

- EEGNet architecture (the source decoder is an EEGNet-style network implemented in this repository): V. J. Lawhern, A. J. Solon, N. R. Waytowich, S. M. Gordon, C. P. Hung, B. J. Lance, "EEGNet: a compact convolutional neural network for EEG-based brain–computer interfaces", Journal of Neural Engineering 15(5):056013, 2018.
- Temperature scaling: C. Guo, G. Pleiss, Y. Sun, K. Q. Weinberger, "On Calibration of Modern Neural Networks", ICML 2017.
- Accept/reject (deferral) threshold: C. K. Chow, "On optimum recognition error and reject tradeoff", IEEE Transactions on Information Theory 16(1), 1970.

The author's MIT licence for `code/pilot/` and `scripts/` does not relicense any item listed here. See [docs/RIGHTS_AND_DEPENDENCIES.md](docs/RIGHTS_AND_DEPENDENCIES.md) for which licence covers which files in this repository.
