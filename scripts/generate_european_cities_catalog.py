#!/usr/bin/env python3
"""Genera un catalogo locale di citta europee per la UI e il backend.

Questo script usa `geonamescache` per produrre un file JSON condiviso
contenente le citta dei paesi classificati nel continente europeo.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import geonamescache


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "european_cities.json"


# Convertiamo nome citta e nazione in una label leggibile e in un identificativo stabile.
def build_city_record(city: dict, country_name: str) -> dict:
    label = city["name"].strip()
    slug_base = re.sub(r"[^a-zA-Z0-9]+", "_", f"{label}_{country_name}").strip("_").lower()

    return {
        "value": f"{slug_base}_{city['geonameid']}",
        "label": label,
        "country": country_name,
        "countryCode": city["countrycode"],
        "lat": float(city["latitude"]),
        "lon": float(city["longitude"]),
        "population": int(city.get("population", 0)),
    }


# Filtriamo i paesi europei e trasformiamo le citta in un catalogo pronto per frontend e backend.
def build_catalog() -> list[dict]:
    gc = geonamescache.GeonamesCache()
    countries = gc.get_countries()
    european_country_codes = {
        code for code, item in countries.items() if item.get("continentcode") == "EU"
    }

    records = []
    for city in gc.get_cities().values():
        if city.get("countrycode") not in european_country_codes:
            continue

        country_name = countries[city["countrycode"]]["name"]
        records.append(build_city_record(city, country_name))

    records.sort(key=lambda item: (-item["population"], item["country"], item["label"]))
    return records


# Scriviamo il catalogo in JSON per renderlo riusabile nel progetto senza dipendere dal pacchetto a runtime.
def main() -> None:
    records = build_catalog()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Catalogo creato: {OUTPUT_PATH}")
    print(f"Città europee totali: {len(records)}")


# Rendiamo lo script eseguibile da terminale.
if __name__ == "__main__":
    main()
