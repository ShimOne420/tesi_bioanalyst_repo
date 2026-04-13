# Matrice Dataset BioAnalyst

Questa tabella serve a dire, in modo esplicito, quali gruppi del batch nativo BioAnalyst sono oggi alimentati da dati reali e quali no.

La regola del ramo `forecast-bioanalyst-native` e semplice:

- se un dataset corrisponde davvero al canale atteso dal modello, lo mappiamo
- se la corrispondenza e dubbia, non la forziamo

## Stato Attuale

| Gruppo BioAnalyst | Variabili attese | Sorgente locale | Stato | Nota |
| --- | --- | --- | --- | --- |
| `surface` | `t2m`, `msl`, `slt`, `z`, `u10`, `v10`, `lsm` | `Copernicus/ERA5-monthly/era5-single/era5_single.nc` | `mapped_real` | Gruppo reale completo |
| `edaphic` | `swvl1`, `swvl2`, `stl1`, `stl2` | `Copernicus/ERA5-monthly/era5-edaphic/era5-edaphic-0.nc` | `mapped_real` | Gruppo reale completo |
| `atmospheric` | `z`, `t`, `u`, `v`, `q` | `Copernicus/ERA5-monthly/era5-pressure/era5_pressure.nc` | `mapped_real` | Gruppo reale completo |
| `climate` | `smlt`, `tp`, `csfr`, `avg_sdswrf`, `avg_snswrf`, `avg_snlwrf`, `avg_tprate`, `avg_sdswrfcs`, `sd`, `t2m`, `d2m` | `era5-climate-energy-moisture-0.nc`, `era5-climate-energy-moisture-1.nc` | `mapped_real` | Gruppo reale completo |
| `species` | 28 specie target | `Species/europe_species.parquet` | `mapped_real` | Rasterizzazione mensile su griglia ERA5 |
| `land` | `Land` | `lsm` da `surface` | `mapped_real` | Ricostruzione sicura da canale reale |
| `vegetation` | `NDVI` | `era5-land-vegetation` (`lai_hv`, `lai_lv`, `cvh`, `cvl`, `tvh`, `tvl`) | `available_but_not_semantically_safe` | Nessuna mappatura diretta documentata a `NDVI` |
| `forest` | `Forest` | nessuna sorgente ancora allineata | `missing` | Priorita alta per la tesi |
| `agriculture` | `Agriculture`, `Arable`, `Cropland` | nessuna sorgente ancora allineata | `missing` | Priorita alta |
| `redlist` | `RLI` | nessuna sorgente locale allineata | `missing` | Da valutare solo dopo clima/forest |
| `misc` | `avg_slhtf`, `avg_pevr` | nessuna sorgente locale allineata | `missing` | Priorita bassa |

## Priorita Di Integrazione

L'ordine scelto per una replica piu fedele a BioAnalyst e:

1. `forest`
2. `agriculture / land cover`
3. `vegetation / NDVI`
4. `redlist`
5. `misc`

## Regola Di Mapping

Non facciamo queste scorciatoie:

- `LAI -> NDVI`
- `high vegetation cover -> Forest`
- `generic land cover -> Cropland`

finche non esiste una giustificazione metodologica chiara.

Meglio un gruppo dichiarato placeholder che un input semanticamente sbagliato dentro il batch.
