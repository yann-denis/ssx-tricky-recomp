"""Optional observation around the supported game's streaming buffer service.

Anchors (function VAs and the three data VAs the service stores to) are
region-parameterized via scripts/region-anchors.<region>.json. The EU build
allocates registers differently inside these routines, so store instructions
are matched with a register-agnostic pattern; if any anchor cannot be located
in the translated sources the hook is skipped with a warning instead of
aborting the pipeline (the observation only feeds optional APU pacing).
"""
import re
from pathlib import Path

US = {'audio_service': '0x00015110', 'audio_stream': '0x00014DF0',
      'audio_publish_va': '0x00205BE8', 'audio_lead_va': '0x00205BE4',
      'audio_ring_va': '0x00205BE0'}


def _warn(msg):
    print(f'[audio-service-observation] WARNING: {msg}', flush=True)


def _function(text, va):
    name = f"sub_{va[2:]}"
    marker = f'void {name}(void)'
    if marker not in text:
        return None, None
    begin = text.index(marker)
    end = text.index('\n/**', begin)
    return begin, end


def apply(root, anchors=None):
    a = {**US, **(anchors or {})}
    gen = Path(root) / 'src/recomp/gen'
    path = None
    for candidate in gen.glob('recomp_*.c'):
        if f"void sub_{a['audio_service'][2:]}(void)" in candidate.read_text():
            path = candidate
            break
    if path is None:
        _warn(f"service function {a['audio_service']} not in translated sources; skipping")
        return
    text = path.read_text()

    begin, end = _function(text, a['audio_service'])
    if begin is None:
        _warn(f"service function {a['audio_service']} not in translated sources; skipping")
        return
    body = text[begin:end]
    # Optional timing trace: the label anchors are US-layout only; other
    # regions skip it (it feeds an optional diagnostic file).
    if a['audio_service'] == US['audio_service']:
        for marker, code in [('loc_00015128: ;\n',
                              '    ssx_audio_service_trace(0, RECOMP_READ32(esp + 8));\n'),
                             ('loc_000151E0: ;\n',
                              '    ssx_audio_service_trace(1, esi);\n')]:
            if marker in body and marker + code not in body:
                body = body.replace(marker, marker + code, 1)
    trace_decl = '    extern void ssx_audio_service_trace(unsigned, unsigned);\n'
    pub = a['audio_publish_va']
    # Generated C prints device VAs without leading zeros (0x20AF10, not
    # 0x0020AF10); accept either spelling.
    pub_alt = '0x%X' % int(pub, 16)
    pub_re = re.compile(rf'    RECOMP_STORE32\((0x{pub[2:]}|0x{pub_alt[2:]}), (\w+)\);\n')
    stores = pub_re.findall(body)
    if not stores:
        _warn(f'no store to publish VA {pub} found; skipping audio service observation')
        return
    reg = stores[0][1]
    decl = '    extern void ssx_audio_service_publish(unsigned);\n'
    if decl not in body:
        def publish_after_store(m):
            return (f'    RECOMP_STORE32({m.group(1)}, {m.group(2)});\n'
                    f'    ssx_audio_service_publish({m.group(2)});\n')
        body = pub_re.sub(publish_after_store, body, count=1)
        head = f'void sub_{a["audio_service"][2:]}(void)\n{{\n'
        body = body.replace(head, head + decl, 1)
        if trace_decl not in body and 'ssx_audio_service_trace' in body:
            body = body.replace(head, head + trace_decl, 1)
    text = text[:begin] + body + text[end:]

    begin, end = _function(text, a['audio_stream'])
    if begin is None:
        _warn(f"stream function {a['audio_stream']} not in translated sources; "
              'lead/ring retuning skipped')
    else:
        body = text[begin:end]
        for address, name in [(a['audio_lead_va'], 'lead'), (a['audio_ring_va'], 'ring')]:
            alt = '0x%X' % int(address, 16)
            rx = re.compile(rf'    RECOMP_STORE32\((0x{address[2:]}|0x{alt[2:]}), (\w+)\);\n')
            if not rx.search(body):
                _warn(f'no store to {name} VA {address} found; {name} retuning skipped')
                continue
            def retune_before_store(m):
                return (f'    {m.group(2)} = ssx_audio_stream_{name}({m.group(2)});\n'
                        f'    RECOMP_STORE32({m.group(1)}, {m.group(2)});\n')
            body = rx.sub(retune_before_store, body, count=1)
            declaration = f'    extern unsigned ssx_audio_stream_{name}(unsigned);\n'
            if declaration not in body:
                body = body.replace(f'void sub_{a["audio_stream"][2:]}(void)\n{{\n',
                                    f'void sub_{a["audio_stream"][2:]}(void)\n{{\n' + declaration, 1)
        text = text[:begin] + body + text[end:]
    path.write_text(text)
