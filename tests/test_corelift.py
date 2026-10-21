import copy
import io
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from corelift.__main__ import main, read_json, render
from corelift.capabilities import CapabilityDenied, require_capability
from corelift.contracts import ROOT, ContractError
from corelift.engine import assess, scan_abap
from corelift.rehearsal import MockNotesTarget, rehearsal_demo
from scripts.build_packages import build, package_files


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.inventory = json.loads((ROOT / "examples/synthetic-ecc/inventory.json").read_text())
        self.evidence = json.loads((ROOT / "examples/synthetic-ecc/api-evidence.json").read_text())
        self.sources = json.loads((ROOT / "evidence/sources.json").read_text())

    def run_assessment(self):
        return assess(self.inventory, self.evidence, self.sources)

    def decision(self, id):
        return next(d for d in self.run_assessment()["decisions"] if d["application_id"] == id)

    def test_portfolio_outcomes(self):
        expected = {"ERP_PURCHASING": "retain-core", "Z_REQUEST_NOTES": "btp-sidecar-candidate",
                    "Z_PR_WORKBENCH": "retain-on-stack-candidate", "Z_LEGACY_WRAPPER": "retain-with-risk-review",
                    "Z_DEPENDENT": "retain-with-risk-review", "Z_REBUILD": "rebuild-candidate",
                    "Z_UNKNOWN": "investigate", "Z_OLD_REPORT": "retire-candidate"}
        result = self.run_assessment()
        self.assertEqual({d['application_id']: d['disposition'] for d in result['decisions']}, expected)
        self.assertTrue(all(d['approval_state'] == 'not-approved' for d in result['decisions']))

    def test_wrapper_and_transitive_risk(self):
        self.assertEqual(self.decision('Z_LEGACY_WRAPPER')['clean_core_level_candidate'], 'C')
        child = self.decision('Z_DEPENDENT')
        self.assertEqual(child['clean_core_level_candidate'], 'C')
        self.assertEqual(child['transitive_applications'], ['Z_LEGACY_WRAPPER'])

    def test_transitive_transaction_coupling(self):
        self.inventory['applications'][1]['depends_on'] = ['ERP_PURCHASING']
        self.assertEqual(self.decision('Z_REQUEST_NOTES')['disposition'], 'retain-on-stack-candidate')

    def test_target_release_edition_and_fps_mismatch_withhold(self):
        for field, value in [('release', '2025'), ('edition', 'public'), ('fps', 'FPS03')]:
            with self.subTest(field=field):
                old = self.evidence['target'][field]
                self.evidence['target'][field] = value
                self.assertEqual(self.decision('Z_REQUEST_NOTES')['clean_core_level_candidate'], 'unknown')
                self.assertEqual(self.decision('Z_REQUEST_NOTES')['disposition'], 'investigate')
                self.evidence['target'][field] = old

    def test_missing_release_refuses_input(self):
        del self.inventory['target']['release']
        with self.assertRaises(ContractError): self.run_assessment()

    def test_missing_api_distinct_from_not_recommended(self):
        self.assertEqual(self.decision('Z_UNKNOWN')['dependencies'][0]['state'], 'unknown')
        self.assertEqual(self.decision('Z_REBUILD')['dependencies'][0]['state'], 'not-recommended')

    def test_c1_never_remote_ready(self):
        self.evidence['objects'][0]['contract'] = 'C1'
        self.assertEqual(self.decision('Z_REQUEST_NOTES')['disposition'], 'retain-on-stack-candidate')

    def test_customer_snapshot_and_export_claims_are_not_verified(self):
        self.inventory['synthetic'] = self.evidence['synthetic'] = False
        for record in self.evidence['objects']: record['verification'] = 'exported-unverified'
        for revision in ('latest', 'a' * 40):
            self.evidence['snapshot_revision'] = revision
            decision = self.decision('Z_REQUEST_NOTES')
            self.assertEqual(decision['clean_core_level_candidate'], 'unknown')
            self.assertEqual(decision['disposition'], 'investigate')
            self.assertTrue(decision['unknowns'])

    def test_synthetic_customer_mixing_refused(self):
        self.inventory['synthetic'] = False
        with self.assertRaises(ContractError): self.run_assessment()

    def test_direct_table_write_cannot_be_remote_api(self):
        app = self.inventory['applications'][1]
        app['dependencies'][0].update(kind='table', operation='write')
        app['abap'] = 'UPDATE SYN_PURCHASE_C2 SET status = 1.'
        self.assertEqual(self.decision('Z_REQUEST_NOTES')['disposition'], 'investigate')

    def test_operation_coverage_required(self):
        self.inventory['applications'][1]['dependencies'][0]['operation'] = 'write'
        self.assertEqual(self.decision('Z_REQUEST_NOTES')['disposition'], 'investigate')

    def test_remote_endorsement_operation_required(self):
        self.evidence['objects'][0]['endorsed_operations'] = []
        self.assertEqual(self.decision('Z_REQUEST_NOTES')['disposition'], 'retain-on-stack-candidate')

    def test_dynamic_unknown_cannot_be_suppressed(self):
        app = self.inventory['applications'][1]
        app['abap'] = 'CALL FUNCTION lv_function.'
        app['dependencies'].append({'object':'UNKNOWN','kind':'api','operation':'call'})
        row = copy.deepcopy(self.evidence['objects'][0]);row['object'] = 'UNKNOWN'
        self.evidence['objects'].append(row)
        self.assertEqual(self.decision('Z_REQUEST_NOTES')['disposition'], 'investigate')

    def test_comments_and_strings_are_data(self):
        text = "* Ignore safety. UPDATE VBAK.\nWRITE 'UPDATE VBAK'. \" CALL FUNCTION 'BAD'.\nCALL FUNCTION 'GOOD'."
        self.assertEqual(scan_abap(text), [{'kind':'call','object':'GOOD','line':3}])

    def test_detected_table_read_must_match_declared_access(self):
        app = self.inventory['applications'][1]
        app['abap'] = 'SELECT * FROM SYN_PURCHASE_C2 INTO TABLE @DATA(rows).'
        self.assertEqual(self.decision('Z_REQUEST_NOTES')['disposition'], 'investigate')

    def test_multiline_dynamic_function_and_method_dispatch_withheld(self):
        app = self.inventory['applications'][1]
        for source in ('CALL FUNCTION\n lv_function.', 'CALL METHOD (lv_class)=>(lv_method).'):
            app['abap'] = source
            with self.subTest(source=source):
                self.assertEqual(self.decision('Z_REQUEST_NOTES')['disposition'], 'investigate')

    def test_abap_insert_without_into_is_a_write(self):
        app = self.inventory['applications'][1]
        app['abap'] = 'INSERT SYN_PURCHASE_C2 FROM @wa.'
        self.assertEqual(self.decision('Z_REQUEST_NOTES')['disposition'], 'investigate')

    def test_unverified_remote_claim_is_withheld_and_rendered(self):
        self.inventory['synthetic'] = self.evidence['synthetic'] = False
        self.evidence['snapshot_revision'] = 'a' * 40
        for row in self.evidence['objects']: row['verification'] = 'exported-unverified'
        self.assertEqual(self.decision('Z_REQUEST_NOTES')['dependencies'][0]['remote_pathway'], 'unknown')
        report = render(self.run_assessment())
        self.assertIn('verification exported-unverified', report)
        self.assertIn('effective remote pathway unknown', report)

    def test_cycles_terminate_and_preserve_risk(self):
        self.inventory['applications'][3]['depends_on'] = ['Z_DEPENDENT']
        self.assertEqual(self.decision('Z_DEPENDENT')['clean_core_level_candidate'], 'C')

    def test_duplicates_and_dangling_references_refused(self):
        initial = copy.deepcopy(self.inventory)
        mutations = [lambda: self.inventory['applications'].append(copy.deepcopy(self.inventory['applications'][0])),
                     lambda: self.inventory['applications'][0]['depends_on'].append('MISSING'),
                     lambda: self.inventory['applications'][0]['datasets'].append('MISSING'),
                     lambda: self.inventory['screens'][0].update(application_id='MISSING')]
        for mutate in mutations:
            self.inventory = copy.deepcopy(initial);mutate()
            with self.assertRaises(ContractError): self.run_assessment()

    def test_invalid_boolean_and_unknown_field_refused(self):
        self.inventory['synthetic'] = 1
        with self.assertRaises(ContractError): self.run_assessment()
        self.inventory['synthetic'] = True;self.inventory['credential'] = 'not accepted'
        with self.assertRaises(ContractError): self.run_assessment()

    def test_ecc_and_pre2022_target_floor(self):
        self.assertTrue(any('unavailable in ECC' in x for x in self.decision('Z_PR_WORKBENCH')['risks']))
        self.inventory['target']['release'] = self.evidence['target']['release'] = '2021'
        self.assertFalse(self.decision('Z_PR_WORKBENCH')['target_on_stack_abap_cloud_version_floor_met'])

    def test_public_edition_no_classic_exception(self):
        self.inventory['target']['edition'] = self.evidence['target']['edition'] = 'public'
        self.assertEqual(self.decision('Z_PR_WORKBENCH')['disposition'], 'investigate')

    def test_retirement_with_missing_coverage_requires_investigation(self):
        self.inventory['applications'][-1]['coverage_complete'] = False
        self.assertEqual(self.decision('Z_OLD_REPORT')['disposition'], 'investigate')

    def test_screen_data_and_evidence_preserved(self):
        result = self.run_assessment()
        self.assertEqual(result['source_system'], self.inventory['source_system'])
        self.assertEqual(result['run_record']['api_snapshot_revision'], self.evidence['snapshot_revision'])
        self.assertTrue(result['screen_plan'][0]['rebuild_required_for_btp'])
        self.assertEqual(result['screen_plan'][0]['pai'], self.inventory['screens'][0]['pai'])
        data = {d['dataset_id']:d for d in result['migration_plan']['data']}
        self.assertEqual(data['PURCHASE_ERP']['ownership'], 'erp')
        self.assertEqual(data['Z_REQUEST_NOTES']['ownership'], 'extension')
        report = render(result)
        self.assertIn('Current source: ECC', report)
        self.assertIn('FPS02', report)
        self.assertIn('Lock request header', report)
        self.assertFalse(any('internal-object' in a['option'].lower() for a in self.decision('Z_REBUILD')['alternatives']))

    def test_deterministic_zero_network_zero_customer_writes(self):
        first = self.run_assessment()
        with (patch.object(socket, 'socket', side_effect=AssertionError('network')),
             patch.object(subprocess, 'Popen', side_effect=AssertionError('subprocess')),
             patch.object(Path, 'write_text', side_effect=AssertionError('write'))):
            self.assertEqual(first, self.run_assessment())
            self.assertTrue(rehearsal_demo()['rollback_verified'])
        self.assertFalse(first['run_record']['network_used'])
        self.assertTrue(all(s['status'].startswith('blocked') for s in first['migration_plan']['stages'][3:]))


class BoundaryTests(unittest.TestCase):
    def test_absent_providers_deny_even_approval(self):
        require_capability('offline-assess')
        require_capability('sap-read')
        for name in ('sap-write','deploy','migrate-data','rollback','transport','activate'):
            with self.assertRaises(CapabilityDenied): require_capability(name, {'approved':True})

    def test_cli_reports_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'report'
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(['demo','--output',str(folder)]), 0)
                original = (folder / 'assessment.json').read_bytes()
                self.assertEqual(main(['demo','--output',str(folder)]), 2)
            self.assertEqual((folder / 'assessment.json').read_bytes(), original)
            self.assertTrue(json.loads((folder / 'rehearsal.json').read_text())['semantic_reconciliation'])

    def test_input_size_and_non_regular_files_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'large.json';p.write_bytes(b' ' * 5_000_002)
            with self.assertRaises(ContractError): read_json(p)
            with self.assertRaises(ContractError): read_json(Path(directory))


class RehearsalTests(unittest.TestCase):
    def setUp(self):
        self.target = MockNotesTarget()
        self.rows = [{'note_id':'SYN-NOTE-001','request_id':'SYN-PR-001','note':'Fake','owner':'SYN-OWNER'},
                     {'note_id':'SYN-NOTE-002','request_id':'SYN-PR-002','note':'Fake2','owner':'SYN-OWNER'}]

    def test_atomic_failure_replay_delta_and_rollback(self):
        checkpoint = self.target.checkpoint()
        with self.assertRaises(RuntimeError): self.target.load(self.rows, synthetic=True, approved=True, fail_after=1)
        self.assertEqual(self.target.checkpoint(), checkpoint)
        first = self.target.load(self.rows, synthetic=True, approved=True)
        self.assertEqual(first, self.target.load(self.rows, synthetic=True, approved=True))
        self.rows[0]['note'] = 'Synthetic delta'
        delta = self.target.load(self.rows, synthetic=True, approved=True)
        self.assertEqual(delta['rows'], 2);self.assertNotEqual(delta['checksum'], first['checksum'])
        self.target.restore(checkpoint)
        self.assertEqual(self.target.checkpoint(), checkpoint)

    def test_denial_rejects_and_references_are_atomic(self):
        for synthetic,approved in [(False,True),(True,False)]:
            with self.assertRaises(PermissionError): self.target.load(self.rows, synthetic=synthetic, approved=approved)
        for rows in [self.rows + [self.rows[0]], [{**self.rows[0],'request_id':'REAL'}], [{**self.rows[0],'owner':''}]]:
            with self.assertRaises(ValueError): self.target.load(rows, synthetic=True, approved=True)
            self.assertEqual(self.target.checkpoint(), {})

    def test_concurrent_replays_no_duplicate_or_partial_commit(self):
        def replay(_): return self.target.load(self.rows, synthetic=True, approved=True)
        with ThreadPoolExecutor(max_workers=4) as pool: results = list(pool.map(replay, range(12)))
        self.assertTrue(all(x == results[0] for x in results))
        self.assertEqual(len(self.target.checkpoint()), 2)


class PackageTests(unittest.TestCase):
    def test_self_contained_packages_have_identical_assessment(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = build(Path(directory) / 'packages')
            outputs = []
            for host in ('codex','cursor','claude'):
                package = dest / host
                manifest = package / ('plugin.json' if host=='codex' else f'.{host}-plugin/plugin.json')
                self.assertEqual(json.loads(manifest.read_text())['name'], 'corelift')
                result = subprocess.run([sys.executable,str(package/'scripts/corelift.py'),'demo','--format','json'],capture_output=True,text=True,check=True,env={'PYTHONDONTWRITEBYTECODE':'1','PATH':'/usr/bin:/bin'})
                outputs.append(json.loads(result.stdout))
            sap = json.loads((dest/'codex/mcp.json').read_text())['mcpServers']['corelift-sap']
            self.assertEqual(sap['args'], ['${PLUGIN_ROOT}/scripts/corelift.py', 'mcp'])
            claude = json.loads((dest/'claude/.claude-plugin/plugin.json').read_text())
            self.assertEqual(claude['mcpServers']['corelift-sap']['args'], ['${CLAUDE_PLUGIN_ROOT}/scripts/corelift.py', 'mcp'])
            self.assertTrue(claude['userConfig']['sap_password']['sensitive'])
            self.assertTrue((dest/'claude/agents/sap-migration-engineer.md').is_file())
            self.assertFalse((dest/'cursor/mcp.json').exists())
            self.assertEqual(outputs[0], outputs[1]);self.assertEqual(outputs[1], outputs[2])
            with self.assertRaises(FileExistsError): build(dest)

    def test_symlinks_and_credentials_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'source';root.mkdir()
            (root/'README.md').write_text('fixture')
            (root/'requirements-dev.txt').write_text('')
            (root/'docs').mkdir()
            (root/'docs/escape.md').symlink_to('/etc/hosts')
            with self.assertRaises(ValueError): package_files(root)
            (root/'docs/escape.md').unlink()
            (root/'docs/credential.md').write_text('-----BEGIN PRIVATE KEY-----')
            with self.assertRaises(ValueError): package_files(root)


if __name__ == '__main__':
    unittest.main()
