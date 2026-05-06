#!/usr/bin/env python3
"""Resume WEkEO HDA downloads via REST using username/password auth.

This helper avoids the fragile `hda` Python client path and talks directly to
the broker REST API:

1. POST /gettoken
2. PUT /termsaccepted/<terms>
3. POST /dataaccess/search
4. POST /dataaccess/download
5. GET /dataaccess/download/<download_id> until file bytes are returned

It is safe to rerun: existing large files are skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BROKER_ROOT = "https://gateway.prod.wekeo2.eu/hda-broker"
TOKEN_URL = f"{BROKER_ROOT}/gettoken"
TERMS_URL = f"{BROKER_ROOT}/api/v1/termsaccepted/{{terms_id}}"
SEARCH_URL = f"{BROKER_ROOT}/api/v1/dataaccess/search"
DOWNLOAD_REQUEST_URL = f"{BROKER_ROOT}/api/v1/dataaccess/download"
DOWNLOAD_FETCH_URL = f"{BROKER_ROOT}/api/v1/dataaccess/download/{{download_id}}"
DEFAULT_TERMS = "Copernicus_Land_Monitoring_Service_Data_Policy"


def call_json(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {"accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    request = Request(url, headers=headers, data=data, method=method)
    try:
        with urlopen(request) as response:
            body = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} while calling {url}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while calling {url}: {exc}") from exc

    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON returned by {url}: {body[:300]!r}") from exc


def authenticate(username: str, password: str) -> str:
    response = call_json(
        TOKEN_URL,
        method="POST",
        payload={"username": username, "password": password},
    )
    token = response.get("access_token")
    if not token:
        raise RuntimeError(f"Token not found in response: {response}")
    return str(token)


def accept_terms(token: str, terms_id: str) -> None:
    call_json(TERMS_URL.format(terms_id=terms_id), method="PUT", token=token)


def fetch_binary(
    url: str,
    *,
    token: str,
) -> tuple[bytes, str]:
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "accept": "*/*",
        },
        method="GET",
    )
    try:
        with urlopen(request) as response:
            return response.read(), str(response.headers.get("Content-Type", ""))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} while fetching {url}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while fetching {url}: {exc}") from exc


def poll_and_download(
    *,
    token: str,
    download_id: str,
    target_path: Path,
    max_attempts: int,
    sleep_seconds: float,
) -> None:
    for attempt in range(1, max_attempts + 1):
        body, content_type = fetch_binary(
            DOWNLOAD_FETCH_URL.format(download_id=download_id),
            token=token,
        )

        if "application/json" not in content_type.lower():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(body)
            return

        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {"raw": body[:200].decode("utf-8", errors="replace")}
        print(f"    waiting {attempt}/{max_attempts}: {payload}")
        time.sleep(max(sleep_seconds, 0.0))

    raise RuntimeError(f"Download {download_id} not ready after {max_attempts} attempts")


def process_query(
    query_path: Path,
    *,
    token: str,
    output_root: Path,
    min_existing_bytes: int,
    max_attempts: int,
    sleep_seconds: float,
) -> None:
    query = json.loads(query_path.read_text(encoding="utf-8"))
    dataset_id = str(query["dataset_id"])
    out_dir = output_root / query_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nProcessing {query_path} ...")
    search_result = call_json(SEARCH_URL, method="POST", token=token, payload=query)
    (out_dir / "search_response.json").write_text(
        json.dumps(search_result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    features = search_result.get("features", [])
    if not isinstance(features, list):
        raise RuntimeError(f"Unexpected search response for {query_path}: {search_result}")

    for index, feature in enumerate(features, start=1):
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            continue
        product_id = str(feature.get("id", "")).strip()
        location = str(properties.get("location", "")).strip()
        if not product_id or not location:
            continue

        target_path = out_dir / f"{product_id}.zip"
        if target_path.exists() and target_path.stat().st_size >= min_existing_bytes:
            print(f"  skip {index}/{len(features)} {product_id}")
            continue

        print(f"  download {index}/{len(features)} {product_id}")
        download_payload = {
            "cacheable": True,
            "searchMetadata": "",
            "dataset_id": dataset_id,
            "product_id": product_id,
            "location": location,
        }
        download_info = call_json(
            DOWNLOAD_REQUEST_URL,
            method="POST",
            token=token,
            payload=download_payload,
        )
        download_id = str(download_info["download_id"])
        poll_and_download(
            token=token,
            download_id=download_id,
            target_path=target_path,
            max_attempts=max_attempts,
            sleep_seconds=sleep_seconds,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resume WEkEO downloads via direct REST API.")
    parser.add_argument("--username", default=os.environ.get("WEKEO_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("WEKEO_PASSWORD"))
    parser.add_argument("--terms", default=DEFAULT_TERMS)
    parser.add_argument("--query", action="append", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--min-existing-bytes", type=int, default=1024 * 1024)
    parser.add_argument("--max-attempts", type=int, default=30)
    parser.add_argument("--sleep-seconds", type=float, default=10.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.username or not args.password:
        raise SystemExit("Missing credentials. Pass --username/--password or set WEKEO_USERNAME/WEKEO_PASSWORD.")

    output_root = Path(args.output_dir).expanduser().resolve()
    query_paths = [Path(item).expanduser().resolve() for item in args.query]

    print("Authenticating to WEkEO HDA broker...")
    token = authenticate(str(args.username), str(args.password))
    print("Accepting terms if needed...")
    accept_terms(token, str(args.terms))

    for query_path in query_paths:
        process_query(
            query_path,
            token=token,
            output_root=output_root,
            min_existing_bytes=max(0, int(args.min_existing_bytes)),
            max_attempts=max(1, int(args.max_attempts)),
            sleep_seconds=max(0.0, float(args.sleep_seconds)),
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
