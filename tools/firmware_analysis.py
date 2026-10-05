#!/usr/bin/env python3
"""Experimental GR III 2.10 offline evidence and resource-export tooling.
No firmware flashing, factory entry guessing, or internal resource writes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from vendor.gr3x_urban_jpeg import parse_jpeg

MODEL = 'GR III'
VERSION = '2.10'
LIMIT = 128 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_new(path, data):
    path = Path(path)
    if path.resolve().parts[:2] == ('/', 'Volumes'):
        raise ValueError('Output must be local, not an SD-card volume')
    with path.open('xb') as stream:
        stream.write(data)


def decode_frames(data):
    """Bounded implementation of the documented GR frame container.

    Static format hypothesis for the supplied file; not model authentication.
    """
    if len(data) < 128:
        raise ValueError('Truncated container header')
    output = bytearray()
    pos = 128
    frames = 0
    while pos + 2 <= len(data):
        prefix = int.from_bytes(data[pos:pos + 2], 'big')
        pos += 2
        if prefix == 0:
            break
        end = pos + (prefix & 0x7fff)
        if end > len(data):
            raise ValueError('Frame exceeds input')
        if prefix & 0x8000:
            if len(output) + end - pos > LIMIT:
                raise ValueError('Decoded payload limit exceeded')
            output.extend(data[pos:end])
            pos = end
        else:
            while pos < end:
                if pos + 2 > end:
                    raise ValueError('Truncated block flags')
                flags = int.from_bytes(data[pos:pos + 2], 'big')
                pos += 2
                for bit in range(15, -1, -1):
                    if pos >= end:
                        break
                    if flags & (1 << bit):
                        if pos + 2 > end:
                            raise ValueError('Truncated back reference')
                        first, second = data[pos:pos + 2]
                        pos += 2
                        distance = ((first & 0xf8) << 5) + second
                        count = first & 7
                        if count == 7:
                            while True:
                                if pos >= end:
                                    raise ValueError('Truncated length extension')
                                extension = data[pos]
                                pos += 1
                                count += extension
                                if extension != 255:
                                    break
                        if not distance:
                            break
                        if distance > len(output):
                            raise ValueError('Back reference before output')
                        if len(output) + count + 3 > LIMIT:
                            raise ValueError('Decoded payload limit exceeded')
                        for _ in range(count + 3):
                            output.append(output[-distance])
                    else:
                        if len(output) >= LIMIT:
                            raise ValueError('Decoded payload limit exceeded')
                        output.append(data[pos])
                        pos += 1
            pos = end
        frames += 1
    if not frames:
        raise ValueError('No frames decoded')
    return bytes(output), frames, pos


def firmware_report(path):
    data = path.read_bytes()
    decoded, frames, consumed = decode_frames(data)
    patterns = [rb'[0-9]{8}\.[0-9]{3}',
                rb'[A-Z]:\\Resource\\Jpeg\\[A-Za-z0-9_.]+',
                rb'[A-Za-z0-9_]*(?:GoodBye|GB_Urban|GB_Diary|GB_ING)[A-Za-z0-9_.]*',
                rb'OPEN_FACTORY_DEBUG_MENU', rb'DEVELOP\.MOD']
    findings = []
    for pattern in patterns:
        for match in re.finditer(pattern, decoded):
            findings.append({'decoded_file_offset': match.start(),
                             'text': match.group().decode('ascii')})
            if len(findings) > 10000:
                raise ValueError('Too many findings')
    return {'requested_model': MODEL, 'requested_firmware': VERSION,
            'status': 'static_evidence_only', 'hardware_verified': False,
            'input_sha256': sha(data), 'input_bytes': len(data),
            'header_model_raw': data[8:20].hex(),
            'header_version_hypothesis': list(data[0x38:0x3c]),
            'version_matches_hypothesis': data[0x38:0x3a] == bytes([2, 10]),
            'word_checksum': sum(x[0] for x in struct.iter_unpack('<I', data)) & 0xffffffff
                             if len(data) % 4 == 0 else None,
            'decoded_bytes': len(decoded), 'frames': frames, 'consumed': consumed,
            'findings': findings, 'embedded_resources': embedded_resources(decoded),
            'limitations': 'Strings are candidates, not proof of entry acceptance or active resources.'}


def jpeg_report(data):
    if not data:
        raise ValueError('Empty readback')
    parts = parse_jpeg(data)
    frames = [p for p in parts if p['marker'] in ('C0', 'C2')]
    if len(frames) != 1 or frames[0]['marker'] != 'C0':
        raise ValueError('Only single-scan baseline JPEG supported by this experimental analyzer')
    frame = frames[0]['payload']
    if len(frame) < 6 or len(frame) != 6 + 3 * frame[5]:
        raise ValueError('Malformed frame header')
    return {'bytes': len(data), 'sha256': sha(data),
            'precision': frame[0], 'height': int.from_bytes(frame[1:3], 'big'),
            'width': int.from_bytes(frame[3:5], 'big'), 'components': frame[5],
            'markers': [p['marker'] for p in parts],
            'parameters': {p['marker']: p['payload'].hex() for p in parts
                           if p['marker'] in ('E0', 'C0', 'DA')},
            'camera_display_verified': False}


def embedded_resources(decoded):
    """Describe archive records; never export vendor artwork in deliverables."""
    resources = []
    for match in re.finditer(rb'B:\\Resource\\Jpeg\\[A-Za-z0-9_]+\.jpg\x00', decoded):
        # The observed archive pads names to four-byte length, then a LE size.
        record = match.start() + ((len(match.group()) + 3) // 4) * 4
        if record + 4 > len(decoded):
            continue
        length = int.from_bytes(decoded[record:record + 4], 'little')
        start = record + 4
        if length < 4 or start + length > len(decoded):
            continue
        data = decoded[start:start + length]
        if data[:2] != b'\xff\xd8':
            continue
        profile = jpeg_report(data)
        resources.append({'path': match.group()[:-1].decode('ascii'),
                          'archive_name_offset': match.start(),
                          'image_offset': start, 'profile': profile})
    return resources


def bind_backup(first, second, body_id):
    a, b = first.read_bytes(), second.read_bytes()
    profile = jpeg_report(a)
    if a != b:
        raise ValueError('The two original readbacks differ')
    if not body_id.strip():
        raise ValueError('A local body identifier is required')
    return {'model': MODEL, 'firmware': VERSION, 'body_id': body_id,
            'status': 'matching_readbacks_not_proof_of_factory_original',
            'original': profile, 'internal_target': None, 'factory_entry': None,
            'internal_write_enabled': False}


def compare_candidate(original, candidate):
    a, b = jpeg_report(original), jpeg_report(candidate)
    if a['sha256'] == b['sha256']:
        raise ValueError('Candidate is identical to original')
    if a['bytes'] != b['bytes']:
        raise ValueError('Candidate length differs; do not pad to bypass this check')
    if a['markers'] != b['markers'] or a['parameters'] != b['parameters']:
        raise ValueError('Candidate JPEG declarations differ from this body original')
    return {'structural_comparison_passed': True, 'candidate': b,
            'internal_write_enabled': False,
            'note': 'Structural comparison is not JPEG decode or hardware verification.'}


def export_probe(target):
    # Explicit path only; no inferred drive, target or entry files.
    if not re.fullmatch(r'[AB]:\\Resource\\Jpeg\\[A-Za-z0-9_]{1,40}\.jpg', target, re.I):
        raise ValueError('Require one literal A:/B: Resource/Jpeg JPEG path; no TTL injection')
    lines = ['; EXPERIMENTAL GR III 2.10 export only; not hardware tested.',
             '; Entry and source path must be established independently.',
             f"filestat '{target}' source_size", 'if result <> 0 then', 'exit', 'endif',
             'if source_size <= 0 then', 'exit', 'endif']
    for name in ('G3READ1.JPG', 'G3READ2.JPG'):
        lines += [f"getfileattr 'C:\\{name}'", 'if result <> -1 then', 'exit', 'endif']
    for name in ('G3READ1.JPG', 'G3READ2.JPG'):
        lines += [f"filecopy '{target}' 'C:\\{name}'",
                  f"filestat 'C:\\{name}' output_size", 'if result <> 0 then', 'exit', 'endif',
                  'if output_size <> source_size then', 'exit', 'endif']
    lines += ['exit']
    return ('\r\n'.join(lines) + '\r\n').encode('ascii')


FIRMWARE_SHA = 'd6a3c9c288d784080e7b283222ecdd8752adfeed6faa36dab44f73115354bfd4'
ORIGINAL_SHA = 'dff9ba0ad2c7ea2697b19470cf6c695337651ee0ef415a6d3359a7f318ff3c79'
TARGET = r'B:\Resource\Jpeg\GoodBye.jpg'
ENTRY = '00078350.588'
ENTRY_DATA = b'[OPEN_FACTORY_DEBUG_MENU]\r\n'
DEVELOP = bytes.fromhex('07 01 2c 1f 10 03 1e 16 05 2d')


def prepare_export(firmware, output):
    """Experimental entry + export; no internal writes or firmware output."""
    data = firmware.read_bytes()
    if sha(data) != FIRMWARE_SHA:
        raise ValueError('This package is bound to the analyzed GR III 2.10 sample')
    decoded, _, _ = decode_frames(data)
    # Fingerprints from the independently disassembled format/getter path.
    checks = [(0xd71e48, b'C:\\%08ld.%03ld\x00'),
              (0x10870 + 0x81fe9c, bytes.fromhex('0e0203e3010040e31eff2fe1')),
              (0x10870 + 0x81fe4c, bytes.fromhex('930fa0e31eff2fe1'))]
    for offset, expected in checks:
        if decoded[offset:offset + len(expected)] != expected:
            raise ValueError('Entry code fingerprint changed')
    resources = embedded_resources(decoded)
    resource = next((r for r in resources if r['path'] == TARGET), None)
    if resource is None or resource['profile']['sha256'] != ORIGINAL_SHA:
        raise ValueError('Firmware resource differs from reference')
    if DEVELOP not in decoded or b'OPEN_FACTORY_DEBUG_MENU' not in decoded:
        raise ValueError('Factory command/token absent')
    output = Path(output)
    if output.resolve().parts[:2] == ('/', 'Volumes'):
        raise ValueError('Prepare a local folder, not an SD volume')
    output.mkdir(exist_ok=False)
    (output / 'script').mkdir()
    files = {ENTRY: ENTRY_DATA, 'DEVELOP.MOD': DEVELOP,
             'script/startup.ttl': export_probe(TARGET)}
    for name, content in files.items():
        save_new(output / name, content)
    result = {'model': MODEL, 'firmware': VERSION, 'firmware_sha256': FIRMWARE_SHA,
              'status': 'experimental_export_only', 'hardware_verified': False,
              'entry_basis': 'ARM static filename-format and constant getters',
              'entry': ENTRY, 'resource': resource,
              'files': {name: {'bytes': len(content), 'sha256': sha(content)}
                        for name, content in files.items()},
              'internal_write_enabled': False}
    save_new(output / 'manifest.json', json.dumps(result, indent=2).encode())
    return result


def verify_export(folder, body_id):
    first, second = folder / 'G3READ1.JPG', folder / 'G3READ2.JPG'
    result = bind_backup(first, second, body_id)
    if result['original']['sha256'] != ORIGINAL_SHA:
        raise ValueError('Readback differs from GR III 2.10 reference; retain evidence and stop')
    result['internal_target'] = TARGET
    result['factory_entry'] = ENTRY
    result['status'] = 'exports_match_firmware_reference_active_display_unverified'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('firmware-report')
    p.add_argument('firmware', type=Path)
    p.add_argument('output', type=Path)
    p = commands.add_parser('bind-backup')
    p.add_argument('first', type=Path)
    p.add_argument('second', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--body-id', required=True)
    p = commands.add_parser('check-candidate')
    p.add_argument('original', type=Path)
    p.add_argument('candidate', type=Path)
    p = commands.add_parser('export-probe')
    p.add_argument('--source', required=True, help='Independently established internal path')
    p.add_argument('--output', required=True, type=Path)
    p = commands.add_parser('prepare-export')
    p.add_argument('firmware', type=Path)
    p.add_argument('output', type=Path)
    p = commands.add_parser('verify-export')
    p.add_argument('folder', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--body-id', required=True)
    args = parser.parse_args()
    if args.command == 'firmware-report':
        result = firmware_report(args.firmware)
        save_new(args.output, json.dumps(result, ensure_ascii=False, indent=2).encode())
    elif args.command == 'bind-backup':
        result = bind_backup(args.first, args.second, args.body_id)
        save_new(args.output, json.dumps(result, ensure_ascii=False, indent=2).encode())
    elif args.command == 'check-candidate':
        result = compare_candidate(args.original.read_bytes(), args.candidate.read_bytes())
    elif args.command == 'prepare-export':
        result = prepare_export(args.firmware, args.output)
    elif args.command == 'verify-export':
        result = verify_export(args.folder, args.body_id)
        save_new(args.output, json.dumps(result, indent=2).encode())
    else:
        save_new(args.output, export_probe(args.source))
        result = {'experimental_export_script_created': True, 'hardware_verified': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
