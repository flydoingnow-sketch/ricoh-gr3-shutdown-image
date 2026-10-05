#!/usr/bin/env python3
# License: see LICENSE (earlier Apache-2.0 grants remain in force)
"""Check or encode the JPEG profile used on one GR IIIx Urban Edition 1.60.

Encoding needs Pillow and an already prepared 720x480 RGB artwork file.
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

SIZE = 107902
OLD_HASH = '7a2154a6d24ed5e460d2a918783d593171e399562923da582801186098ffc89f'
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
                    raise ValueError('Restart markers differ from the tested profile')
                else:
                    break
            parts.append({'marker': 'ENTROPY', 'raw': data[start:pos], 'payload': data[start:pos]})
    raise ValueError('Missing JPEG EOI')


def validate_original(data):
    if len(data) != SIZE or hashlib.sha256(data).hexdigest() != OLD_HASH:
        raise ValueError('Original differs from the tested Urban 1.60 resource')
    return parse_jpeg(data)


def validate_candidate(original, candidate):
    old_parts = validate_original(original)
    parts = parse_jpeg(candidate)
    if len(candidate) != SIZE or [p['marker'] for p in parts] != MARKERS:
        raise ValueError('Candidate length or marker order differs from the tested profile')
    for marker in ('E0', 'C0', 'DA'):
        old = next(p['payload'] for p in old_parts if p['marker'] == marker)
        new = next(p['payload'] for p in parts if p['marker'] == marker)
        if old != new:
            raise ValueError(f'Candidate {marker} parameters differ from original')
    if not next(p['payload'] for p in parts if p['marker'] == 'ENTROPY'):
        raise ValueError('Empty JPEG scan')
    return {'bytes': len(candidate), 'sha256': hashlib.sha256(candidate).hexdigest(),
            'markers': MARKERS, 'camera_display_verified': False}


def encode(original, artwork, output):
    from PIL import Image

    original_data = original.read_bytes()
    original_parts = validate_original(original_data)
    if output.exists():
        raise FileExistsError('Refusing to overwrite candidate')
    if output.resolve().parts[:2] == ('/', 'Volumes'):
        raise ValueError('Encode into local staging, not directly onto an SD card')
    with Image.open(artwork) as source:
        source.load()
        if source.mode != 'RGB' or source.size != (720, 480):
            raise ValueError('Prepare a 720x480 RGB artwork file first; no automatic resizing')
        image = source.copy()
    jfif = next(p['raw'] for p in original_parts if p['marker'] == 'E0')

    def encoded(tables=None, quality=None):
        stream = BytesIO()
        options = dict(format='JPEG', subsampling=2, optimize=True, progressive=False)
        options.update(qtables=tables) if tables is not None else options.update(quality=quality)
        image.save(stream, **options)
        parts = parse_jpeg(stream.getvalue())
        return parts[0]['raw'] + jfif + b''.join(p['raw'] for p in parts[1:] if p['marker'] != 'E0')

    low = {k: list(v) for k, v in Image.open(BytesIO(original_data)).quantization.items()}
    high = {k: list(v) for k, v in Image.open(BytesIO(encoded(quality=91))).quantization.items()}
    positions = [(k, i) for k in sorted(low) for i in range(64) if low[k][i] != high[k][i]]

    def tables(mask):
        result = {k: list(v) for k, v in low.items()}
        for enabled, (k, i) in zip(mask, positions):
            if enabled:
                result[k][i] = high[k][i]
        return result

    rng = random.Random(20261001)
    mask = [True] * len(positions)
    best = encoded(tables(mask))
    best_error = abs(len(best) - SIZE)
    best_mask = list(mask)
    current_error = best_error
    attempts = 1
    start = time.monotonic()
    while best_error and attempts < 6000 and time.monotonic() - start < 45:
        if not positions:
            break
        candidate_mask = list(mask)
        flips = min(len(mask), 1 if attempts % 7 else rng.randint(2, 5))
        for index in rng.sample(range(len(mask)), flips):
            candidate_mask[index] = not candidate_mask[index]
        candidate = encoded(tables(candidate_mask))
        attempts += 1
        error = abs(len(candidate) - SIZE)
        temperature = max(1.0, 8.0 * (1 - (attempts % 400) / 400))
        if error < current_error or rng.random() < 0.015 and error <= current_error + temperature:
            mask, current_error = candidate_mask, error
        if error < best_error:
            best, best_error, best_mask = candidate, error, candidate_mask
        if attempts % 400 == 0:
            mask = list(best_mask)
            for index in rng.sample(range(len(mask)), min(3, len(mask))):
                mask[index] = not mask[index]
            current_error = abs(len(encoded(tables(mask))) - SIZE)
    if best_error:
        raise RuntimeError(f'No exact-size JPEG found in {attempts} trials; no output written. '
                           f'Nearest size was {len(best)}. Revise artwork instead of padding this profile.')
    result = validate_candidate(original_data, best)
    decoded = Image.open(BytesIO(best))
    decoded.load()
    if decoded.mode != 'RGB' or decoded.size != (720, 480):
        raise ValueError('Desktop JPEG decode failed')
    with output.open('xb') as destination:
        destination.write(best)
    return dict(result, encoding_trials=attempts, pillow_decode_verified=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    checker = commands.add_parser('check')
    checker.add_argument('original', type=Path)
    checker.add_argument('candidate', type=Path)
    encoder = commands.add_parser('encode')
    encoder.add_argument('original', type=Path)
    encoder.add_argument('artwork', type=Path)
    encoder.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.command == 'check':
        result = validate_candidate(args.original.read_bytes(), args.candidate.read_bytes())
    else:
        result = encode(args.original, args.artwork, args.output)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
