# Notebooks

Questa cartella contiene notebook di supporto.

Nel ramo `forecast-bioanalyst-native` i notebook non sono il punto principale per il forecast. I run nativi del modello passano prima dagli script Python, non dai notebook.

I notebook che restano servono soprattutto per:

- ispezione del dataset
- verifica delle variabili disponibili
- calcolo esplorativo degli indicatori
- grafici preliminari

## Notebook presenti

- [01_dataset_exploration.ipynb](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/notebooks/01_dataset_exploration.ipynb)
  Notebook generico per esplorare `csv`, `parquet` e `xlsx` cambiando solo il path del dataset nella cella di configurazione. E pensato per aprire sia file raw di `BioCube` sia gli output prodotti da `selected_area_indicators.py`.

- [selected_area.ipynb](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/notebooks/selected_area.ipynb)
  Al momento e un duplicato del notebook esplorativo base. Non contiene ancora correzioni integrate nella pipeline degli indicatori, ma include output gia eseguiti su Milano che possono essere usati come sanity check visuale.
