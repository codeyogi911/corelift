# Contributing

Start with synthetic fixtures. Do not submit customer metadata, credentials, real SAP exports or proprietary documentation. Discuss a narrowly scoped capability before adding live connectors; read-only annotations and host hooks are not authorization boundaries.

Python 3.11+ runs the core without third-party dependencies. The full gate also needs Node 22+ and the dev requirements:

```sh
npm ci
python3 -m pip install -r requirements-dev.txt   # in a project-local venv if you prefer
python3 scripts/verify.py           # full gate, identical to CI
python3 scripts/verify.py --quick   # agent docs and Python tests
```

Agents and humans follow the same build loop in [AGENTS.md](AGENTS.md); domain terms are in [CONTEXT.md](CONTEXT.md). Use a fresh package output directory. Test uncertain evidence, target-version mismatch, imported provenance and failure paths; preserve the distinction between mock verification, protocol validation and actual host/SAP acceptance. New dependencies require redistribution-license review. Contributions intentionally submitted for inclusion are under Apache-2.0 unless explicitly stated otherwise.
