"""Public verification schemas.

The models themselves live in ``app.schemas`` so the Claim can embed a
VerificationRecord without circular imports; this module re-exports them as the
verification package's surface (RFC-0002 module layout).
"""

from app.schemas import (
    DowngradeFlag,
    FieldQuote,
    ModelVerdict,
    VerdictType,
    VerificationRecord,
)

__all__ = [
    "DowngradeFlag",
    "FieldQuote",
    "ModelVerdict",
    "VerdictType",
    "VerificationRecord",
]
