# External

Questa cartella serve per i repository esterni che non vogliamo mescolare con il codice della tesi.

Per il ramo `forecast-bioanalyst-native`, qui va clonato il repository ufficiale:

```text
external/
  bfm-model/
```

Comando:

```bash
git clone https://github.com/BioDT/bfm-model.git external/bfm-model
```

Il runner nativo usa questo path per importare:

- `LargeClimateDataset`
- `setup_bfm_model`
- utility ufficiali del repository BioAnalyst
