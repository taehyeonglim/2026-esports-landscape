"""Privacy-safe contracts for the school esports data pipeline."""

from .models import (
    BudgetStatus,
    CandidateStatus,
    PublicationStatus,
    Relation,
    ReviewStatus,
    SubjectKind,
)
from .pii import PiiFinding, PiiKind, PiiScanResult, scan_text, scan_url

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "BudgetStatus",
    "CandidateStatus",
    "PublicationStatus",
    "Relation",
    "ReviewStatus",
    "SubjectKind",
    "PiiFinding",
    "PiiKind",
    "PiiScanResult",
    "scan_text",
    "scan_url",
]
