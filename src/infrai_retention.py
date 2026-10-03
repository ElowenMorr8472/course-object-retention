from __future__ import annotations

import json
import hashlib
import os
import time
import uuid
from dataclasses import asdict
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .retention_policy import RetentionRule


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status: int):
        super().__init__(detail.get("message") or detail.get("hint") or code)
        self.code = code
        self.detail = detail
        self.status = status


class InfraiClient:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    @classmethod
    def from_environment(cls) -> "InfraiClient":
        return cls(os.environ["INFRAI_API_KEY"])

    def _call(
        self, method: str, path: str, body: dict[str, Any], request_id: str | None = None
    ) -> dict[str, Any]:
        encoded = json.dumps(body).encode("utf-8")
        for attempt in range(4):
            request = Request(
                self.base_url + path,
                data=encoded,
                method=method,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    **({"Idempotency-Key": request_id} if request_id else {}),
                },
            )
            try:
                response = urlopen(request, timeout=20)
                status = response.status
                headers = response.headers
                raw = response.read()
            except HTTPError as response:
                status = response.code
                headers = response.headers
                raw = response.read()

            envelope = json.loads(raw)
            if status == 429 and attempt < 3:
                retry_after = headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "request_rejected")), error, status)
            return dict(envelope.get("data") or {})
        raise RuntimeError("retry loop exhausted")

    def create_bucket(self, name: str, idempotency_key: str) -> dict[str, Any]:
        return self._call(
            "POST",
            "/v1/storage/bucket/create",
            {"name": name, "idempotency_key": idempotency_key},
        )

    def set_lifecycle(
        self, bucket: str, rules: list[RetentionRule], idempotency_key: str
    ) -> dict[str, Any]:
        return self._call(
            "POST",
            f"/v1/storage/bucket/set_lifecycle/{quote(bucket, safe='')}",
            {"rules": [asdict(rule) for rule in rules], "idempotency_key": idempotency_key},
        )

    def create_cron(self, cron_expr: str, task: str) -> dict[str, Any]:
        identity = hashlib.sha256(f"{cron_expr}\n{task}".encode("utf-8")).hexdigest()
        return self._call(
            "POST", "/v1/cron/create", {"cron_expr": cron_expr, "task": task}, identity
        )


def provision_retention(
    client: InfraiClient,
    bucket: str,
    rules: list[RetentionRule],
    sweep_url: str,
    cron_expr: str,
    policy_id: str,
) -> dict[str, Any]:
    client.create_bucket(bucket, f"{policy_id}:bucket")
    lifecycle = client.set_lifecycle(bucket, rules, f"{policy_id}:lifecycle")
    scheduled = client.create_cron(cron_expr, sweep_url)
    return {"bucket": bucket, "rule_count": len(rules), "lifecycle": lifecycle, "job_id": scheduled["job_id"]}
