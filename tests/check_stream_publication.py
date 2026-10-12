"""Run the actual generated producer and a forced pre-fix publication negative."""
import argparse
import json
import re
import subprocess
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--cc', required=True)
p.add_argument('--root', type=Path, required=True)
p.add_argument('--work', type=Path, required=True)
a = p.parse_args()
a.work.mkdir(exist_ok=True)
anchors = {}
for region_file in sorted((a.root / 'scripts').glob('region-anchors.*.json')):
    anchors = json.loads(region_file.read_text())
    break
producer = anchors.get('stream_producer', '0x0014EA00')
name = 'sub_' + producer[2:]
source = next((a.root / 'src/recomp/gen').glob('recomp_*.c'))
text = None
for path in (a.root / 'src/recomp/gen').glob('recomp_*.c'):
    candidate = path.read_text()
    if f'void {name}(void)' in candidate:
        source, text = path, candidate
        break
if text is None:
    raise SystemExit(f'{name} not found in generated sources')
start = text.index(f'void {name}(void)')
body = text[start:text.index('\n/**', start)]
late_re = re.search(r'(loc_[0-9A-Fa-f]+): ;\n    RECOMP_STORE32\(eax \+ 8, ecx\);', body)
assert late_re, 'publication store not found in producer body'
loc = late_re.group(1)
late = late_re.group(0)
negative = body.replace(late, f'{loc}: ;').replace(
    f'    if (CMP_NE(_fa, _fb)) goto {loc};',
    f'    RECOMP_STORE32(eax + 8, edx);\n    if (CMP_NE(_fa, _fb)) goto {loc};')
# Rename region-specific symbols to the fixture's fixed US names so the
# fixture itself stays region-agnostic.
callees = sorted({c for c in re.findall(r'sub_[0-9A-Fa-f]+', body) if c != name})
renames = {name: 'sub_0014EA00'}
for callee, fixed in zip(callees, ('sub_00164300', 'sub_00164310')):
    renames[callee] = fixed

def normalize(text):
    for old, new in renames.items():
        if old != new:
            text = re.sub(r'\b' + old + r'\b', new, text)
    return text

body, negative = normalize(body), normalize(negative)
for label, text, expected in [('actual', body, 0), ('negative', negative, 42)]:
    include = (a.work / (label + '.inc')).resolve()
    include.write_text(text)
    executable = (a.work / label).resolve()
    subprocess.run([a.cc, '-std=c11', '-O2', '-DPRODUCER_INCLUDE="' + str(include) + '"',
                    str(a.root / 'tests/stream_publication_fixture.c'), '-o', str(executable)], check=True)
    result = subprocess.run([str(executable)], capture_output=True, text=True)
    assert result.returncode == expected, (label, result.returncode, result.stdout, result.stderr)
    print(label + ': ' + (result.stdout or result.stderr).strip())
