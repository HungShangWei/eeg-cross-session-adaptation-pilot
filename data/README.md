# Data: source, files used, and redistribution boundary

The pilot uses left- versus right-hand motor-imagery EEG from **BCI Competition IV dataset 2b** (also described as *BCI Competition 2008 – Graz data set B*), nine participants. The source page lists three EEG and three EOG channels per recording.

**No recording is included in this repository.** Obtain the files yourself from the official source and follow its terms.

## Where the files come from

The pilot read the MAT-format release on the BNCI Horizon 2020 database, entry **"4. Two class motor imagery (004-2014)"** at <https://bnci-horizon-2020.eu/database/data-sets>. When read on 2026-10-27, that page listed the files `B01T.mat`, `B01E.mat`, …, `B09T.mat`, `B09E.mat`, stated that the set was originally released as data set 2b of BCI Competition IV, and gave the licence as *Creative Commons Attribution No Derivatives 4.0 (CC BY-ND 4.0)* with the Institute for Knowledge Discovery, Graz University of Technology, as licensor. Check the page for the current terms before use.

The BCI Competition IV download area (<https://bbci.de/competition/iv/download/>) distributes the same competition data as GDF files. **The pilot did not use the GDF release**, and the file names and hashes below refer to the BNCI MAT files only.

Reference: R. Leeb, C. Brunner, G. R. Müller-Putz, A. Schlögl, G. Pfurtscheller. *BCI Competition 2008 – Graz data set B.* Official technical description, 2008. <https://www.bbci.de/competition/iv/desc_2b.pdf>

## Files and sessions used

Each MAT container holds several recording sessions as separate groups. The pilot used one group per container: **physical session 3** is group index 2 of `B0xT.mat`, and **physical session 4** is group index 0 of `B0xE.mat`. The mapping, expected sizes and SHA-256 values below are copied from the run's [data manifest](../code/pilot/candidate/config/DATA_MANIFEST_v1.json) (`DATA_MANIFEST_v1.json`; local paths replaced by `<PROJECT_ROOT>`). They record the files as previously identified in the author's local copy. They were not re-hashed for this showcase, and whether a fresh download today has identical bytes has not been checked.

| Participant | Physical session | File | Group index | Trials in group | Expected bytes | Expected SHA-256 |
|---:|---:|---|---:|---:|---:|---|
| 1 | 3 | B01T.mat | 2 | 160 | 34203437 | `0da6e77ab0dab5b4aa1d2d5a6a542ac02f6768d3b7a76b0abe896ec1cf259919` |
| 1 | 4 | B01E.mat | 0 | 160 | 18595217 | `5effd365ae3733402286f2eea6b1ce482680a9f9ffc55c0b41bc63061a0161b5` |
| 2 | 3 | B02T.mat | 2 | 160 | 33060824 | `1c4ace3eee8d72ca184fa6995a9466939b71175b8b3a129bdaa838a85adf6473` |
| 2 | 4 | B02E.mat | 0 | 120 | 16538614 | `f057ada16e36e7d58e5670b705ab41aec1175afde0a1e1e0b96cae58dbc7a083` |
| 3 | 3 | B03T.mat | 2 | 160 | 35581243 | `4ae1b23b4b4359151787a1a61d3acea128719677c49bfaf0113748cffece3b98` |
| 3 | 4 | B03E.mat | 0 | 160 | 19310824 | `6fca9dd9cbbdbb53dd8fb2798feed8e22669a91d1259fdac6695855756181353` |
| 4 | 3 | B04T.mat | 2 | 160 | 35749247 | `e7230d6d28a9e81d3afdf7ba5d363979e0186dbbc5a73f66d4b713be020ce960` |
| 4 | 4 | B04E.mat | 0 | 160 | 17900104 | `a08bbc7efb12a29b9ac901c810a42f84053a268b567c0c5c705d401038c6d7f6` |
| 5 | 3 | B05T.mat | 2 | 160 | 35047531 | `53166e2cf1a97576262b3f2f27395f489af6fda15ade5c3b3cdd2c89f7df0d79` |
| 5 | 4 | B05E.mat | 0 | 160 | 17493104 | `a395a547e62241f6bf69b1b42828d394f997189271ebd90d5ff4dde4e4e9e757` |
| 6 | 3 | B06T.mat | 2 | 160 | 36512412 | `d69f679ea33121a9202901d5b62efb50f8ed004fa8ad70d10a59351493ffdad8` |
| 6 | 4 | B06E.mat | 0 | 160 | 19381269 | `c13d76a3bcd6fd445482e3268d38ebd51f28ea286869fc22c47c6d39857b2f2f` |
| 7 | 3 | B07T.mat | 2 | 160 | 33061422 | `0b79522d66710a88f852b83802c7bffd015226d765480f60f16b6bedc5ea33c2` |
| 7 | 4 | B07E.mat | 0 | 160 | 17883151 | `29900042a1adee5f722410f8e52e46961f356b68d5a7906df05df04319fde2f1` |
| 8 | 3 | B08T.mat | 2 | 160 | 38046816 | `d96bdfd0c8331f238740c10ff03121dc3e3a20a4b1254840c5cc4878aa149b67` |
| 8 | 4 | B08E.mat | 0 | 160 | 18959016 | `d616cd7f843e899fb01cd1fa86a2a8dd0fd2f2e4db94ab3a09e6b9f8d5a6399a` |
| 9 | 3 | B09T.mat | 2 | 160 | 33324824 | `4f017991a64ceabb2ca73abf6f3c620b2b8fd7468184f52a8444dfdec1ee2adc` |
| 9 | 4 | B09E.mat | 0 | 160 | 17332216 | `99f3937393a3c4982beda69850cf3c6cde98dd33e1733a9d67a787e10f407bfd` |

Participant 2's session-4 group has 120 trials, so its evaluation segment (trial index 40 onward) has 80 trials; every other participant has 120 evaluation trials.

## Redistribution boundary

This repository does not contain the recordings, any modified copy of them, per-trial labels, per-trial predictions, or model weights. It contains aggregate statistics computed from the recordings (see [results/](../results/README.md)) and one fixed bootstrap matrix of participant indices (0–8) that contains no signal or label values ([protocol/README.md](../protocol/README.md)). Public availability of a dataset does not by itself grant permission to redistribute it; this note is a description of what was done, not legal advice.
