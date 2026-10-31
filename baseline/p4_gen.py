import os
import numpy as np
import pandas as pd

# Input originali e cartella di output della versione 2
# I file CSV di partenza devono stare nella stessa cartella di questo script
D = os.path.dirname(os.path.abspath(__file__)) + os.sep
OUT = D  # tutti i file nella stessa cartella dello script

# Corrispondenza colonne clean (CamelCase) -> colonne dirty (minuscole)
CLEAN_TO_DIRTY = {
    "index": "index", "ProviderNumber": "provider_number", "HospitalName": "name",
    "Address1": "address_1", "Address2": "address_2", "Address3": "address_3",
    "City": "city", "State": "state", "ZipCode": "zip", "CountyName": "county",
    "PhoneNumber": "phone", "HospitalType": "type", "HospitalOwner": "owner",
    "EmergencyService": "emergency_service", "Condition": "condition",
    "MeasureCode": "measure_code", "MeasureName": "measure_name",
    "Score": "score", "Sample": "sample", "Stateavg": "state_average",
}
# Nuovi nomi opachi delle colonne (col_01 ... col_19)
P4_RENAME_MAP = {
    "index": "index", "provider_number": "col_01", "name": "col_02", "address_1": "col_03",
    "address_2": "col_04", "address_3": "col_05", "city": "col_06", "state": "col_07",
    "zip": "col_08", "county": "col_09", "phone": "col_10", "type": "col_11", "owner": "col_12",
    "emergency_service": "col_13", "condition": "col_14", "measure_code": "col_15",
    "measure_name": "col_16", "score": "col_17", "sample": "col_18", "state_average": "col_19",
}


def main():
    # Caricamento: clean portato ai nomi dirty, dirty allineato al clean per 'index'
    clean = pd.read_csv(D + "0499ba75-clean.csv", dtype=str, keep_default_na=False)
    clean = clean.apply(lambda s: s.str.strip()).rename(columns=CLEAN_TO_DIRTY).reset_index(drop=True)
    dirty = pd.read_csv(D + "3192ed70-dirty.csv", dtype=str, keep_default_na=False)
    dirty = dirty.apply(lambda s: s.str.strip())
    dirty = dirty.set_index("index", drop=False).loc[clean["index"]].reset_index(drop=True)

    # Ordine delle colonne permutato con seed fisso 42. La permutazione parte dall'ordine
    # delle colonne del file dirty, così il risultato è identico alla versione consegnata in precedenza.
    renamed_order = list(dirty.rename(columns=P4_RENAME_MAP).columns)
    rng = np.random.default_rng(42)
    data_cols = [c for c in renamed_order if c != "index"]
    permuted_cols = ["index"] + rng.permutation(data_cols).tolist()
    assert sorted(permuted_cols) == sorted(P4_RENAME_MAP.values())

    # Solo rinomina e riordino: i valori delle celle non cambiano
    new_clean = clean.rename(columns=P4_RENAME_MAP)[permuted_cols]
    new_dirty = dirty.rename(columns=P4_RENAME_MAP)[permuted_cols]
    assert new_clean.shape == clean.shape and new_dirty.shape == dirty.shape

    # La maschera degli errori deve restare identica a quella originale (confronto nello stesso ordine di colonne)
    orig_mask = dirty.rename(columns=P4_RENAME_MAP)[permuted_cols].ne(
        clean.rename(columns=P4_RENAME_MAP)[permuted_cols]).values
    new_mask = new_dirty.ne(new_clean).values
    assert (orig_mask == new_mask).all(), "maschera degli errori diversa"

    new_clean.to_csv(OUT + "p4_clean.csv", index=False)
    new_dirty.to_csv(OUT + "p4_dirty.csv", index=False)
    print(f"[P4] celle corrotte {int(new_mask.sum())} (originale {int(orig_mask.sum())}); colonne: {permuted_cols}")


if __name__ == "__main__":
    main()
