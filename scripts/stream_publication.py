"""Preserve stream availability publication on concurrently executing host threads."""
import re
from pathlib import Path


def fix_stream_publication(text, producer='0x0014EA00'):
    marker = f"void sub_{producer[2:]}(void)"
    if marker not in text:
        return text, False
    start = text.index(marker)
    end = text.index('\n/**', start)
    body = text[start:end]
    # The publication race fixup: original publishes count (edx) before the
    # pointer is initialized; ECX retains the exact new byte count.
    old_re = re.compile(
        r'    RECOMP_STORE32\(eax \+ 8, edx\);\n'
        r'    if \(CMP_NE\(_fa, _fb\)\) goto (loc_[0-9A-Fa-f]+);')
    published_re = re.compile(
        r'(loc_[0-9A-Fa-f]+): ;\n    eax = RECOMP_READ32\(esi \+ 0x60\);')
    old_match = old_re.search(body)
    pub_match = published_re.search(body)
    if old_match is None and pub_match is not None and 'ssx' not in body and \
            'Publish packet pointer' not in body:
        raise ValueError('Unsupported translated stream producer')
    if old_match is None:
        # Already applied (or unsupported shape without the original store).
        if 'Publish packet pointer before its nonzero availability count.' in body:
            return text, True
        return text, False
    if pub_match is None:
        raise ValueError('Unsupported translated stream producer')
    loc = old_match.group(1)
    if pub_match.group(1) != loc:
        raise ValueError('Unsupported translated stream producer')
    published = (f'{loc}: ;\n'
                 '    RECOMP_STORE32(eax + 8, ecx);\n'
                 '    eax = RECOMP_READ32(esi + 0x60);')
    # Original 14EAFF publishes count before 14EB08 initializes the pointer.
    # The reader tests count before taking the producer's critical section.
    # Independent host threads can therefore consume its poison initializer.
    # ECX retains the exact new byte count after EDX becomes the packet pointer.
    body = old_re.sub('    /* Publish packet pointer before its nonzero availability count. */\n'
                      '    if (CMP_NE(_fa, _fb)) goto ' + loc + ';', body, count=1)
    body = published_re.sub(published, body, count=1)
    return text[:start] + body + text[end:], True


def apply(root, anchors=None):
    producer = (anchors or {}).get('stream_producer', '0x0014EA00')
    found = 0
    for path in (Path(root) / 'src/recomp/gen').glob('recomp_*.c'):
        old = path.read_text()
        new, matched = fix_stream_publication(old, producer)
        found += matched
        if new != old:
            path.write_text(new)
    if found != 1:
        raise ValueError(f'Expected one supported stream producer, found {found}')
