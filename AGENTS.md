# Working on legal-quality-loop

## Fast feedback

| What | Command | Time |
|---|---|---|
| Lint and format, Python and web | `make check` | ~10 s |
| All tests | `make test` | ~10 s |
| Development experiments | `make develop` | ~10 s |

## Invariants

1. **Expert grades stay isolated.** Only `labels.py` (budgeted, noisy human labels), `meta/` and `experiments.py`
   import `world.expert`. The app, judges, checks, gate and optimizer never do; `tests/test_platform.py` enforces it.
2. **No judge scores anything before calibration.** A judge below `calibration.min_kappa` against expert labels may
   not be the fitness of a search or the scorer of a release; the gate blocks it.
3. **Every comparison has bounds.** Report intervals, paired differences and ties, not single numbers.
4. **Settings in config.** Prices, error rates, lever effects, thresholds and budgets live in `config/qloop.toml`,
   loaded strictly. The dashboard's colours, sizes and timings live in `web/src/theme/tokens.ts`.
5. **Generated reports.** `reports/results.json`, `reports/RESULTS.md` and the README block come from `qloop report`.
6. **Traces are redacted** before they are written or sent.

## The held-out rule

The held-out tasks (topics never used for tuning) are pinned in `config/heldout.sha256`. `qloop heldout` refuses to
run if they changed and refuses a second run without `--again`, which is logged in `reports/heldout-runs.log` and
reported. Tune on the development set only. When the held-out run shows a problem, publish it, fix it with a test,
and do not rerun the held-out set to make the number better.
