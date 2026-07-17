"""Send the fictional sample HighLevel event to a running local API."""

import json
import os
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_PATH = PROJECT_ROOT / "examples" / "new_lead.json"


def main() -> None:
    """Post a locally configured sample event and print the JSON response."""
    base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
    secret = os.getenv("WEBHOOK_SHARED_SECRET", "local-demo-secret")
    payload = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))
    response = httpx.post(
        f"{base_url.rstrip('/')}/webhooks/highlevel",
        headers={"X-Webhook-Secret": secret},
        json=payload,
        timeout=15,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()
