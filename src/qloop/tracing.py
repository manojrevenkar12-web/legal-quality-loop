"""Traces in Langfuse's ingestion format: one trace per answer, a span or generation per pipeline step, and a score
per judge verdict and check, all redacted. Written to JSONL always; sent to a Langfuse server when LANGFUSE_HOST,
LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set."""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

from qloop.privacy import Redactor
from qloop.runner import Item, Run


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _event(kind: str, body: dict) -> dict:
    return {"id": str(uuid.uuid4()), "timestamp": _now(), "type": kind, "body": body}


def events(run: Run, run_name: str, redactor: Redactor) -> list[dict]:
    out: list[dict] = []
    for item in run.items:
        out.extend(item_events(item, run, run_name, redactor))
    return out


def item_events(item: Item, run: Run, run_name: str, redactor: Redactor) -> list[dict]:
    trace_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{run_name}/{run.config.key()}/{item.task.id}"))
    ev = [_event("trace-create", {
        "id": trace_id, "name": f"{item.task.family}:{item.task.topic}", "sessionId": run_name,
        "input": redactor.value({"prompt": item.task.prompt, "documents": [d.text for d in item.task.documents]}),
        "output": redactor.text(item.answer),
        "metadata": {"config": run.config.model_dump(), "config_key": run.config.key(), "jurisdiction": item.task.jurisdiction,
                     "language": item.task.language, "split": item.task.split},
        "tags": [item.task.family, item.task.jurisdiction, run.config.model]})]
    for step in item.steps:
        body = {"id": str(uuid.uuid4()), "traceId": trace_id, "name": step["name"],
                "input": redactor.value(step.get("input")), "output": redactor.value(step.get("output"))}
        if step["name"] == "generate":
            body.update({"model": step["model"], "usage": step["usage"], "costDetails": {"total": step["cost_eur"]}})
            ev.append(_event("generation-create", body))
        else:
            ev.append(_event("span-create", body))
    ev.append(_event("score-create", {"id": str(uuid.uuid4()), "traceId": trace_id, "name": item.judged.judge + "/" + item.judged.rubric,
                                      "value": item.judged.score, "comment": "; ".join(item.judged.rationale)[:500]}))
    ev.append(_event("score-create", {"id": str(uuid.uuid4()), "traceId": trace_id, "name": "platform_pass",
                                      "value": 1.0 if item.passed else 0.0, "comment": "; ".join(item.checks.failures())}))
    return ev


def write(path: Path, evs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for e in evs:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def push(evs: list[dict], client: httpx.Client | None = None, batch: int = 200) -> int:
    """Sends events to Langfuse's public ingestion API. Returns how many were accepted."""
    host = os.environ.get("LANGFUSE_HOST")
    pk, sk = os.environ.get("LANGFUSE_PUBLIC_KEY"), os.environ.get("LANGFUSE_SECRET_KEY")
    if not (host and pk and sk):
        return 0
    client = client or httpx.Client(timeout=10)
    accepted = 0
    for i in range(0, len(evs), batch):
        r = client.post(f"{host.rstrip('/')}/api/public/ingestion", json={"batch": evs[i:i + batch]}, auth=(pk, sk))
        r.raise_for_status()
        accepted += len(r.json().get("successes", []))
    return accepted
