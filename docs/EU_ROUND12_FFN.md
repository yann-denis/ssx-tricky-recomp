# Round 12 — EU title.ffn / menu.ffn FFN analysis (verdict: asset legitimately different)

Follow-up to round 11 (`r11_findings.md`): EU menu yellow title top edge sits
~5px lower than US (rows 78-94 vs 73-94, same bottom row 94). Round 11 proved
the divergence is geometric and data-driven. This round decodes the FFN font
format, verifies extraction integrity, and audits the host for font parsing.

## 1. FFN format fully decoded (parser: scratch/r12b_ffn*.py, r12b_dxt.py)

```
0x00  "FNTF" magic
0x04  u16 (per-file checksum-like, EU 0x42a2 / US 0xca56)
0x06  u16 (companion checksum)
0x08  u16 version (202)
0x0a  u16 glyph_count
0x1c  u32 texture_offset
0x20  glyph_count x 12-byte records:
        u16 charcode, u8 w, u8 h, u16 texX, u16 texY,
        u8 advance, i8 top-bearing, u8, u8
tex   16-byte subheader: u16 magic(122), u16 0, u16 width, u16 height
      then DXT1 (pitch = width/2 bytes per 4-row block row)
```
Verified by DXT1-decoding the EU title atlas: glyph 'A' at (110,30,19x16)
renders a clean stylized 'A' — atlas interpretation is correct.

## 2. EU vs US field-by-field (title.ffn)

| field | EU | US |
|---|---|---|
| size / glyphs | 19072 B / 91 | 17152 B / 82 |
| extra glyphs | +10 accented (Ä É Ô Ü à ä è é î ü) | — |
| atlas | 256x140 DXT1 (17920 B) | 256x125 DXT1 (16000 B) |
| common-glyph width diffs | 62/82 (EU glyphs 1-2 px WIDER) | — |
| common-glyph height diffs | 25/82 (lowercase h=11 EU vs 12 US) | — |
| uppercase top-bearing (rec byte 9) | 2 | 3 |
| advance diffs | 36/82 | — |

menu.ffn: EU 8192 B/125 glyphs vs US 7296 B/104; EU adds 20 accented glyphs;
all 105 common glyphs have IDENTICAL w/h metrics. Atlas 128x102 vs 128x92.

## 3. Extraction integrity — VERIFIED CLEAN

Scanned the retail EU ISO
(`~/Téléchargements/SSX Tricky (Europe) (En,Fr,De).iso`, 3.26 GB) for `FNTF`
blobs: title.ffn found at ISO offset 1442547712, menu.ffn at 1442529280,
smlfont/jexcept nearby. Full-file byte comparison against
`game/data/fonts/*.ffn`: **byte-identical** (title sha256
c38f48ae8536f4b5…, menu c62d9c6dad17ca02…). The EU dump is the genuine retail
EU asset — no extraction bug.

## 4. Host font path audit — no host FFN parser exists

`grep -rniE 'ffn|FNTF|font'` over `src/`, `src/recomp/gen/`, `scripts/`,
`tools/` and the frozen `third_party/xboxrecomp` runtime: **zero hits**. The
guest reads the .ffn files itself through HLE file I/O
(`kernel_bridge.c` NtCreateFile/NtReadFile → `kernel_file.c`), parses the
metrics in guest code, and uploads the atlas through the generic NV2A
pushbuffer path (`nv2a_gl.c` texture slots are width/height/format/pitch
driven from the guest's own texture setup — nothing hardcoded to US sizes).
There is no host-side US assumption to fix.

## 5. Verdict: (b) asset legitimately different — rendering is faithful to data

- The EU title font is a genuinely different retail asset: 91 vs 82 glyphs,
  wider uppercase (62/82 width diffs), shorter lowercase (h 11 vs 12),
  smaller top-bearing (2 vs 3), taller atlas (140 vs 125 rows).
- The title quad geometry is computed by the guest from these metrics
  (round 11: EU/US menu code byte-identical modulo rebase 0xC940). With the
  baseline anchored (identical bottom row 94 in both regions), the EU
  bearing/height combination yields a shorter box → top edge at row 78
  instead of 73. On original Xbox hardware the EU disc would render the
  same truncated-looking title: the "bug" is an asset design difference,
  not a host emulation defect.
- No host fix is warranted; changing anything would make EU LESS faithful.

Numbers that produce the observed geometry: EU uppercase metric row
(w≈19-24, h=16, top-bearing 2) vs US (w≈17-22, h=16, top-bearing 3);
bottom row 94 = baseline anchor in both; EU title box = 94-78+1 = 17 px
≈ h16 + bearing 2 - 1 rounding; US box = 94-73+1 = 22 px (US string
"Single Event" includes taller mixed-case layout; EU "TRICKS SIMPLE"
all-caps box is 17 px, matching EU h16+bearing2).
