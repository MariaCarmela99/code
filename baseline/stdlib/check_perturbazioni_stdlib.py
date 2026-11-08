"""Controllo indipendente dei dataset P1-P4, senza pandas: usa solo la libreria standard.
Stessa logica di check_perturbazioni.py. Lanciare dalla cartella code/: servono db/clean.csv,
db/dirty.csv e i file p1_, p2_, p3it_, p3fr_, p4_ clean/dirty in db/. Esce con codice 1 se un controllo obbligatorio fallisce."""
import csv
import os
import sys

D = "./db/"  # lanciare dalla cartella code/
V = D

CLEAN_TO_DIRTY = {
    "index": "index", "ProviderNumber": "provider_number", "HospitalName": "name",
    "Address1": "address_1", "Address2": "address_2", "Address3": "address_3",
    "City": "city", "State": "state", "ZipCode": "zip", "CountyName": "county",
    "PhoneNumber": "phone", "HospitalType": "type", "HospitalOwner": "owner",
    "EmergencyService": "emergency_service", "Condition": "condition",
    "MeasureCode": "measure_code", "MeasureName": "measure_name",
    "Score": "score", "Sample": "sample", "Stateavg": "state_average",
}
P4_MAP = {
    "index": "index", "provider_number": "col_01", "name": "col_02", "address_1": "col_03",
    "address_2": "col_04", "address_3": "col_05", "city": "col_06", "state": "col_07",
    "zip": "col_08", "county": "col_09", "phone": "col_10", "type": "col_11", "owner": "col_12",
    "emergency_service": "col_13", "condition": "col_14", "measure_code": "col_15",
    "measure_name": "col_16", "score": "col_17", "sample": "col_18", "state_average": "col_19",
}
P4_INV = {v: k for k, v in P4_MAP.items()}

# Dipendenze funzionali (nomi dirty). Un'FD valida sull'originale deve valere anche sul perturbato.
FDS = [
    (["provider_number"], "name"), (["provider_number"], "city"), (["zip"], "city"),
    (["city"], "state"), (["city"], "county"), (["zip"], "state"), (["zip"], "county"),
    (["phone"], "provider_number"), (["phone"], "zip"),
    (["measure_code"], "measure_name"), (["measure_code"], "condition"),
    (["state", "measure_code"], "state_average"),
]


# Distanza di Levenshtein, ricopiata per rendere il controllo indipendente dai generatori
def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def read_csv(path, rename=None, strip=True):
    """Legge un CSV come (colonne, righe); rinomina le colonne con 'rename' se indicato."""
    rename = rename or {}
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        cols = [rename.get(c, c) for c in r.fieldnames]
        rows = [{rename.get(k, k): (v.strip() if strip else v) for k, v in row.items()} for row in r]
    return cols, rows


def holds(rows, lhs, rhs):
    seen = {}
    for r in rows:
        key = tuple(r[c] for c in lhs)
        if seen.setdefault(key, r[rhs]) != r[rhs]:
            return False
    return True


def load_original():
    cols, c = read_csv(D + "clean.csv", CLEAN_TO_DIRTY)
    _, d_rows = read_csv(D + "dirty.csv")
    by_idx = {r["index"]: r for r in d_rows}
    return cols, c, [by_idx[r["index"]] for r in c]


def load_pert(cpath, dpath, p4):
    # come nel controllo originale: i file perturbati vengono letti senza togliere spazi
    _, c = read_csv(cpath, P4_INV if p4 else CLEAN_TO_DIRTY, strip=False)
    _, d = read_csv(dpath, P4_INV if p4 else None, strip=False)
    return c, d


def run(label, cpath, dpath, p4, required_edit, declared=()):
    cols, c0, d0 = load_original()
    c, d = load_pert(cpath, dpath, p4)
    n = len(c0)
    fails, notes = [], []

    if not c or not d or set(c[0]) != set(cols) or set(d[0]) != set(cols):
        print(f"== {label}: ['colonne diverse dall'originale']")
        return False
    if len(c) != n or len(d) != n or any(c[i]["index"] != c0[i]["index"] or d[i]["index"] != d0[i]["index"]
                                         for i in range(n)):
        print(f"== {label}: ['righe o indice non allineati']")
        return False

    # Maschera degli errori
    m0 = [[d0[i][k] != c0[i][k] for k in cols] for i in range(n)]
    m1 = [[d[i][k] != c[i][k] for k in cols] for i in range(n)]
    if m0 != m1:
        fails.append("maschera errori diversa dall'originale")
    notes.append(f"celle corrotte {sum(map(sum, m1))} (originale {sum(map(sum, m0))})")

    # Colonne perturbate; le altre devono restare identiche anche nel dirty
    perturbed = [k for k in cols if k != "index" and any(c[i][k] != c0[i][k] for i in range(n))]
    for k in cols:
        if k not in perturbed and any(d[i][k] != d0[i][k] for i in range(n)):
            fails.append(f"colonna non perturbata {k} modificata nel dirty")

    # Biiettività per colonna
    bij = []
    for k in perturbed:
        pairs = {(c0[i][k], c[i][k]) for i in range(n)}
        injective = len({o for o, _ in pairs}) == len(pairs)
        back = len({x for _, x in pairs}) == len(pairs)
        n_o, n_n = len({r[k] for r in c0}), len({r[k] for r in c})
        ok = injective and back and n_o == n_n
        bij.append(f"{k} {n_o}->{n_n}{'' if ok else ' NON-BIIETTIVA'}")
        if not ok and k not in declared:
            fails.append(f"{k} non biiettiva")
    notes.append("biiettività: " + "; ".join(bij))

    # Valori modificati di uguale lunghezza (informativo)
    changed = [(c[i][k], c0[i][k]) for k in perturbed for i in range(n) if c[i][k] != c0[i][k]]
    notes.append(f"valori modificati di uguale lunghezza: {sum(len(a) == len(b) for a, b in changed)}/{len(changed)}")

    # Distanza di edit cella per cella
    exact, mism = 0, 0
    for k in cols:
        for i in range(n):
            if d0[i][k] != c0[i][k]:
                if lev(d0[i][k], c0[i][k]) == lev(d[i][k], c[i][k]):
                    exact += 1
                else:
                    mism += 1
    notes.append(f"distanza di edit esatta {exact}/{exact + mism}")
    if required_edit and mism:
        fails.append(f"distanza di edit non preservata in {mism} celle")

    # Dipendenze funzionali
    fd_lines = []
    for lhs, rhs in FDS:
        if any(x not in cols for x in lhs + [rhs]):
            continue
        h0, h1 = holds(c0, lhs, rhs), holds(c, lhs, rhs)
        fd_lines.append(f"{'+'.join(lhs)}->{rhs}: {h0}->{h1}")
        if h0 and not h1:
            fails.append(f"FD {'+'.join(lhs)}->{rhs} rotta")
    notes.append("FD: " + " | ".join(fd_lines))

    # Stateavg = State_MeasureCode
    sa0 = all(r["state"] + "_" + r["measure_code"] == r["state_average"] for r in c0)
    sa1 = all(r["state"] + "_" + r["measure_code"] == r["state_average"] for r in c)
    notes.append(f"Stateavg=State_MeasureCode: {sa0}->{sa1}")
    if sa0 and not sa1:
        fails.append("Stateavg non coerente con State_MeasureCode")

    print(f"== {label}: {'OK' if not fails else 'FALLITO'}")
    for x in notes:
        print("   ", x)
    for f in fails:
        print("    ERRORE:", f)
    print()
    return not fails


results = {
    "P1": run("P1", V + "p1_clean.csv", V + "p1_dirty.csv", False, True),
    "P2": run("P2", V + "p2_clean.csv", V + "p2_dirty.csv", False, False),
    "P3IT": run("P3IT", V + "p3it_clean.csv", V + "p3it_dirty.csv", False, True),
    "P3FR": run("P3FR", V + "p3fr_clean.csv", V + "p3fr_dirty.csv", False, True),
    "P4": run("P4", V + "p4_clean.csv", V + "p4_dirty.csv", True, True),
}
print({k: ("OK" if v else "FALLITO") for k, v in results.items()})
sys.exit(0 if all(results.values()) else 1)
