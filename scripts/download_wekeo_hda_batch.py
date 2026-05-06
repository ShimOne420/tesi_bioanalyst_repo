#!/usr/bin/env python3
"""Batch-download WEkEO HDA search results from one or more query JSON files.

This script is meant to unblock bulk CLMS downloads when the WEkEO viewer only
exposes per-tile ordering. It consumes the same query JSON exported by the
Expert Data Viewer, authenticates once, accepts terms if needed, searches for
matching products, then requests and downloads every result.

Example:
    python scripts/download_wekeo_hda_batch.py \
      --username "$WEKEO_USERNAME" \
      --password "$WEKEO_PASSWORD" \
      --terms Copernicus_Land_Monitoring_Service_Data_Policy \
      --query data/staging/agriculture_forest/forest/tcd_2022_query.json \
      --query data/staging/agriculture_forest/forest/tcd_2023_query.json \
      --output-dir data/staging/agriculture_forest_downloads
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


BASE_URL = "https://gateway.prod.wekeo2.eu/hda-broker"
TOKEN_URL = f"{BASE_URL}/gettoken"
SEARCH_URL = f"{BASE_URL}/api/v1/dataaccess/search"
DOWNLOAD_REQUEST_URL = f"{BASE_URL}/api/v1/dataaccess/download"
DOWNLOAD_FETCH_URL = f"{BASE_URL}/api/v1/dataaccess/download/{{download_id}}"
TERMS_URL = f"{BASE_URL}/api/v1/termsaccepted/{{terms_id}}"
DEFAULT_TERMS = "Copernicus_Land_Monitoring_Service_Data_Policy"


def http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | list[Any] | None = None,
    token: str | None = None,
    accept: str = "application/json",
) -> dict[str, Any] | list[Any]:
    headers = {"accept": accept}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request) as response:
            body = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"HTTP {exc.code} while calling {url}: {detail}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while calling {url}: {exc}") from exc
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON returned by {url}: {body[:500]!r}") from exc


def authenticate(username: str, password: str) -> str:
    response = http_json(
        TOKEN_URL,
        method="POST",
        payload={"username": username, "password": password},
    )
    token = response.get("access_token")
    if not token:
        raise RuntimeError(f"Token not found in authentication response: {response}")
    return token


def accept_terms(token: str, terms_id: str) -> None:
    http_json(
        TERMS_URL.format(terms_id=terms_id),
        method="PUT",
        token=token,
    )


def load_query(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def search_products(token: str, query: dict[str, Any]) -> dict[str, Any]:
    response = http_json(SEARCH_URL, method="POST", payload=query, token=token)
    if not isinstance(response, dict):
        raise RuntimeError(f"Unexpected search response type: {type(response)!r}")
    return response


def iter_features(search_response: dict[str, Any]) -> list[dict[str, Any]]:
    features = search_response.get("features")
    if isinstance(features, list):
        return [feature for feature in features if isinstance(feature, dict)]
    return []


def infer_dataset_id(query: dict[str, Any], search_response: dict[str, Any]) -> str:
    dataset_id = query.get("dataset_id")
    if dataset_id:
        return str(dataset_id)
    properties = search_response.get("properties")
    if isinstance(properties, dict) and properties.get("dataset_id"):
        return str(properties["dataset_id"])
    raise RuntimeError("Unable to infer dataset_id from query/search response.")


def request_download(
    token: str,
    *,
    dataset_id: str,
    product_id: str,
    location: str,
) -> str:
    payload = {
        "cacheable": True,
        "searchMetadata": "",
        "dataset_id": dataset_id,
        "product_id": product_id,
        "location": location,
    }
    response = http_json(
        DOWNLOAD_REQUEST_URL,
        method="POST",
        payload=payload,
        token=token,
    )
    download_id = response.get("download_id")
    if not download_id:
        raise RuntimeError(
            f"download_id not found for product_id={product_id}: {response}"
        )
    return str(download_id)


def sanitize_filename(name: str) -> str:
    name = name.strip().strip('"')
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    return name or "download.bin"


def filename_from_location(location: str) -> str | None:
    parsed = urlparse(location)
    candidate = Path(parsed.path).name
    if candidate:
        return sanitize_filename(candidate)
    return None


def filename_from_headers(headers: Any) -> str | None:
    disposition = headers.get("Content-Disposition")
    if not disposition:
        return None
    match = re.search(r'filename="?([^";]+)"?', disposition)
    if match:
        return sanitize_filename(match.group(1))
    return None


def extension_from_headers(headers: Any) -> str | None:
    content_type = headers.get("Content-Type")
    if not content_type:
        return None
    extension = mimetypes.guess_extension(content_type.split(";")[0].strip())
    return extension


def download_file(
    token: str,
    download_id: str,
    destination_dir: Path,
    *,
    preferred_name: str | None = None,
) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    request = Request(
        DOWNLOAD_FETCH_URL.format(download_id=download_id),
        headers={
            "accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="GET",
    )
    try:
        with urlopen(request) as response:
            filename = (
                preferred_name
                or filename_from_headers(response.headers)
                or f"{download_id}{extension_from_headers(response.headers) or ''}"
            )
            target_path = destination_dir / sanitize_filename(filename)
            with target_path.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"HTTP {exc.code} while downloading {download_id}: {detail}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while downloading {download_id}: {exc}") from exc
    return target_path


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def read_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_download_entry(entry: dict[str, Any], destination_dir: Path) -> dict[str, Any]:
    normalized = dict(entry)
    saved_to = normalized.get("saved_to")
    if saved_to:
        saved_path = Path(str(saved_to))
        if not saved_path.is_absolute():
            saved_path = destination_dir / saved_path
        normalized["saved_to"] = str(saved_path)
    return normalized


def load_existing_downloads(manifest_path: Path, destination_dir: Path) -> dict[str, dict[str, Any]]:
    payload = read_json_if_exists(manifest_path)
    if not isinstance(payload, dict):
        return {}
    downloads = payload.get("downloads")
    if not isinstance(downloads, list):
        return {}
    existing: dict[str, dict[str, Any]] = {}
    for raw_entry in downloads:
        if not isinstance(raw_entry, dict):
            continue
        product_id = str(raw_entry.get("product_id", "")).strip()
        if not product_id:
            continue
        existing[product_id] = normalize_download_entry(raw_entry, destination_dir)
    return existing


def entry_has_saved_file(entry: dict[str, Any]) -> bool:
    saved_to = entry.get("saved_to")
    return bool(saved_to) and Path(str(saved_to)).exists()


def persist_query_summary(path: Path, summary: dict[str, Any]) -> None:
    write_json(path, summary)


def process_query_file(
    token: str,
    query_path: Path,
    output_root: Path,
    *,
    dry_run: bool,
    pause_seconds: float,
) -> dict[str, Any]:
    query = load_query(query_path)
    query_name = query_path.stem
    destination_dir = output_root / query_name
    destination_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = destination_dir / "download_manifest.json"
    existing_downloads = load_existing_downloads(manifest_path, destination_dir)

    search_response = search_products(token, query)
    write_json(destination_dir / "search_response.json", search_response)

    features = iter_features(search_response)
    dataset_id = infer_dataset_id(query, search_response)
    summary: dict[str, Any] = {
        "query_file": str(query_path),
        "dataset_id": dataset_id,
        "feature_count": len(features),
        "downloads": [],
    }

    if not features:
        print(f"[WARN] No features found for {query_path}")
        return summary

    for index, feature in enumerate(features, start=1):
        product_id = str(feature.get("id", ""))
        properties = feature.get("properties") if isinstance(feature, dict) else {}
        location = ""
        if isinstance(properties, dict):
            location = str(properties.get("location", ""))
        if not product_id or not location:
            print(f"[WARN] Skipping malformed feature #{index} in {query_path}")
            continue

        preferred_name = filename_from_location(location)
        entry = {
            "product_id": product_id,
            "location": location,
            "preferred_name": preferred_name,
        }

        existing_entry = existing_downloads.get(product_id)
        if existing_entry and entry_has_saved_file(existing_entry):
            print(f"[{query_name}] {index}/{len(features)} skip existing {preferred_name or product_id}")
            summary["downloads"].append(existing_entry)
            continue

        if dry_run:
            summary["downloads"].append(entry)
            continue

        print(f"[{query_name}] {index}/{len(features)} request download for {preferred_name or product_id}")
        try:
            download_id = request_download(
                token,
                dataset_id=dataset_id,
                product_id=product_id,
                location=location,
            )
            entry["download_id"] = download_id
            target_path = download_file(
                token,
                download_id,
                destination_dir,
                preferred_name=preferred_name,
            )
            entry["saved_to"] = str(target_path)
            summary["downloads"].append(entry)
            persist_query_summary(manifest_path, summary)
            if pause_seconds > 0:
                time.sleep(pause_seconds)
        except Exception as exc:
            persist_query_summary(manifest_path, summary)
            raise RuntimeError(
                f"{query_name}: stopped after {len(summary['downloads'])}/{len(features)} downloads. "
                f"You can safely rerun the same command later; existing files will be skipped. "
                f"Original error: {exc}"
            ) from exc

    persist_query_summary(manifest_path, summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk-download WEkEO HDA results from exported query JSON files."
    )
    parser.add_argument("--username", help="WEkEO username. Can also use WEKEO_USERNAME.")
    parser.add_argument("--password", help="WEkEO password. Can also use WEKEO_PASSWORD.")
    parser.add_argument(
        "--terms",
        default=DEFAULT_TERMS,
        help=f"Terms ID to accept before download. Default: {DEFAULT_TERMS}",
    )
    parser.add_argument(
        "--query",
        action="append",
        required=True,
        help="Path to a query JSON exported from the WEkEO Expert Data Viewer. Repeatable.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where per-query download folders will be created.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=0.0,
        help="Optional pause between download jobs to be gentle with the API.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run search only and write manifests without requesting downloads.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    username = args.username or os.environ.get("WEKEO_USERNAME")
    password = args.password or os.environ.get("WEKEO_PASSWORD")
    if not username or not password:
        raise SystemExit(
            "Missing credentials. Pass --username/--password or set "
            "WEKEO_USERNAME and WEKEO_PASSWORD."
        )

    output_root = Path(args.output_dir).expanduser().resolve()
    query_paths = [Path(path).expanduser().resolve() for path in args.query]

    print("Authenticating to WEkEO HDA...")
    token = authenticate(username, password)
    print("Accepting terms if needed...")
    accept_terms(token, args.terms)

    overall_summary = {
        "output_dir": str(output_root),
        "queries": [],
        "dry_run": bool(args.dry_run),
    }
    for query_path in query_paths:
        print(f"Processing query: {query_path}")
        summary = process_query_file(
            token,
            query_path,
            output_root,
            dry_run=args.dry_run,
            pause_seconds=max(args.pause_seconds, 0.0),
        )
        overall_summary["queries"].append(summary)

    write_json(output_root / "batch_manifest.json", overall_summary)
    print(f"Done. Manifest written to {output_root / 'batch_manifest.json'}")


if __name__ == "__main__":
    main()
