#!/usr/bin/env python3
# License: see LICENSE (earlier Apache-2.0 grants remain in force)
"""Validate the JPEG profile used on GR III 2.10 resource. Derived from the local GR III adapter.

Encoding is implemented in gr3_workflow.py.
The bounded quantizer search may fail for other artwork. It adds no padding.
Structure checks and desktop decoding do not prove camera compatibility.
"""
import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import random
import time

SIZE = 7264
OLD_HASH = 'dff9ba0ad2c7ea2697b19470cf6c695337651ee0ef415a6d3359a7f318ff3c79'
MARKERS = ['D8', 'E0', 'DB', 'DB', 'C0', 'C4', 'C4', 'C4', 'C4', 'DA', 'ENTROPY', 'D9']


def parse_jpeg(data):
    """Parse the single-scan profile strictly, including bounds and entropy stuffing."""
    if data[:2] != b'\xff\xd8':
        raise ValueError('Missing JPEG SOI')
    parts = [{'marker': 'D8', 'raw': data[:2], 'payload': b''}]
    pos = 2
    while pos < len(data):
        start = pos
        if data[pos] != 255:
            raise ValueError('Expected JPEG marker')
        while pos < len(data) and data[pos] == 255:
            pos += 1
        if pos == len(data):
            raise ValueError('Truncated JPEG marker')
        marker = data[pos]
        pos += 1
        if marker == 0xD9:
            if pos != len(data):
                raise ValueError('Trailing bytes after EOI')
            parts.append({'marker': 'D9', 'raw': data[start:pos], 'payload': b''})
            return parts
        if marker in (0, 1, 0xD8) or 0xD0 <= marker <= 0xD7:
            raise ValueError('Unexpected standalone marker')
        if pos + 2 > len(data):
            raise ValueError('Truncated JPEG length')
        length = int.from_bytes(data[pos:pos + 2], 'big')
        if length < 2 or pos + length > len(data):
            raise ValueError('Invalid JPEG segment length')
        end = pos + length
        parts.append({'marker': f'{marker:02X}', 'raw': data[start:end], 'payload': data[pos + 2:end]})
        pos = end
        if marker == 0xDA:
            start = pos
            while pos < len(data):
                if data[pos] != 255:
                    pos += 1
                    continue
                if pos + 1 >= len(data):
                    raise ValueError('Truncated JPEG entropy')
                following = data[pos + 1]
                if following == 0:
                    pos += 2
                elif 0xD0 <= following <= 0xD7:
                    raise ValueError('Restart markers differ from the firmware reference profile')
                else:
                    break
            parts.append({'marker': 'ENTROPY', 'raw': data[start:pos], 'payload': data[start:pos]})
    raise ValueError('Missing JPEG EOI')


def validate_original(data):
    if len(data) != SIZE or hashlib.sha256(data).hexdigest() != OLD_HASH:
        raise ValueError('Original differs from the GR III 2.10 firmware GoodBye.jpg reference')
    return parse_jpeg(data)


def validate_candidate(original, candidate):
    old_parts = validate_original(original)
    parts = parse_jpeg(candidate)
    if len(candidate) != SIZE or [p['marker'] for p in parts] != MARKERS:
        raise ValueError('Candidate length or marker order differs from the firmware reference profile')
    for marker in ('E0', 'C0', 'DA'):
        old = next(p['payload'] for p in old_parts if p['marker'] == marker)
        new = next(p['payload'] for p in parts if p['marker'] == marker)
        if old != new:
            raise ValueError(f'Candidate {marker} parameters differ from original')
    if not next(p['payload'] for p in parts if p['marker'] == 'ENTROPY'):
        raise ValueError('Empty JPEG scan')
    return {'bytes': len(candidate), 'sha256': hashlib.sha256(candidate).hexdigest(),
            'markers': MARKERS, 'camera_display_verified': False}

