"""Provider boundary: no external provider is implemented in this prototype."""


class CapabilityDenied(RuntimeError):
    pass


def require_capability(name, approval=None):
    if name == "offline-assess":
        return
    raise CapabilityDenied(f"{name}: provider not implemented; no operation performed. "
                           "Future providers require target/system/operation/artifact-bound approval, "
                           "checkpoint, rollback and verification evidence.")
