# Contributing

Start with synthetic fixtures. Do not submit customer metadata, credentials, real SAP exports or proprietary documentation. Discuss a narrowly scoped capability before adding live connectors; read-only annotations and host hooks are not authorization boundaries.

Python 3.11+ runs the core without third-party dependencies:

```sh
python3 -m unittest discover -s tests -v
python3 -m corelift demo
python3 -m corelift rehearse-demo
```

For workspace development, use Node 22+:

```sh
npm ci
npm run build:ui
npm run test:ui
python3 -m unittest discover -s tests -v
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/check_schemas.py
python3 scripts/build_packages.py --with-ui --output dist-check
```

Use a fresh package output directory. Test uncertain evidence, target-version mismatch, imported provenance and failure paths; preserve the distinction between mock verification, protocol validation and actual host/SAP acceptance. New dependencies require redistribution-license review. Contributions intentionally submitted for inclusion are under Apache-2.0 unless explicitly stated otherwise.
