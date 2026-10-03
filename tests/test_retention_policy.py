from datetime import date

from src.retention_policy import CourseRetentionRequest, build_retention_rules


def test_deadlines_produce_distinct_domain_retention_windows() -> None:
    request = CourseRetentionRequest(
        course_id="nursing-privacy-101",
        delivery_ends_on=date(2026, 9, 20),
        learner_deadline=date(2026, 9, 25),
        educator_report_due=date(2026, 10, 2),
    )

    rules = build_retention_rules(request, today=date(2026, 9, 11))

    assert [rule.prefix for rule in rules] == [
        "courses/nursing-privacy-101/delivery/",
        "courses/nursing-privacy-101/submissions/",
        "courses/nursing-privacy-101/reports/",
    ]


def test_past_deadline_still_builds_rules() -> None:
    request = CourseRetentionRequest("course-7", date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3))
    assert len(build_retention_rules(request, date(2026, 9, 11))) == 3
