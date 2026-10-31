import os
import sys
import pandas as pd

# Percorsi: dati originali e cartella con i dataset v2 da verificare
# I file CSV di partenza devono stare nella stessa cartella di questo script
D = os.path.dirname(os.path.abspath(__file__)) + os.sep
V = D  # tutti i file nella stessa cartella dello script

# Corrispondenza colonne clean (CamelCase) -> dirty (minuscole); tutti i confronti avvengono nei nomi dirty
CLEAN_TO_DIRTY = {
    "index": "index", "ProviderNumber": "provider_number", "HospitalName": "name",
    "Address1": "address_1", "Address2": "address_2", "Address3": "address_3",
    "City": "city", "State": "state", "ZipCode": "zip", "CountyName": "county",
    "PhoneNumber": "phone", "HospitalType": "type", "HospitalOwner": "owner",
    "EmergencyService": "emergency_service", "Condition": "condition",
    "MeasureCode": "measure_code", "MeasureName": "measure_name",
    "Score": "score", "Sample": "sample", "Stateavg": "state_average",
}
# P4 usa nomi col_01..col_19: questa mappa li riporta ai nomi dirty
P4_MAP = {
    "index": "index", "provider_number": "col_01", "name": "col_02", "address_1": "col_03",
    "address_2": "col_04", "address_3": "col_05", "city": "col_06", "state": "col_07",
    "zip": "col_08", "county": "col_09", "phone": "col_10", "type": "col_11", "owner": "col_12",
    "emergency_service": "col_13", "condition": "col_14", "measure_code": "col_15",
    "measure_name": "col_16", "score": "col_17", "sample": "col_18", "state_average": "col_19",
}
P4_INV = {v: k for k, v in P4_MAP.items()}

# Dipendenze funzionali (nomi dirty). Un'FD verificata sull'originale deve valere anche sul perturbato.
FDS = [
    (["provider_number"], "name"), (["provider_number"], "city"), (["zip"], "city"),
    (["city"], "state"), (["city"], "county"), (["zip"], "state"), (["zip"], "county"),
    (["phone"], "provider_number"), (["phone"], "zip"),
    (["measure_code"], "measure_name"), (["measure_code"], "condition"),
    (["state", "measure_code"], "state_average"),
]


# Distanza di Levenshtein, ricopiata dal generatore per rendere il controllo indipendente da esso
def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# Carica il clean e il dirty originali, nei nomi dirty, con il dirty allineato al clean per 'index'
def load_original():
    c = pd.read_csv(D + "0499ba75-clean.csv", dtype=str, keep_default_na=False)
    c = c.apply(lambda s: s.str.strip()).rename(columns=CLEAN_TO_DIRTY)
    d = pd.read_csv(D + "3192ed70-dirty.csv", dtype=str, keep_default_na=False)
    d = d.apply(lambda s: s.str.strip())
    d = d.set_index("index", drop=False).loc[c["index"]].reset_index(drop=True)
    return c.reset_index(drop=True), d


# Carica un dataset perturbato. Per P4 riporta i nomi col_xx ai nomi dirty.
def load_pert(cpath, dpath, p4):
    c = pd.read_csv(cpath, dtype=str, keep_default_na=False)
    d = pd.read_csv(dpath, dtype=str, keep_default_na=False)
    if p4:
        c = c.rename(columns=P4_INV)
        d = d.rename(columns=P4_INV)
    else:
        c = c.rename(columns=CLEAN_TO_DIRTY)
    return c, d


# Esegue tutti i controlli su un dataset perturbato e stampa il risultato.
# required_edit: se True, una distanza di edit diversa dall'originale fa fallire il controllo.
# declared: colonne la cui perdita di biiettività è dichiarata nella tesi (per P3, county 33->9).
def run(label, cpath, dpath, p4, required_edit, declared=()):
    # Originali e perturbati nello stesso formato
    c0, d0 = load_original()
    c, d = load_pert(cpath, dpath, p4)
    cols = list(c0.columns)
    fails, notes = [], []

    # Stesse colonne e stesse righe, con indice allineato
    if set(c.columns) != set(cols) or set(d.columns) != set(cols):
        fails.append("colonne diverse dall'originale")
        print(f"== {label}: {fails}")
        return False
    c, d = c[cols], d[cols]
    if len(c) != len(c0) or len(d) != len(d0) or (c["index"].values != c0["index"].values).any() \
            or (d["index"].values != d0["index"].values).any():
        fails.append("righe o indice non allineati")
        print(f"== {label}: {fails}")
        return False

    # Maschera degli errori: stessa posizione delle celle sporche rispetto all'originale
    m0 = d0.ne(c0).values
    m1 = d.ne(c).values
    n_err = int(m1.sum())
    if (m0 != m1).any():
        fails.append("maschera errori diversa dall'originale")
    notes.append(f"celle corrotte {n_err} (originale {int(m0.sum())})")

    # Colonne effettivamente perturbate; le altre devono restare identiche anche nel dirty
    perturbed = [col for col in cols if col != "index" and (c[col] != c0[col]).any()]
    unchanged = [col for col in cols if col not in perturbed]
    for col in unchanged:
        if (d[col] != d0[col]).any():
            fails.append(f"colonna non perturbata {col} modificata nel dirty")

    # Biiettività per colonna: ogni valore originale ha un solo sintetico e viceversa
    bij_report = []
    for col in perturbed:
        pr = pd.DataFrame({"o": c0[col], "n": c[col]}).drop_duplicates()
        injective = pr.groupby("o").size().max() == 1
        surjective_back = pr.groupby("n").size().max() == 1
        n_o, n_n = c0[col].nunique(), c[col].nunique()
        ok = injective and surjective_back and n_o == n_n
        bij_report.append(f"{col} {n_o}->{n_n}{'' if ok else ' NON-BIIETTIVA'}")
        if not ok and col not in declared:
            fails.append(f"{col} non biiettiva")
    notes.append("biiettività: " + "; ".join(bij_report))

    # Quante delle celle modificate hanno la stessa lunghezza dell'originale (informativo)
    len_ok = sum(len(a) == len(b) for col in perturbed for a, b in zip(c[col], c0[col]) if a != b)
    len_tot = sum(1 for col in perturbed for a, b in zip(c[col], c0[col]) if a != b)
    notes.append(f"valori modificati di uguale lunghezza: {len_ok}/{len_tot}")

    # Distanza di edit: per ogni cella sporca, confronto tra la distanza originale e quella perturbata
    exact, mism = 0, []
    for col in cols:
        for r in range(len(c)):
            if d0.at[r, col] != c0.at[r, col]:
                e0 = lev(d0.at[r, col], c0.at[r, col])
                e1 = lev(d.at[r, col], c.at[r, col])
                if e0 == e1:
                    exact += 1
                else:
                    mism.append((col, r, e0, e1))
    notes.append(f"distanza di edit esatta {exact}/{exact + len(mism)}")
    if required_edit and mism:
        fails.append(f"distanza di edit non preservata in {len(mism)} celle")

    # Dipendenze funzionali: se valgono sull'originale, devono valere sul perturbato
    fd_lines = []
    for lhs, rhs in FDS:
        if any(x not in cols for x in lhs + [rhs]):
            continue
        h0 = bool(c0.groupby(lhs)[rhs].nunique().max() == 1)
        h1 = bool(c.groupby(lhs)[rhs].nunique().max() == 1)
        fd_lines.append(f"{'+'.join(lhs)}->{rhs}: {h0}->{h1}")
        if h0 and not h1:
            fails.append(f"FD {'+'.join(lhs)}->{rhs} rotta")
    notes.append("FD: " + " | ".join(fd_lines))

    # Stateavg deve restare uguale a {State}_{MeasureCode} se lo era nell'originale
    sa0 = bool(((c0["state"] + "_" + c0["measure_code"]) == c0["state_average"]).all())
    sa1 = bool(((c["state"] + "_" + c["measure_code"]) == c["state_average"]).all())
    notes.append("Stateavg=State_MeasureCode: " + f"{sa0}->{sa1}")
    if sa0 and not sa1:
        fails.append("Stateavg non coerente con State_MeasureCode")

    status = "OK" if not fails else "FALLITO"
    print(f"== {label}: {status}")
    for n in notes:
        print("   ", n)
    for f in fails:
        print("    ERRORE:", f)
    print()
    return not fails


# Esecuzione sui quattro dataset v2; exit code 1 se un controllo obbligatorio fallisce
results = {
    "P1": run("P1", V + "p1_clean.csv", V + "p1_dirty.csv", False, True),
    "P2": run("P2", V + "p2_clean.csv", V + "p2_dirty.csv", False, False),
    "P3": run("P3", V + "p3_clean.csv", V + "p3_dirty.csv", False, False, declared=("county",)),
    "P4": run("P4", V + "p4_clean.csv", V + "p4_dirty.csv", True, True),
}
print({k: ("OK" if v else "FALLITO") for k, v in results.items()})
sys.exit(0 if all(results.values()) else 1)
