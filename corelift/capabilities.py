"""Provider boundary. Reads are allowed; every SAP/BTP write fails closed.

- offline-assess: deterministic engine over local JSON.
- sap-read: the ADT client, which itself refuses any request outside its
  read-only allowlist (corelift/sap/adt.py).
- network-evidence: download SAP's public Cloudification Repository at one commit.
"""

ALLOWED = {"offline-assess", "sap-read", "network-evidence"}


class CapabilityDenied(RuntimeError):
    pass


def require_capability(name, approval=None):
    if name in ALLOWED:
        return
    raise CapabilityDenied(f"{name}: provider not implemented; no operation performed. "
                           "Future providers require target/system/operation/artifact-bound approval, "
                           "checkpoint, rollback and verification evidence.")
