"""Check public source/package privacy and required redistribution notices."""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_PATH = re.compile(r'/(?:Users|home)/[A-Za-z0-9_.-]+/|[A-Z]:\\\\Users\\\\[^\\\\]+')
SECRET = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=]{32,})')


def check_files(files):
    for file in files:
        if file.is_symlink():
            raise ValueError(f'symlink in release: {file.name}')
        if file.name in {'.env', 'auth.json'} or file.suffix in {'.pem', '.key'}:
            raise ValueError(f'forbidden release file: {file.name}')
        # Binary files (screenshots) are scanned too: metadata chunks can carry paths.
        text = file.read_bytes().decode('utf-8', errors='replace')
        if PRIVATE_PATH.search(text) or SECRET.search(text):
            raise ValueError(f'private path or secret-like value in {file.name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packages', type=Path, required=True)
    args = parser.parse_args()
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    check_files([ROOT / name for name in tracked if name])
    for host in ('codex', 'cursor', 'claude'):
        root = args.packages / host
        check_files([p for p in root.rglob('*') if p.is_file()])
        for name in ('LICENSE', 'NOTICE', 'THIRD_PARTY.md'):
            assert (root / name).is_file(), f'missing {host} {name}'
        assert 'Apache License' in (root / 'LICENSE').read_text()
    root = args.packages / 'codex/ui/generated'
    inventory = json.loads((root / 'bundle-licenses.json').read_text())
    notice = (root / 'THIRD_PARTY_NOTICES.txt').read_text()
    assert inventory and len({(x['name'], x['version']) for x in inventory}) == len(inventory)
    for item in inventory:
        assert item['license'] in {'MIT', 'ISC', 'BSD-2-Clause', 'BSD-3-Clause', 'Apache-2.0'}, item['name']
        assert item['notice_files'] and f"{item['name']}@{item['version']}" in notice
    assert all('SAP' not in x['name'] for x in inventory)
    print(f'PASS: public source/package privacy patterns; license files for all hosts; notices for {len(inventory)} bundled dependencies')


if __name__ == '__main__':
    main()
