#!/usr/bin/env python3
# License: see LICENSE (earlier Apache-2.0 grants remain in force)
"""Generate the two TTL steps verified on one GR IIIx Urban Edition 1.60.

This tool writes a local staging directory. It does not connect to a camera,
locate an SD card, or install anything. Generated TTL embeds the user's JPEG;
keep generated files private. Verify full camera readbacks between stages.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from gr3x_urban_jpeg import validate_candidate

NEW = r'B:\Resource\Jpeg\RB81NW.JPG'
OLD = r'B:\Resource\Jpeg\RB41OL.JPG'
TARGET = r'B:\Resource\Jpeg\GB_Urban.jpg'
SIZE = 107902
OLD_HASH = '7a2154a6d24ed5e460d2a918783d593171e399562923da582801186098ffc89f'


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Script:
    def __init__(self, log):
        self.log = log
        self.lines = [f"filestat '{log}' logsize", 'if result <> 0 then',
                      'exit', 'endif', 'if logsize <> 0 then', 'exit', 'endif',
                      f"fileopen log '{log}' 0", 'if log < 0 then', 'exit', 'endif',
                      "filewriteln log 'started'", "filewriteln log '1'",
                      'error = 0', 'attempted = 0', 'restored = 0']
        self.checkpoint('preflight_started')

    def add(self, *lines):
        self.lines.extend(lines)

    def guard(self, condition, code, destination='done', close=()):
        self.add(f'if {condition} then', *(f'fileclose {x}' for x in close),
                 f'error = {code}', f'goto {destination}', 'endif')

    def size(self, path, code, destination='done'):
        self.add(f"filestat '{path}' checksize", 'statresult = result')
        self.guard('statresult <> 0', code, destination)
        self.guard(f'checksize <> {SIZE}', code + 1, destination)

    def checkpoint(self, name):
        self.add(f"filewriteln log '{name}'", "filewriteln log '1'", 'fileclose log',
                 f"fileopen log '{self.log}' 1", 'if log < 0 then', 'exit', 'endif')

    def copy(self, source, destination):
        if not source.startswith('B:'):
            raise ValueError('Every filecopy source must be internal B:')
        self.add(f"filecopy '{source}' '{destination}'")

    def finish(self):
        self.add(':done')
        for name in ('error', 'attempted', 'restored'):
            self.add(f'int2str value {name}', f"filewriteln log '{name}'", 'filewriteln log value')
        self.add("filewriteln log 'completed'", "filewriteln log '1'", 'fileclose log', 'exit')
        if max(map(len, self.lines)) >= 256:
            raise ValueError('Native parser line buffer exceeded')
        if sum(x.startswith('if ') for x in self.lines) != self.lines.count('endif'):
            raise ValueError('Unbalanced conditionals')
        labels = {x[1:]: i for i, x in enumerate(self.lines) if x.startswith(':')}
        for i, line in enumerate(self.lines):
            if line.startswith('goto ') and labels[line[5:]] <= i:
                raise ValueError('A backward interpreted jump is forbidden')
        if any(x.startswith(('filedelete ', 'setfileattr ')) for x in self.lines):
            raise ValueError('Unexpected resource deletion or attribute mutation')
        return ('\r\n'.join(self.lines) + '\r\n').encode('ascii')


def temporary_script(image):
    s = Script(r'C:\URBLOG8.TXT')
    s.size(OLD, 101)
    s.size(TARGET, 103)
    s.add(f"getfileattr '{TARGET}'")
    s.guard('result <> 32', 105)
    s.add(f"getfileattr '{NEW}'")
    s.guard('result <> -1', 106)
    # Existing original and backup are copied out before any temporary write.
    s.copy(OLD, r'C:\URBORG8.JPG')
    s.size(r'C:\URBORG8.JPG', 107)
    s.copy(TARGET, r'C:\URBPRE8.JPG')
    s.size(r'C:\URBPRE8.JPG', 109)
    s.checkpoint('original_readbacks_saved')
    s.add(f"filecreate image '{NEW}'")
    s.guard('image < 0', 201)
    s.add('fileclose image', f"filetruncate '{NEW}' {SIZE}")
    s.size(NEW, 202)
    s.add(f"fileopen image '{NEW}' 0")
    s.guard('image < 0', 204)
    s.checkpoint('temporary_write_started')
    index = 0
    operations = 0
    while index < len(image):
        if image[index] == 0:
            index += 1
            continue
        start = index
        while index < len(image) and image[index] != 0 and index - start < 42:
            index += 1
        s.add(f'fileseek image {start} 0',
              'filewrite image ' + ''.join(f'#{x}' for x in image[start:index]))
        operations += 1
    s.add('fileclose image')
    s.size(NEW, 205)
    s.checkpoint('temporary_write_finished')
    s.copy(NEW, r'C:\URBIMG8.JPG')
    s.size(r'C:\URBIMG8.JPG', 207)
    s.checkpoint('readback_finished')
    data = s.finish()
    reconstructed = bytearray(SIZE)
    position = None
    for line in s.lines:
        if line.startswith('fileseek image '):
            position = int(line.split()[2])
        elif line.startswith('filewrite image '):
            values = bytes(int(x) for x in re.findall(r'#(\d+)', line))
            if not values or 0 in values or position is None:
                raise ValueError('Invalid emitted literal write')
            reconstructed[position:position + len(values)] = values
    if bytes(reconstructed) != image:
        raise ValueError('Script payload differs from JPEG')
    internal_writes = [x for x in s.lines if x.startswith('filecopy ') and x.split("'")[3].startswith('B:')]
    if internal_writes:
        raise ValueError('Step 1 must not overwrite the shutdown resource')
    return data, operations, len(s.lines), max(map(len, s.lines))


def install_script():
    s = Script(r'C:\URBLOG9.TXT')
    for path, code in ((NEW, 101), (OLD, 103), (TARGET, 105)):
        s.size(path, code)
    s.add(f"getfileattr '{TARGET}'", 'originalattr = result')
    s.guard('originalattr <> 32', 107)
    for source, destination, code in (
            (NEW, r'C:\URBNW9.JPG', 108), (OLD, r'C:\URBOR9.JPG', 110),
            (TARGET, r'C:\URBPRE9.JPG', 112)):
        s.copy(source, destination)
        s.size(destination, code)
    s.checkpoint('write_started')
    s.add('attempted = 1')
    s.copy(NEW, TARGET)
    s.size(TARGET, 201, 'rollback')
    s.copy(TARGET, r'C:\URBRD9.JPG')
    s.size(r'C:\URBRD9.JPG', 203, 'rollback')
    s.add(f"getfileattr '{TARGET}'")
    s.guard('result <> originalattr', 205, 'rollback')
    s.add('goto done', ':rollback', 'restored = 1')
    s.copy(OLD, TARGET)
    s.copy(TARGET, r'C:\URBRS9.JPG')
    # These checks cannot establish content identity; computer readback SHA-256
    # remains mandatory. JPEG display also cannot be established by TTL sizes.
    script = s.finish()
    internal_writes = [x for x in s.lines if x.startswith('filecopy ') and x.split("'")[3].startswith('B:')]
    if internal_writes != [f"filecopy '{NEW}' '{TARGET}'", f"filecopy '{OLD}' '{TARGET}'"]:
        raise ValueError('Unexpected internal installation destinations')
    return script, len(s.lines)



def build(original, image, output):
    original_data, image_data = original.read_bytes(), image.read_bytes()
    if sha(original_data) != OLD_HASH or len(original_data) != SIZE:
        raise ValueError('Original does not match the tested Urban 1.60 backup; stop and investigate this body/version.')
    validate_candidate(original_data, image_data)
    if output.exists():
        raise FileExistsError('Output directory must be new; previous logs and readbacks must be archived.')
    if output.resolve().parts[:2] == ('/', 'Volumes'):
        raise ValueError('Build in a local directory, then copy one reviewed step to the SD card.')
    first, operations, lines, longest = temporary_script(image_data)
    second, install_lines = install_script()
    output.mkdir(parents=True)
    for name, log, script in [('01-temporary-only', 'URBLOG8.TXT', first),
                              ('02-install-after-readback', 'URBLOG9.TXT', second)]:
        directory = output / name / 'script'
        directory.mkdir(parents=True)
        (directory / 'startup.ttl').write_bytes(script)
        (directory.parent / log).write_bytes(b'')
    new_hash = sha(image_data)
    manifest = {
        'format': 'gr3x-urban-160-two-step-v1', 'tested_model': 'GR IIIx Urban Edition',
        'tested_firmware': '1.60', 'image_bytes': SIZE,
        'original_sha256': OLD_HASH, 'candidate_sha256': new_hash,
        'target': TARGET, 'temporary': NEW, 'internal_original_backup': OLD,
        'step_1': {'script_bytes': len(first), 'script_sha256': sha(first),
                   'lines': lines, 'maximum_line_length': longest,
                   'literal_write_operations': operations,
                   'required_readbacks': {'URBIMG8.JPG': new_hash,
                                           'URBORG8.JPG': OLD_HASH, 'URBPRE8.JPG': OLD_HASH}},
        'step_2': {'script_bytes': len(second), 'script_sha256': sha(second), 'lines': install_lines,
                   'required_readbacks': {'URBNW9.JPG': new_hash, 'URBOR9.JPG': OLD_HASH,
                                           'URBPRE9.JPG': OLD_HASH, 'URBRD9.JPG': new_hash}},
        'interpreted_checksum_loops': 0,
        'generated_scripts_contain_user_image_bytes': True,
        'camera_installation_verified_for_this_input': False,
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def verify(manifest_path, readback_directory, step):
    if step not in (1, 2):
        raise ValueError('Step must be 1 or 2')
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('format') != 'gr3x-urban-160-two-step-v1'
            or manifest.get('original_sha256') != OLD_HASH
            or manifest.get('image_bytes') != SIZE
            or not re.fullmatch('[0-9a-f]{64}', manifest.get('candidate_sha256', ''))):
        raise ValueError('Unknown or changed manifest')
    new_hash = manifest['candidate_sha256']
    expected = ({'URBIMG8.JPG': new_hash, 'URBORG8.JPG': OLD_HASH, 'URBPRE8.JPG': OLD_HASH}
                if step == 1 else {'URBNW9.JPG': new_hash, 'URBOR9.JPG': OLD_HASH,
                                   'URBPRE9.JPG': OLD_HASH, 'URBRD9.JPG': new_hash})
    for name, expected_hash in expected.items():
        data = (readback_directory / name).read_bytes()
        if len(data) != SIZE or sha(data) != expected_hash:
            raise ValueError(f'Full readback mismatch: {name}; do not proceed.')
    name = 'URBLOG8.TXT' if step == 1 else 'URBLOG9.TXT'
    log = (readback_directory / name).read_text(encoding='ascii').splitlines()
    if len(log) % 2:
        raise ValueError('Incomplete log')
    if len(set(log[::2])) != len(log) // 2:
        raise ValueError('Duplicate log fields; archive stale runs instead of appending them')
    fields = dict(zip(log[::2], log[1::2]))
    expected_fields = {'started': '1', 'error': '0', 'completed': '1', 'restored': '0',
                       'attempted': '0' if step == 1 else '1'}
    if any(fields.get(k) != v for k, v in expected_fields.items()):
        raise ValueError('Log does not show successful completion')
    return {'step': step, 'complete_readback_hashes_verified': expected,
            'successful_log_verified': True,
            'camera_display_must_be_checked_separately': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    creator = commands.add_parser('build', help='Generate two separate local steps for an already reviewed JPEG')
    creator.add_argument('original', type=Path)
    creator.add_argument('candidate', type=Path)
    creator.add_argument('output', type=Path)
    verifier = commands.add_parser('verify', help='Check every full camera readback and completion log')
    verifier.add_argument('manifest', type=Path)
    verifier.add_argument('readback_directory', type=Path)
    verifier.add_argument('--step', type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    if args.command == 'build':
        result = build(args.original, args.candidate, args.output)
    else:
        result = verify(args.manifest, args.readback_directory, args.step)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
