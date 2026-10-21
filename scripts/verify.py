"""Run the CoreLift verification gate. The same command runs locally and in CI."""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def steps(packages, quick):
    yield 'agent docs', [PY, 'scripts/check_agent_docs.py']
    yield 'python tests', [PY, '-m', 'unittest', 'discover', '-s', 'tests']
    if quick:
        return
    npm = shutil.which('npm') or 'npm'
    if not (ROOT / 'node_modules').is_dir():
        yield 'npm ci', [npm, 'ci']
    yield 'ui build', [npm, 'run', 'build:ui']
    yield 'ui tests', [npm, 'run', 'test:ui']
    yield 'schemas', [PY, 'scripts/check_schemas.py']
    yield 'packages', [PY, 'scripts/build_packages.py', '--with-ui', '--output', str(packages)]
    yield 'release', [PY, 'scripts/check_release.py', '--packages', str(packages)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quick', action='store_true', help='agent docs and Python tests only, for inner red-green slices')
    args = parser.parse_args()
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    with tempfile.TemporaryDirectory(prefix='corelift-verify-') as scratch:
        for name, command in steps(Path(scratch) / 'packages', args.quick):
            started = time.monotonic()
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            if result.returncode:
                print(result.stdout + result.stderr)
                if name == 'schemas' and 'jsonschema' in result.stderr:
                    print('Install the dev dependency: python3 -m pip install -r requirements-dev.txt')
                print(f'RED: {name} failed: {" ".join(command)}')
                sys.exit(1)
            print(f'ok   {name} ({time.monotonic() - started:.1f}s)')
    print('GREEN: quick gate passed; run the full gate before review' if args.quick else 'GREEN: full gate passed')


if __name__ == '__main__':
    main()
