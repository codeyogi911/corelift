"""Check that AGENTS.md is the single source of agent instructions and its links resolve."""
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
MAX_LINES = 150
COMPETING = ('.cursorrules', '.windsurfrules', 'GEMINI.md', '.github/copilot-instructions.md')
LINKED = re.compile(r'(?:^|/)(?:AGENTS|CONTEXT)\.md$|^docs/(?:agents|adr)/.*\.md$')
LINK = re.compile(r'\]\(([^)\s]+)\)')


def tracked_files(root=ROOT):
    return [name for name in subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0') if name]


def problems(root=ROOT, tracked=None):
    tracked = tracked_files(root) if tracked is None else tracked
    if 'AGENTS.md' not in tracked:
        return ['AGENTS.md missing']
    found = []
    for name in tracked:
        path = PurePosixPath(name)
        if path.name == 'CLAUDE.md' and (root / name).read_text().strip() != '@AGENTS.md':
            found.append(f'{name} must contain only @AGENTS.md')
        if name in COMPETING:
            found.append(f'{name} duplicates AGENTS.md; move its rules into AGENTS.md')
        if LINKED.search(name):
            for target in LINK.findall((root / name).read_text()):
                target = target.split('#')[0]
                if target and '://' not in target and not target.startswith('mailto:') and not (root / path.parent / target).exists():
                    found.append(f'{name} links to missing {target}')
    lines = len((root / 'AGENTS.md').read_text().splitlines())
    if lines > MAX_LINES:
        found.append(f'AGENTS.md has {lines} lines; keep it under {MAX_LINES} and disclose detail behind pointers')
    return found


def main():
    found = problems()
    for problem in found:
        print(f'FAIL: {problem}', file=sys.stderr)
    if found:
        sys.exit(1)
    print('PASS: AGENTS.md is the single agent guide; CLAUDE.md files are pointers; agent doc links resolve')


if __name__ == '__main__':
    main()
