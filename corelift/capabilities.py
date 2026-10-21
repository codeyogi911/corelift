"""Provider boundary. Reads are allowed; every SAP/BTP write fails closed.

- offline-assess: deterministic engine over local JSON.
- network-evidence: download SAP's public Cloudification Repository at one commit.
- sap-read: only bound to one system the user connected themselves
  (approval {"system": <url>}); the ADT client then refuses any request
  outside its read-only allowlist (corelift/sap/adt.py).
"""

ALLOWED = {"offline-assess", "network-evidence"}


class CapabilityDenied(RuntimeError):
    pass


def require_capability(name, approval=None):
    if name in ALLOWED:
        return
    if name == "sap-read" and isinstance(approval, dict) and approval.get("system"):
        return
    raise CapabilityDenied(f"{name}: provider not implemented; no operation performed. "
                           "Future providers require target/system/operation/artifact-bound approval, "
                           "checkpoint, rollback and verification evidence.")
