"""qloop: evaluate a config, compare two, run the development experiments, the held-out run, and the reports.

qloop eval --config configs/candidate.json --family research
qloop compare --baseline configs/baseline.json --candidate configs/candidate.json
qloop develop            # calibration, landscape, searches, red team (development set only)
qloop heldout            # the held-out set, once (pinned in config/heldout.sha256)
qloop report             # reports/results.json, reports/RESULTS.md, the README block
qloop serve              # the HTTP API on :8000
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from qloop.app.assistant import AppConfig
from qloop.config import ROOT, load


def _cfg(path: str | None) -> AppConfig:
    return AppConfig(**json.loads(Path(path).read_text())) if path else AppConfig()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="qloop")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("eval")
    e.add_argument("--config")
    e.add_argument("--family", action="append")
    c = sub.add_parser("compare")
    c.add_argument("--baseline", required=True)
    c.add_argument("--candidate", required=True)
    sub.add_parser("develop")
    h = sub.add_parser("heldout")
    h.add_argument("--again", action="store_true", help="run the held-out set again (recorded)")
    sub.add_parser("report")
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8000)
    a = p.parse_args(argv)
    settings = load()
    reports = ROOT / "reports"

    if a.cmd == "eval":
        from qloop.experiments import tasks
        from qloop.runner import evaluate

        dev, _ = tasks(settings)
        fams = a.family or ["research", "review", "discovery"]
        print(json.dumps(evaluate(_cfg(a.config), [t for t in dev if t.family in fams], settings).summary(), indent=1))
    elif a.cmd == "compare":
        from qloop.experiments import tasks
        from qloop.gate import compare
        from qloop.runner import evaluate

        dev, _ = tasks(settings)
        d = compare(evaluate(_cfg(a.baseline), dev, settings), evaluate(_cfg(a.candidate), dev, settings), settings)
        print(json.dumps(d.as_dict(), indent=1))
        return 0 if d.verdict == "ship" else 1
    elif a.cmd == "develop":
        from qloop.experiments import development, write_json

        write_json(reports / "development.json", development(settings))
        print("wrote reports/development.json")
    elif a.cmd == "heldout":
        from qloop.experiments import heldout, tasks, write_json
        from qloop.world.tasks import fingerprint

        _, held = tasks(settings)
        pin = (ROOT / "config" / "heldout.sha256").read_text().strip()
        if fingerprint(held) != pin:
            print(f"the held-out set changed since it was pinned ({pin[:12]})", file=sys.stderr)
            return 2
        log = reports / "heldout-runs.log"
        if log.exists() and log.read_text().strip() and not a.again:
            print("the held-out set has already run; --again runs it again and is recorded", file=sys.stderr)
            return 2
        dev_report = json.loads((reports / "development.json").read_text())
        with log.open("a") as f:
            f.write(f"{datetime.now(UTC).isoformat()} pin={pin}\n")
        write_json(reports / "heldout.json", heldout(settings, dev_report))
        print("wrote reports/heldout.json")
    elif a.cmd == "report":
        from qloop.report import build

        build(settings)
        print("wrote reports/results.json, reports/RESULTS.md and the README block")
    elif a.cmd == "serve":
        import uvicorn

        from qloop.api import create_app

        uvicorn.run(create_app(settings), host="0.0.0.0", port=a.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
