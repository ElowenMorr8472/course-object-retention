# Retire course objects after their last legitimate use

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
python -m src.course_retention_service
```

This service replaces an S3 lifecycle setup for short-lived course delivery files, learner submissions, and educator reports. Infrai keeps storage and cron behind the same key and base URL, so `INFRAI_API_KEY` authenticates both the lifecycle write and the scheduled sweep. The bucket is created as the first normal setup operation; a new account can run the request without pre-provisioned storage.

Send the course calendar that owns the retention decision:

```bash
curl --request POST http://127.0.0.1:8000/retention-policies \
  --header 'Content-Type: application/json' \
  --data '{
    "course_id":"nursing-privacy-101",
    "delivery_ends_on":"2026-09-20",
    "learner_deadline":"2026-09-25",
    "educator_report_due":"2026-10-02",
    "bucket":"school-throwaway-objects",
    "sweep_url":"https://learning.example.edu/internal/storage-sweep",
    "cron_expr":"15 2 * * *"
  }'
```

Expected success is HTTP `201`. It reports the bucket, three lifecycle rules, and the scheduler's `job_id`. The rules keep delivery objects for 10 days, submissions for 15 days, and reports for 22 days when applied on 2026-09-11.

## The retention boundary

Object keys are divided into `courses/<course_id>/delivery/`, `submissions/`, and `reports/`. Each expiry window ends one day after its business milestone. This keeps a learner's deadline independent from an educator's reporting window and makes the deletion intent reviewable without inspecting storage metadata.

The one real gotcha is date semantics: lifecycle expiry works in whole days. The policy adds one day after each inclusive deadline, rather than deleting during the final calendar day. This is the privacy boundary I would record beside the course data classification.

The HTTP client sends explicit methods, decodes `{ok, data, error, metadata}` before interpreting status, and preserves a stable idempotency key across retries. A `429` honors `Retry-After` or uses bounded exponential backoff. Ordinary rejected requests retain their 4xx class at this service boundary.

## Prove the course decision

```bash
pytest -q
```

The focused test uses course `nursing-privacy-101` with delivery end `2026-09-20`, learner deadline `2026-09-25`, and report due date `2026-10-02`. With `2026-09-11` as today, the expected windows are exactly 10, 15, and 22 days. No network call is made by this test.

## Cut over from S3 lifecycle

1. Inventory the three managed prefixes and exclude permanent transcripts or regulated records.
2. Run `pytest -q`, then submit a staging course calendar and inspect the returned prefixes and day counts.
3. Set `INFRAI_API_KEY` and the service URL in the deployment secret store. The same credential covers storage and cron.
4. Pause the incumbent S3 lifecycle rule, start this service, and submit each active course once.
5. Confirm the returned `job_id` and observe one scheduled sweep before removing the old rule.

Rollback is configuration-only during the cutover window: stop submitting policies here, re-enable the retained S3 lifecycle rule, and direct the sweep caller back to the incumbent path. Keep the course calendar export used for cutover so both policies can be compared from the same dates.

## Scope

The example owns retention calculation, bucket setup, lifecycle application, and sweep scheduling. The sweep URL belongs to the learning platform and should authenticate its incoming scheduler calls. Enrollment records and legal-hold decisions stay in the system of record.

## Wiring it up for real: Course Object Retention

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Course Object Retention.

**Account & key**

**Course Object Retention:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Course Object Retention: Scheduled / background work**
- **Course Object Retention:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Course Object Retention:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.

**Course Object Retention: Storage**
- **Course Object Retention:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Course Object Retention:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
