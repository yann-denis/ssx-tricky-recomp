# EU region support

This branch adds support for the **SSX Tricky (Europe) (En,Fr,De)** retail
XBE alongside the US release, as a first step toward upstream multi-region
support.

## Bring your own dump

The pipeline is region-aware but still requires you to supply your own
retail disc image (no game data is distributed here):

```sh
python3 scripts/pipeline.py extract --iso "SSX Tricky (Europe) (En,Fr,De).iso"
python3 scripts/pipeline.py analyze
cmake --preset linux-release && cmake --build --preset linux-release
ctest --preset linux-release
```

`scripts/pipeline.py` identifies the region from the SHA-256 of
`game/default.xbe` (US `0128bbf6…`, EU `2b69b736…`) and automatically
selects the region-specific seed, manual-function, verified-range and
anchor files (`scripts/*.<region>.json`).

## What differs on EU

- **Data layout.** EU `.data` globals sit `0x5328` bytes above the audited
  US addresses. The runtime shifts the audited data addresses through the
  `SSX_DATA_VA_DELTA` environment variable (`0x5328` for EU, `0` for US);
  `scripts/play-linux.py` sets it automatically from the image digest.
- **Language.** Force the EU language table with
  `SSX_EEPROM_LANGUAGE=4` when launching the emulator headless.
- **Function identities.** EU code addresses differ; the recompiled hooks
  (startup movie, stream publication, audio service) are driven by
  `scripts/region-anchors.eu.json` instead of hardcoded US VAs, and the EU
  seed sets (`scripts/function-seeds.eu.json`,
  `scripts/verified-function-seeds.eu.json`, …) come from the region-aware
  disassembly of the EU XBE.
- **Manual functions.** The cdecl `memmove` lives at `0x00160A70` on EU and
  is aliased to the audited US body in `src/recomp_manual.c`.

## Seed generation

The EU JSON files are generated, not hand-written. They are produced by
`tools/eu_seeds.py` in the GaribaldiSX development repository, which runs
against a checkout of this repository with `--eu <checkout>` and emits the
anchor/seed/range files consumed by `scripts/pipeline.py`.
