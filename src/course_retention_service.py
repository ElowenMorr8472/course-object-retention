from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .infrai_retention import InfraiClient, InfraiError, provision_retention
from .retention_policy import CourseRetentionRequest, build_retention_rules


def parse_request(body: dict[str, Any]) -> tuple[CourseRetentionRequest, str, str, str]:
    required = ("course_id", "delivery_ends_on", "learner_deadline", "educator_report_due", "bucket", "sweep_url")
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise ValueError(f"missing fields: {', '.join(missing)}")
    course = CourseRetentionRequest(
        course_id=str(body["course_id"]),
        delivery_ends_on=date.fromisoformat(str(body["delivery_ends_on"])),
        learner_deadline=date.fromisoformat(str(body["learner_deadline"])),
        educator_report_due=date.fromisoformat(str(body["educator_report_due"])),
    )
    return course, str(body["bucket"]), str(body["sweep_url"]), str(body.get("cron_expr", "15 2 * * *"))


class RetentionHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/retention-policies":
            self._json(404, {"error": "route not found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            course, bucket, sweep_url, cron_expr = parse_request(json.loads(self.rfile.read(size)))
            rules = build_retention_rules(course, date.today())
            result = provision_retention(
                InfraiClient.from_environment(), bucket, rules, sweep_url, cron_expr, f"course:{course.course_id}"
            )
            self._json(201, {**result, "course_id": course.course_id, "rules": [asdict(rule) for rule in rules]})
        except (ValueError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})
        except InfraiError as error:
            status = error.status if 400 <= error.status < 500 else 502
            self._json(status, {"error": error.code, "detail": error.detail})

    def _json(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    print(f"Course retention service listening on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), RetentionHandler).serve_forever()


if __name__ == "__main__":
    main()
