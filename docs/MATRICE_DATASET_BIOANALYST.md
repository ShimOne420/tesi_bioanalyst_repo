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
| `vegetation` | `NDVI` | `Land/Europe_ndvi_monthly_un_025.csv` oppure `era5-land-vegetation/data_stream-moda.nc` | `mapped_real_or_proxy` | Preferisce il CSV NDVI ufficiale; se manca, usa una proxy dichiarata da `lai_hv + lai_lv` ricampionata a 0.25 gradi |
| `forest` | `Forest` | `Forest/Europe_forest_data.csv` | `mapped_real` | Valore annuale `Forest_YYYY` ripetuto sui mesi dello stesso anno |
| `agriculture` | `Agriculture`, `Arable`, `Cropland` | `Agriculture/Europe_combined_agriculture_data.csv` | `mapped_real` | Usa le righe CSV corrispondenti e la colonna `Agri_YYYY` |
| `redlist` | `RLI` | nessuna sorgente locale allineata | `missing` | Da valutare solo dopo clima/forest |
| `misc` | `avg_slhtf`, `avg_pevr` | nessuna sorgente locale allineata | `missing` | Priorita bassa |

## Modalita Di Input

Per diagnosticare se gli input extra aiutano davvero il modello, il runner espone:

- `--input-mode clean`: usa `surface`, `edaphic`, `atmospheric`, `climate`, `species` e `land`; mette a zero `vegetation`, `agriculture`, `forest`, `redlist`, `misc`.
- `--input-mode all`: usa anche `vegetation`, `agriculture` e `forest` quando i file sono disponibili; resta comunque esplicito nel manifest cosa e reale, proxy o placeholder.

## Priorita Di Integrazione

L'ordine scelto per una replica piu fedele a BioAnalyst e:

1. `forest`
2. `agriculture / land cover`
3. `vegetation / NDVI`
4. `redlist`
5. `misc`

## Regola Di Mapping

La scorciatoia che resta da trattare con cautela e:

- fallback `LAI -> NDVI`, usato solo quando il CSV NDVI ufficiale non e presente

Nel codice questa conversione e marcata come proxy, non come `NDVI` osservato ufficiale.

Forest e agriculture sono ora letti da dataset dedicati, quindi non usano piu `cvh`, `cvl`, `tvh` o `tvl` come scorciatoia.
