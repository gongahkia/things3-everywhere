"""Errors contain fixed diagnostics, never raw subprocess output or task text."""


class BridgeError(Exception):
    def __init__(self, code: str, message: str, *, outcome: str = "not_attempted"):
        super().__init__(message)
        self.code = code
        self.message = message
        self.outcome = outcome

    def public(self) -> dict:
        return {"code": self.code, "message": self.message,
                "outcome": self.outcome, "retry_safe": False}


def unexpected_error() -> BridgeError:
    return BridgeError("INTERNAL_ERROR", "The operation failed. No automatic retry was made.",
                       outcome="unknown")

