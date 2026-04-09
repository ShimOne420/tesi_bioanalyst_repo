# Scope del branch `forecast-bioanalyst-native`

Questo branch serve a ricostruire il blocco forecast nella direzione `BioAnalyst-native first`.

## Obiettivo del branch

- usare il modello nel modo piu fedele possibile alla pipeline ufficiale;
- separare input nativo, runner del modello e aggregazione BIOMAP;
- validare su `CUDA` il nuovo forecast prima di qualsiasi merge su `main`.

## Cosa va qui

- costruzione di un runner forecast parallelo al blocco attuale;
- lettura o costruzione di input il piu possibile vicini al formato nativo;
- estrazione degli output nativi del modello;
- aggregazione finale degli output nei tre indicatori BIOMAP.

## Cosa non va qui

- il blocco observed non va rifattorizzato insieme al forecast;
- la UI non va toccata finche il nuovo forecast non e validato;
- i benchmark della pipeline forecast attuale non sono l'obiettivo principale di questo ramo.

## Relazione con `main`

- `main` resta stabile e non va usato per esperimenti forecast;
- questo e il solo ramo forecast candidato a rientrare in `main`;
- il merge potra avvenire solo dopo validazione scientifica chiara del blocco clima.
