# Tesi di Maria Carmela Scibilia – codice

Generazione e verifica dei dataset perturbati del benchmark Hospital, baseline deterministica
ed esperimenti di riparazione delle celle con un LLM locale (Ollama).

Modelli usati negli esperimenti: **Llama 3.1 8B** (`llama3.1:8b`) e **Mistral 7B** (`mistral:latest`).

## Struttura

| Percorso | Contenuto |
|---|---|
| `db/clean.csv`, `db/dirty.csv` | dataset Hospital originale (pulito e sporco) |
| `db/p1_*`, `db/p2_*`, `db/p3it_*`, `db/p3fr_*`, `db/p4_*` | dataset perturbati (pulito e sporco) |
| `baseline/p1_gen.py` … `baseline/p4_gen.py` | generatori delle perturbazioni |
| `baseline/p3it_gen.py`, `baseline/p3fr_gen.py` | P3 nelle varianti italiana e francese |
| `baseline/check_perturbazioni.py` | controllo indipendente delle proprietà di P1–P4 |
| `baseline/baseline.py` | baseline deterministica e controllo di invarianza |
| `baseline/comuni_cap_map.csv` | comuni italiani con CAP (ISTAT), usato da P3IT |
| `baseline/laposte_cp_map.csv` | *Base officielle des codes postaux* (La Poste, data.gouv.fr), usato da P3FR |
| `baseline/p3it_geo_map.csv`, `baseline/p3fr_geo_map.csv` | corrispondenze stato/contea/città prodotte da P3 |
| `test_hospitals.py` | esperimento con l'LLM (Ollama) |
| `requirements.txt` | dipendenze Python dell'esperimento con l'LLM |

## Le perturbazioni

| | Cosa fa | Distanza di edit preservata |
|---|---|---|
| P1 | valori sostituiti da stringhe sintetiche della stessa forma; errori trasferiti con le operazioni di edit | 509 / 509 |
| P2 | valori reali permutati tra entità (derangement ciclico) | 507 / 509 |
| P3IT | trapianto nel dominio italiano: al → Italia settentrionale, ak → Italia centrale; una provincia diversa per ogni contea | 509 / 509 |
| P3FR | trapianto nel dominio francese: al → Francia metropolitana, ak → oltremare; un département diverso per ogni contea | 509 / 509 |
| P4 | colonne rinominate col_01 … col_19 e permutate (seme 42) | 509 / 509 |

In tutte le versioni la maschera degli errori è identica all'originale (509 celle) e le dipendenze
funzionali sono preservate. In P3 tutte le mappe, contea compresa, sono biiettive.

## Preparazione dell'ambiente

Quasi tutti gli script hanno bisogno di pandas (`p3it_gen.py` e `p3fr_gen.py` usano solo la
libreria standard): su Debian e Ubuntu recenti il Python di sistema non permette l'installazione
diretta dei pacchetti, quindi conviene un ambiente virtuale dedicato.

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Da qui in avanti si usa `.venv/bin/python` al posto di `python`, oppure si attiva l'ambiente una
volta per sessione con `source .venv/bin/activate`.

## Esecuzione

Tutti gli script si lanciano dalla cartella principale del repository:

```
python baseline/p1_gen.py
python baseline/p2_gen.py
python baseline/p3it_gen.py
python baseline/p3fr_gen.py
python baseline/p4_gen.py
python baseline/check_perturbazioni.py
python baseline/baseline.py
```

Esperimento con l'LLM (serve Ollama in esecuzione con il modello scelto già scaricato):

```
python test_hospitals.py --dry-run --max-rows 0
python test_hospitals.py --max-rows 0 --prefix p3it_
python test_hospitals.py --max-rows 0 --prefix p3it_ --model mistral:latest
```

Prefissi disponibili: `""` (originale), `p1_`, `p2_`, `p3it_`, `p3fr_`, `p4_`.

### Scelta del modello

`--model` seleziona il modello Ollama; il valore predefinito è `llama3.1:8b`. Con il modello
predefinito i risultati finiscono in `db/<prefisso>hospital_output_log.csv` e
`db/<prefisso>hospital_output_repaired.csv`; con un modello diverso i nomi prendono un suffisso
(per esempio `db/p3it_hospital_output_log_mistral-latest.csv`), così i confronti fra modelli non
si sovrascrivono.

Ogni modello occupa circa 5 GB di RAM e `test_hospitals.py` lo mantiene in memoria per trenta
minuti dopo l'ultima chiamata. Su una macchina con 16 GB conviene quindi scaricare il modello
precedente prima di passare al successivo:

```
ollama stop llama3.1:8b
```
