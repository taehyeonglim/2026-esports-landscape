"""Stable domain values shared by the data pipeline."""

from __future__ import annotations

from enum import Enum


class SubjectKind(str, Enum):
    """Kinds of entities that can be represented in the pipeline."""

    SCHOOL = "school"
    REGION = "region"
    ORGANIZATION = "organization"
    VENUE = "venue"
    PROGRAM = "program"
    UNIVERSITY = "university"


class CandidateStatus(str, Enum):
    """Lifecycle state of a candidate before publication."""

    PRIVATE = "private"
    REVIEW = "review"
    REJECTED = "rejected"
    REVERIFICATION_PENDING = "reverification_pending"


class PublicationStatus(str, Enum):
    """Confidence level of published information."""

    VERIFIED = "verified"
    PROVISIONAL = "provisional"


class Relation(str, Enum):
    """How a source subject relates to the current subject."""

    PRIMARY = "primary"
    RELATED = "related"


class ReviewStatus(str, Enum):
    """State of a review record."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"


class BudgetStatus(str, Enum):
    """Outcome of a privacy or publication budget check."""

    PASS = "pass"
    SOFT = "soft"
    HARD = "hard"
