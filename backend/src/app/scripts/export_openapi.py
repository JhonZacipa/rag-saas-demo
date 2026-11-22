"""Write the OpenAPI schema to a file so the frontend can generate typed clients.

Usage: ``uv run python -m app.scripts.export_openapi frontend/openapi.json``
"""

import json
import sys
from pathlib import Path

from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    # The schema does not depend on real infrastructure, so placeholder settings are enough.
    settings = Settings(database_url=SecretStr("postgresql://unused@localhost/unused"))
    schema = create_app(settings).openapi()
    content = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    # newline="\n" keeps LF endings on Windows too, so the file matches the one CI generates.
    target.write_text(content, encoding="utf-8", newline="\n")
    print(f"OpenAPI schema written to {target}")


if __name__ == "__main__":
    main()
