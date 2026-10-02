"""Read-only workspace snapshots. Imported provenance remains an assertion."""
import argparse
import json
import sys
from pathlib import Path

from .__main__ import read_json
from .contracts import ROOT, contract
from .engine import assess, digest
from .rehearsal import rehearsal_demo


def snapshot(assessment_path=None):
    if assessment_path is None:
        assessment = assess(read_json(ROOT / 'examples/synthetic-ecc/inventory.json'),
                            read_json(ROOT / 'examples/synthetic-ecc/api-evidence.json'),
                            read_json(ROOT / 'evidence/sources.json'))
        mode, label, rehearsal = 'demo', 'Synthetic purchasing portfolio', rehearsal_demo()
    else:
        assessment = read_json(assessment_path)
        contract('assessment', assessment)
        mode, label, rehearsal = 'imported', Path(assessment_path).name, None
    value = {
        'workspace_version': '1.0.0', 'read_only': True,
        'mode': mode, 'label': label,
        'snapshot_hash': digest(assessment), 'assessment': assessment,
        'rehearsal': rehearsal,
        'provenance_notice': ('Computed from bundled synthetic exports; no SAP system connected.' if mode == 'demo'
                              else 'Imported report assertions; CoreLift has not independently verified this report or its run record.'),
        'connections': [{'id': 'offline-export', 'label': 'Local assessment data', 'status': 'available'},
                        {'id': 'sap', 'label': 'SAP ERP', 'status': 'not-connected'},
                        {'id': 'btp', 'label': 'SAP BTP', 'status': 'not-connected'}],
    }
    contract('workspace', value)
    return value


def main():
    parser = argparse.ArgumentParser(description='Emit a validated read-only CoreLift workspace snapshot')
    parser.add_argument('--assessment', help='Explicit local assessment JSON to inspect (no upload)')
    args = parser.parse_args()
    try:
        print(json.dumps(snapshot(args.assessment), sort_keys=True))
    except (OSError, ValueError, RecursionError):
        print('CoreLift workspace: assessment could not be read or did not match the supported schema.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
