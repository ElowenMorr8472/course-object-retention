from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CourseRetentionRequest:
    course_id: str
    delivery_ends_on: date
    learner_deadline: date
    educator_report_due: date


@dataclass(frozen=True)
class RetentionRule:
    prefix: str


def build_retention_rules(request: CourseRetentionRequest, today: date) -> list[RetentionRule]:
    """Keep each object class through its last legitimate use, with a one-day floor."""
    milestones = (
        ("delivery", request.delivery_ends_on),
        ("submissions", request.learner_deadline),
        ("reports", request.educator_report_due),
    )
    return [RetentionRule(prefix=f"courses/{request.course_id}/{kind}/") for kind, _ in milestones]
