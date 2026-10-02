"""Synthetic in-memory extension-owned notes rehearsal, never a SAP connector."""
import copy
import threading

from .engine import digest


class MockNotesTarget:
    def __init__(self):
        self.rows = {}
        self._lock = threading.Lock()

    def checkpoint(self):
        with self._lock:
            return copy.deepcopy(self.rows)

    def restore(self, checkpoint):
        with self._lock:
            self.rows = copy.deepcopy(checkpoint)

    def load(self, rows, *, synthetic, approved, fail_after=None):
        if synthetic is not True or approved is not True:
            raise PermissionError("mock rehearsal needs explicit synthetic fixture approval")
        validated = {}
        for row in rows:
            if set(row) != {"note_id", "request_id", "note", "owner"}:
                raise ValueError("invalid synthetic note fields")
            if not all(isinstance(v, str) and v for v in row.values()):
                raise ValueError("all synthetic note fields must be nonempty strings")
            if row["request_id"] not in {"SYN-PR-001", "SYN-PR-002"}:
                raise ValueError("unresolved synthetic request reference")
            if row["note_id"] in validated:
                raise ValueError("duplicate source note key")
            validated[row["note_id"]] = copy.deepcopy(row)
        with self._lock:
            candidate = copy.deepcopy(self.rows)
            for i, (key, row) in enumerate(sorted(validated.items())):
                if fail_after is not None and i >= fail_after:
                    raise RuntimeError("injected mock load failure; transaction not committed")
                candidate[key] = row
            self.rows = candidate
            return {"rows": len(candidate), "checksum": digest(candidate)}


def rehearsal_demo():
    rows = [{"note_id": "SYN-NOTE-001", "request_id": "SYN-PR-001", "note": "Synthetic delivery note", "owner": "SYN-BUYER"},
            {"note_id": "SYN-NOTE-002", "request_id": "SYN-PR-002", "note": "Synthetic quantity review", "owner": "SYN-BUYER"}]
    target = MockNotesTarget()
    checkpoint = target.checkpoint()
    initial = target.load(rows, synthetic=True, approved=True)
    repeat = target.load(rows, synthetic=True, approved=True)
    expected = {r["note_id"]: r for r in rows}
    reconciled = target.checkpoint() == expected
    target.restore(checkpoint)
    return {"synthetic": True, "target": "in-memory-mock-not-SAP", "network_used": False,
            "erp_data_moved": False, "initial_load": initial, "idempotent_replay": initial == repeat,
            "semantic_reconciliation": reconciled, "rollback_verified": target.checkpoint() == checkpoint,
            "limitations": ["Two fake extension-owned notes only; not a SAP data migration",
                            "No SAP compilation, authorizations, API sequencing, delta capture or deployment verified"]}
