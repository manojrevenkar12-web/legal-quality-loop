PY ?= python3
export PYTHONPATH := src

.PHONY: check test develop heldout report serve web
check:        ## lint and format, Python and web
	ruff check src tests && ruff format --check src tests
	cd web && npx tsc --noEmit && npx eslint src test
test:         ## 95 Python tests and the dashboard tests, seconds
	$(PY) -m pytest -q
	cd web && npx vitest run
develop:      ## calibration, searches, audits, red team: development set only
	$(PY) -m qloop.cli develop
heldout:      ## the pinned held-out set, once
	$(PY) -m qloop.cli heldout
report:       ## reports/results.json, reports/RESULTS.md, the README block
	$(PY) -m qloop.cli report
serve:        ## the API on :8000
	$(PY) -m qloop.cli serve
web:          ## the dashboard on :5173
	cd web && npm ci && npm run dev
