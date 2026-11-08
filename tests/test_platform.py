import ast
import json

import httpx
from fastapi.testclient import TestClient

from qloop.api import create_app
from qloop.app.assistant import AppConfig
from qloop.config import ROOT
from qloop.privacy import Redactor
from qloop.runner import evaluate
from qloop.tracing import events, push


def test_only_labels_and_meta_read_expert_grades():
    allowed = {"labels.py", "experiments.py", "truth.py", "expert.py"}
    offenders = []
    for path in (ROOT / "src" / "qloop").rglob("*.py"):
        if path.name in allowed:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom):
                names = [f"{node.module}.{a.name}" for a in node.names]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            if any("world.expert" in n or n.endswith("world.expert") or "qloop.meta" in n for n in names):
                offenders.append(path.name)
    assert not offenders, offenders


def test_redaction():
    r = Redactor(b"k")
    s = r.text("Havel Software GmbH (legal@havel-software.de), IBAN DE02 1203 0000 0000 2020 51, +49 176 36795025")
    assert "havel-software.de" not in s and "DE02" not in s and "Havel Software GmbH" not in s and "36795025" not in s
    assert r.text("legal@havel-software.de") == r.text("legal@havel-software.de")


def test_traces_are_langfuse_events_and_redacted(dev, settings, monkeypatch):
    run = evaluate(AppConfig(), [t for t in dev if t.family == "discovery"][:6], settings)
    evs = events(run, "test", Redactor(b"k"))
    kinds = {e["type"] for e in evs}
    assert {"trace-create", "generation-create", "score-create"} <= kinds
    assert "@" not in json.dumps([e for e in evs if e["type"] == "trace-create"])
    sent = []

    def handler(request):
        body = json.loads(request.content)
        sent.extend(body["batch"])
        return httpx.Response(
            207, json={"successes": [{"id": e["id"], "status": 201} for e in body["batch"]], "errors": []}
        )

    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    assert push(evs, httpx.Client(transport=httpx.MockTransport(handler)), batch=10) == len(evs) == len(sent)


def test_api(tmp_path):
    client = TestClient(create_app(reports=tmp_path))
    r = client.post("/evaluate", json={"config": {"model": "small"}, "families": ["review"]})
    assert r.status_code == 200 and r.json()["items"] > 0 and r.json()["judge_trusted"] is False
    assert client.post("/evaluate", json={"split": "heldout"}).status_code == 403
    assert client.post("/evaluate", json={"families": ["poetry"]}).status_code == 422
    assert client.post("/evaluate", json={"config": {"model": "huge"}}).status_code == 422
    c = client.post(
        "/compare",
        json={"baseline": {}, "candidate": {"model": "small", "tone": "assertive"}, "families": ["research"]},
    )
    assert c.json()["decision"]["verdict"] == "block"
    assert client.get("/results").status_code == 404


def test_config_is_strict(tmp_path):
    import pytest

    from qloop.config import load

    bad = tmp_path / "q.toml"
    bad.write_text((ROOT / "config" / "qloop.toml").read_text() + "\n[typo]\nx = 1\n")
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        load(bad)
