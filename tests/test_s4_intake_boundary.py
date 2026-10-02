"""Synthetic-only checks for the next read-only S/4 intake boundary."""
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from corelift.capabilities import CapabilityDenied, require_capability
from corelift.contracts import ROOT
from corelift.engine import assess
from corelift.workspace import snapshot


class S4IntakeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.inventory = json.loads((ROOT / 'examples/synthetic-ecc/inventory.json').read_text())
        self.evidence = json.loads((ROOT / 'examples/synthetic-ecc/api-evidence.json').read_text())
        self.sources = json.loads((ROOT / 'evidence/sources.json').read_text())
        self.inventory['source_system'] = {'family': 'S4HANA', 'edition': 'on-premise', 'release': '2021', 'fps': 'FPS01'}

    def test_source_and_target_are_distinct_without_connection(self):
        with patch.object(socket, 'socket', side_effect=AssertionError('unexpected network')):
            result = assess(self.inventory, self.evidence, self.sources)
        self.assertEqual(result['source_system'], self.inventory['source_system'])
        self.assertEqual(result['target'], self.inventory['target'])
        self.assertNotEqual(result['source_system']['release'], result['target']['release'])
        self.assertEqual(result['run_record']['connector'], 'offline-exports')
        self.assertFalse(result['run_record']['network_used'])
        self.assertFalse(result['run_record']['customer_writes'])

    def test_customer_shaped_s4_evidence_stays_unverified(self):
        # Fictional fixture bytes only; changing the provenance shape grants no trust.
        self.inventory['synthetic'] = self.evidence['synthetic'] = False
        self.evidence['snapshot_revision'] = 'a' * 40
        for item in self.evidence['objects']:
            item['verification'] = 'exported-unverified'
        result = assess(self.inventory, self.evidence, self.sources)
        for decision in result['decisions']:
            self.assertEqual(decision['approval_state'], 'not-approved')
            for dependency in decision['dependencies']:
                self.assertEqual(dependency['state'], 'unknown')
        self.assertEqual(result['migration_plan']['state'], 'draft-not-executable')

    def test_s4_import_does_not_inherit_demo_or_connection(self):
        report = assess(self.inventory, self.evidence, self.sources)
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'synthetic-s4-report.json'
            file.write_text(json.dumps(report))
            value = snapshot(file)
        self.assertEqual(value['mode'], 'imported')
        self.assertIsNone(value['rehearsal'])
        self.assertTrue(all(c['status'] == 'not-connected' for c in value['connections'] if c['id'] in {'sap', 'btp'}))

    def test_declared_environment_access_and_approval_never_unlock_provider(self):
        for environment in ('development', 'qa', 'production', 'unknown'):
            for name in ('sap-adt-read', 'sap-atc-read', 'sap-rfc', 'sap-odata', 'sap-run-atc', 'sap-enable-monitor'):
                with self.subTest(environment=environment, capability=name):
                    with self.assertRaises(CapabilityDenied):
                        require_capability(name, approval={'environment': environment, 'approved': True, 'access': 'existing-adt'})


if __name__ == '__main__': unittest.main()
