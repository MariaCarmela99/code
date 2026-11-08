"""Baseline deterministica senza pandas (solo libreria standard di Python).
Stessa logica di baseline_v2.py: per ogni cella sporca, il valore più frequente tra le righe
che condividono la chiave di una dipendenza funzionale. Usa solo il dirty.
Lanciare dalla cartella code/: i CSV stanno in code/db/."""
import csv
import os
from collections import Counter, defaultdict

HERE = "."  # lanciare dalla cartella code/

# Colonne del clean (CamelCase) -> colonne del dirty (minuscole)
CLEAN_TO_DIRTY = {
    "ProviderNumber": "provider_number", "HospitalName": "name", "Address1": "address_1",
    "Address2": "address_2", "Address3": "address_3", "City": "city", "State": "state",
    "ZipCode": "zip", "CountyName": "county", "PhoneNumber": "phone", "HospitalType": "type",
    "HospitalOwner": "owner", "EmergencyService": "emergency_service", "Condition": "condition",
    "MeasureCode": "measure_code", "MeasureName": "measure_name", "Score": "score",
    "Sample": "sample", "Stateavg": "state_average",
}
# Nomi opachi della versione P4 -> nomi del dirty
P4_RENAME = {
    "provider_number": "col_01", "name": "col_02", "address_1": "col_03", "address_2": "col_04",
    "address_3": "col_05", "city": "col_06", "state": "col_07", "zip": "col_08", "county": "col_09",
    "phone": "col_10", "type": "col_11", "owner": "col_12", "emergency_service": "col_13",
    "condition": "col_14", "measure_code": "col_15", "measure_name": "col_16", "score": "col_17",
    "sample": "col_18", "state_average": "col_19",
}
P4_INV = {v: k for k, v in P4_RENAME.items()}

FD_COLS = ["provider_number", "name", "address_1", "city", "state", "zip", "county", "phone",
           "type", "owner", "emergency_service", "condition", "measure_code", "measure_name",
           "state_average"]

# (chiave, colonna determinata), in ordine di priorità
RULES = [(("provider_number",), t) for t in ["name", "address_1", "city", "state", "zip",
          "county", "phone", "type", "owner", "emergency_service"]]
RULES += [(("phone",), "provider_number"), (("phone",), "zip"),
          (("zip",), "city"), (("zip",), "state"), (("zip",), "county"),
          (("measure_code",), "measure_name"), (("measure_code",), "condition"),
          (("state", "measure_code"), "state_average")]

MISSING = {"", "empty"}

SETS = {
    "original": ("db/dirty.csv", "db/clean.csv"),
    "P1": ("db/p1_dirty.csv", "db/p1_clean.csv"),
    "P2": ("db/p2_dirty.csv", "db/p2_clean.csv"),
    "P3IT": ("db/p3it_dirty.csv", "db/p3it_clean.csv"),
    "P3FR": ("db/p3fr_dirty.csv", "db/p3fr_clean.csv"),
    "P4": ("db/p4_dirty.csv", "db/p4_clean.csv"),
}


def read_rows(path, is_clean):
    """Legge un CSV, porta i nomi delle colonne al formato del dirty e toglie gli spazi ai bordi."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = []
        for r in csv.DictReader(f):
            nr = {}
            for k, v in r.items():
                name = P4_INV.get(k, k)
                if is_clean:
                    name = CLEAN_TO_DIRTY.get(name, name)
                nr[name] = v.strip()
            rows.append(nr)
    return rows


def load(dirty_f, clean_f):
    dirty = read_rows(dirty_f, is_clean=False)
    clean = read_rows(clean_f, is_clean=True)
    # Il clean viene riallineato al dirty tramite la colonna 'index'
    clean_by_idx = {r["index"]: r for r in clean}
    clean = [clean_by_idx[r["index"]] for r in dirty]
    return dirty, clean


def build_index(dirty):
    idx = {}
    for lhs, rhs in RULES:
        d = defaultdict(Counter)
        for row in dirty:
            d[tuple(row[c] for c in lhs)][row[rhs]] += 1
        idx[(lhs, rhs)] = d
    return idx


def run(name, dirty_f, clean_f):
    dirty, clean = load(dirty_f, clean_f)
    idx = build_index(dirty)
    recs = []
    for row, crow in zip(dirty, clean):
        for t in FD_COLS:
            if row[t] == crow[t]:
                continue  # solo celle realmente sporche
            pred, rule = row[t], "nessuna"
            for lhs, rhs in RULES:
                if rhs != t:
                    continue
                key = tuple(row[c] for c in lhs)
                if any(k in MISSING for k in key):
                    continue
                cnt = idx[(lhs, rhs)].get(key)
                if not cnt:
                    continue
                cnt = Counter({k: v for k, v in cnt.items() if v > 0})
                cnt[row[t]] -= 1  # escludo la cella stessa
                cnt = Counter({k: v for k, v in cnt.items() if v > 0 and k not in MISSING})
                if not cnt:
                    continue
                pred = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                rule = f"{'+'.join(lhs)}->{rhs}"
                break
            recs.append({"dataset": name, "index": row["index"], "col": t,
                         "dirty": row[t], "clean": crow[t], "pred": pred,
                         "rule": rule, "correct": int(pred == crow[t]),
                         "changed": int(pred != row[t])})
    return recs


def main():
    all_recs = []
    for name, (d, c) in SETS.items():
        all_recs += run(name, os.path.join(HERE, d), os.path.join(HERE, c))

    out = os.path.join(HERE, "baseline", "baseline_results_stdlib.csv")
    cols = ["dataset", "index", "col", "dirty", "clean", "pred", "rule", "correct", "changed"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(all_recs)

    print("== Riepilogo per dataset ==")
    for name in SETS:
        g = [r for r in all_recs if r["dataset"] == name]
        n = len(g)
        cov = sum(r["rule"] != "nessuna" for r in g) / n * 100
        acc = sum(r["correct"] for r in g) / n * 100
        ch = [r for r in g if r["changed"] == 1]
        prec = sum(r["correct"] for r in ch) / len(ch) * 100 if ch else float("nan")
        print(f"{name:9s} celle sporche={n:4d}  copertura={cov:6.2f}%  accuratezza={acc:6.2f}%  "
              f"precisione sulle modificate={prec:6.2f}% (n={len(ch)})")

    print("\n== Invarianza: confronto con l'originale (stessa cella, stessa regola, stesso esito) ==")
    base = {(r["index"], r["col"]): r for r in all_recs if r["dataset"] == "original"}
    for name in ["P1", "P2", "P3IT", "P3FR", "P4"]:
        g = {(r["index"], r["col"]): r for r in all_recs if r["dataset"] == name}
        common = [k for k in base if k in g]
        same_rule = sum(base[k]["rule"] == g[k]["rule"] for k in common) / len(common) * 100
        same_ok = sum(base[k]["correct"] == g[k]["correct"] for k in common) / len(common) * 100
        print(f"{name}: celle in comune={len(common)}, stessa regola={same_rule:.2f}%, "
              f"stesso esito={same_ok:.2f}%, solo nell'originale={len(set(base) - set(g))}, "
              f"solo in {name}={len(set(g) - set(base))}")


if __name__ == "__main__":
    main()
