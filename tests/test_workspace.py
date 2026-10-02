import copy
import json
import tempfile
import unittest
from pathlib import Path
from corelift.contracts import ROOT, ContractError, contract, validate
from corelift.workspace import snapshot
from scripts.build_packages import build


class WorkspaceTests(unittest.TestCase):
    def test_demo_and_imported_provenance_never_conflate(self):
        demo = snapshot()
        self.assertEqual(demo['mode'], 'demo')
        self.assertIsNotNone(demo['rehearsal'])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'local.json'
            path.write_text(json.dumps(demo['assessment']))
            imported = snapshot(path)
            self.assertEqual(imported['mode'], 'imported')
            self.assertIsNone(imported['rehearsal'])
            self.assertEqual(imported['snapshot_hash'], demo['snapshot_hash'])
            self.assertIn('assertions', imported['provenance_notice'])
            path.write_text('{}')
            with self.assertRaises(ContractError): snapshot(path)

    def test_workspace_schema_rejects_type_and_shape_substitutions(self):
        value = snapshot()
        for field, invalid in [('read_only', 1), ('workspace_version', '99'), ('rehearsal', {'passed': True})]:
            modified = copy.deepcopy(value)
            modified[field] = invalid
            with self.assertRaises(ContractError): contract('workspace', modified)
        with self.assertRaises(ContractError): validate(0, {'const': False})
        validate(None, {'anyOf': [{'type': 'null'}, {'type': 'object'}]})

    @unittest.skipUnless((ROOT / "ui/generated/server.mjs").is_file(), "optional UI not built; run npm run build:ui")
    def test_optional_ui_build_requires_real_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = build(Path(folder) / 'packages', with_ui=True)
            config = json.loads((destination / 'codex/mcp.json').read_text())
            self.assertEqual(config['mcpServers']['corelift-workspace']['args'], ['${PLUGIN_ROOT}/ui/generated/server.mjs'])
            self.assertTrue((destination / 'codex/ui/generated/workspace.html').is_file())
            for host in ('cursor', 'claude'):
                self.assertFalse((destination / host / 'mcp.json').exists())
                self.assertFalse((destination / host / 'ui').exists())

if __name__ == '__main__': unittest.main()
