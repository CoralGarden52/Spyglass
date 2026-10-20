"""Export only the public schema, never settings or environment values."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))

from app.main import create_app  # noqa: E402

destination = root / ".artifacts/openapi.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2), "utf-8")
print("OpenAPI exported to .artifacts/openapi.json")
