import tempfile
import unittest
from pathlib import Path

from scripts.build_packages import package_files
from scripts.check_agent_docs import problems


def repo(directory, files):
    root = Path(directory)
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return root, sorted(files)


class AgentDocsTests(unittest.TestCase):
    def test_current_repository_passes(self):
        self.assertEqual(problems(), [])

    def test_agents_md_required(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(problems(*repo(directory, {'README.md': 'x'})), ['AGENTS.md missing'])

    def test_claude_md_must_only_import_sibling_agents_md(self):
        with tempfile.TemporaryDirectory() as directory:
            root, tracked = repo(directory, {'AGENTS.md': '# Guide\n', 'CLAUDE.md': '@AGENTS.md\n',
                                             'plugins/x/AGENTS.md': '# X\n', 'plugins/x/CLAUDE.md': 'Use pytest.\n'})
            self.assertEqual(problems(root, tracked), ['plugins/x/CLAUDE.md must contain only @AGENTS.md'])

    def test_competing_instruction_files_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root, tracked = repo(directory, {'AGENTS.md': '# Guide\n', '.cursorrules': 'x',
                                             '.github/copilot-instructions.md': 'x'})
            self.assertEqual(problems(root, tracked), [
                '.cursorrules duplicates AGENTS.md; move its rules into AGENTS.md',
                '.github/copilot-instructions.md duplicates AGENTS.md; move its rules into AGENTS.md'])

    def test_broken_relative_links_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root, tracked = repo(directory, {'AGENTS.md': '[ok](CONTEXT.md) [web](https://x.test/a.md) [gone](docs/agents/gone.md#top)\n',
                                             'CONTEXT.md': '# Context\n'})
            self.assertEqual(problems(root, tracked), ['AGENTS.md links to missing docs/agents/gone.md'])

    def test_agents_md_line_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root, tracked = repo(directory, {'AGENTS.md': 'line\n' * 151})
            self.assertEqual(problems(root, tracked), ['AGENTS.md has 151 lines; keep it under 150 and disclose detail behind pointers'])

    def test_contributor_process_docs_stay_out_of_packages(self):
        root = Path(__file__).resolve().parent.parent
        packaged = {p.relative_to(root).as_posix() for p in package_files(root)}
        self.assertIn('docs/input-contracts.md', packaged)
        self.assertFalse([p for p in packaged if p.startswith(('docs/agents/', 'docs/adr/'))])


if __name__ == '__main__':
    unittest.main()
