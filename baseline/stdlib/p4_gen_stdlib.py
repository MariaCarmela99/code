"""Generatore di P4 (perturbazione sintattica della struttura) senza pandas né numpy.
Stessa logica di p4_gen.py: le colonne vengono rinominate col_01 ... col_19 e permutate;
i valori delle celle non cambiano. Lanciare dalla cartella code/: i CSV stanno in code/db/;
p4_clean.csv e p4_dirty.csv vengono scritti in code/db/."""
import csv
import os

D = "./db/"  # i CSV stanno in code/db/ (lanciare lo script dalla directory code)
OUT = D

CLEAN_TO_DIRTY = {
    "index": "index", "ProviderNumber": "provider_number", "HospitalName": "name",
    "Address1": "address_1", "Address2": "address_2", "Address3": "address_3",
    "City": "city", "State": "state", "ZipCode": "zip", "CountyName": "county",
    "PhoneNumber": "phone", "HospitalType": "type", "HospitalOwner": "owner",
    "EmergencyService": "emergency_service", "Condition": "condition",
    "MeasureCode": "measure_code", "MeasureName": "measure_name",
    "Score": "score", "Sample": "sample", "Stateavg": "state_average",
}
P4_RENAME_MAP = {
    "index": "index", "provider_number": "col_01", "name": "col_02", "address_1": "col_03",
    "address_2": "col_04", "address_3": "col_05", "city": "col_06", "state": "col_07",
    "zip": "col_08", "county": "col_09", "phone": "col_10", "type": "col_11", "owner": "col_12",
    "emergency_service": "col_13", "condition": "col_14", "measure_code": "col_15",
    "measure_name": "col_16", "score": "col_17", "sample": "col_18", "state_average": "col_19",
}
# Ordine permutato delle colonne. È il risultato di
#   numpy.random.default_rng(42).permutation(colonne_dati)
# calcolato una volta con numpy sull'ordine delle colonne del file dirty (come in p4_gen.py)
# e riportato qui come elenco fisso, così lo script non richiede numpy.
PERMUTED_COLS = ["index", "col_15", "col_10", "col_18", "col_08", "col_13", "col_11", "col_07",
                 "col_19", "col_04", "col_01", "col_16", "col_06", "col_12", "col_03", "col_05",
                 "col_17", "col_02", "col_14", "col_09"]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        cols = r.fieldnames
        rows = [{k: v.strip() for k, v in row.items()} for row in r]
    return cols, rows


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main():
    _, clean = read_csv(D + "clean.csv")
    _, dirty_rows = read_csv(D + "dirty.csv")
    by_idx = {r["index"]: r for r in dirty_rows}
    dirty = [by_idx[r["index"]] for r in clean]

    assert sorted(PERMUTED_COLS) == sorted(P4_RENAME_MAP.values())

    # Solo rinomina: clean -> nomi dirty -> nomi opachi; dirty -> nomi opachi. I valori non cambiano.
    new_clean = [{P4_RENAME_MAP[CLEAN_TO_DIRTY[k]]: v for k, v in r.items()} for r in clean]
    new_dirty = [{P4_RENAME_MAP[k]: v for k, v in r.items()} for r in dirty]
    assert len(new_clean) == len(clean) and len(new_dirty) == len(dirty)

    # Maschera degli errori: stessa cella sporca, prima e dopo
    orig = sum(dirty[i][dc] != clean[i][cc] for i in range(len(clean))
               for cc, dc in CLEAN_TO_DIRTY.items())
    new = sum(new_dirty[i][c] != new_clean[i][c] for i in range(len(clean)) for c in PERMUTED_COLS)
    assert orig == new, "maschera degli errori diversa"

    write_csv(OUT + "p4_clean.csv", PERMUTED_COLS, new_clean)
    write_csv(OUT + "p4_dirty.csv", PERMUTED_COLS, new_dirty)
    print(f"[P4] celle corrotte {new} (originale {orig}); colonne: {PERMUTED_COLS}")


if __name__ == "__main__":
    main()
