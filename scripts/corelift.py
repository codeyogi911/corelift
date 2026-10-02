"""Self-contained host entry point; Python 3.11+, no installation required."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from corelift.__main__ import main

raise SystemExit(main())
