"""Baseline deterministica: valore più frequente tra le righe che condividono la chiave
di una dipendenza funzionale. Usa solo il dirty (nessuna ground truth nella predizione)."""
import pandas as pd
from collections import Counter, defaultdict

D = "/mnt/user-data/attachments/be48e8bc-8215-55c7-b4da-1e0267c0e58a/"
OUT = "/tmp/claude-0/-home-claude/be48e8bc-8215-55c7-b4da-1e0267c0e58a/scratchpad/"

CLEAN_TO_DIRTY = {
    "ProviderNumber": "provider_number", "HospitalName": "name", "Address1": "address_1",
    "Address2": "address_2", "Address3": "address_3", "City": "city", "State": "state",
    "ZipCode": "zip", "CountyName": "county", "PhoneNumber": "phone", "HospitalType": "type",
    "HospitalOwner": "owner", "EmergencyService": "emergency_service", "Condition": "condition",
    "MeasureCode": "measure_code", "MeasureName": "measure_name", "Score": "score",
    "Sample": "sample", "Stateavg": "state_average",
}
P4_RENAME = {"provider_number": "col_01", "name": "col_02", "address_1": "col_03", "address_2": "col_04",
    "address_3": "col_05", "city": "col_06", "state": "col_07", "zip": "col_08", "county": "col_09",
    "phone": "col_10", "type": "col_11", "owner": "col_12", "emergency_service": "col_13",
    "condition": "col_14", "measure_code": "col_15", "measure_name": "col_16", "score": "col_17",
    "sample": "col_18", "state_average": "col_19"}
P4_INV = {v: k for k, v in P4_RENAME.items()}

FD_COLS = ["provider_number", "name", "address_1", "city", "state", "zip", "county", "phone",
           "type", "owner", "emergency_service", "condition", "measure_code", "measure_name",
           "state_average"]

# (chiave, colonna determinata), in ordine di priorità per ciascuna colonna da riparare
RULES = [(("provider_number",), t) for t in ["name", "address_1", "city", "state", "zip",
          "county", "phone", "type", "owner", "emergency_service"]]
RULES += [(("phone",), "provider_number"), (("phone",), "zip"),
          (("zip",), "city"), (("zip",), "state"), (("zip",), "county"),
          (("measure_code",), "measure_name"), (("measure_code",), "condition"),
          (("state", "measure_code"), "state_average")]

MISSING = {"", "empty"}

def load(dirty_f, clean_f):
    dirty = pd.read_csv(dirty_f, dtype=str, keep_default_na=False)
    clean = pd.read_csv(clean_f, dtype=str, keep_default_na=False)
    if "col_01" in dirty.columns:
        dirty = dirty.rename(columns=P4_INV)
    if "col_01" in clean.columns:
        clean = clean.rename(columns=P4_INV)
    clean = clean.rename(columns=CLEAN_TO_DIRTY)
    dirty = dirty.apply(lambda s: s.str.strip())
    clean = clean.apply(lambda s: s.str.strip())
    clean = clean.set_index("index").loc[dirty["index"]].reset_index()
    return dirty.reset_index(drop=True), clean.reset_index(drop=True)

def build_index(dirty):
    idx = {}
    for lhs, rhs in RULES:
        d = defaultdict(Counter)
        for _, row in dirty.iterrows():
            key = tuple(row[c] for c in lhs)
            d[key][row[rhs]] += 1
        idx[(lhs, rhs)] = d
    return idx

def run(name, dirty_f, clean_f):
    dirty, clean = load(dirty_f, clean_f)
    idx = build_index(dirty)
    recs = []
    for i in range(len(dirty)):
        row = dirty.iloc[i]
        for t in FD_COLS:
            if row[t] == clean.at[i, t]:
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
                         "dirty": row[t], "clean": clean.at[i, t], "pred": pred,
                         "rule": rule, "correct": int(pred == clean.at[i, t]),
                         "changed": int(pred != row[t])})
    return pd.DataFrame(recs)

sets = {
    "original": ("/mnt/user-data/attachments/be48e8bc-8215-55c7-b4da-1e0267c0e58a/3192ed70-dirty.csv", "/mnt/user-data/attachments/be48e8bc-8215-55c7-b4da-1e0267c0e58a/0499ba75-clean.csv"),
    "P1": ("/tmp/claude-0/-home-claude/be48e8bc-8215-55c7-b4da-1e0267c0e58a/scratchpad/v2/p1_dirty.csv", "/tmp/claude-0/-home-claude/be48e8bc-8215-55c7-b4da-1e0267c0e58a/scratchpad/v2/p1_clean.csv"),
    "P2": ("/tmp/claude-0/-home-claude/be48e8bc-8215-55c7-b4da-1e0267c0e58a/scratchpad/v2/p2_dirty.csv", "/tmp/claude-0/-home-claude/be48e8bc-8215-55c7-b4da-1e0267c0e58a/scratchpad/v2/p2_clean.csv"),
    "P3": ("/tmp/claude-0/-home-claude/be48e8bc-8215-55c7-b4da-1e0267c0e58a/scratchpad/v2/p3_dirty.csv", "/tmp/claude-0/-home-claude/be48e8bc-8215-55c7-b4da-1e0267c0e58a/scratchpad/v2/p3_clean.csv"),
    "P4": ("/tmp/claude-0/-home-claude/be48e8bc-8215-55c7-b4da-1e0267c0e58a/scratchpad/v2/p4_dirty.csv", "/tmp/claude-0/-home-claude/be48e8bc-8215-55c7-b4da-1e0267c0e58a/scratchpad/v2/p4_clean.csv"),
}
all_res = pd.concat([run(k, *v) for k, v in sets.items()], ignore_index=True)
all_res.to_csv("/tmp/claude-0/-home-claude/be48e8bc-8215-55c7-b4da-1e0267c0e58a/scratchpad/v2/baseline_results_v2.csv", index=False)

print("== Riepilogo per dataset ==")
for k, g in all_res.groupby("dataset", sort=False):
    cov = (g["rule"] != "nessuna").mean() * 100
    acc = g["correct"].mean() * 100
    ch = g[g["changed"] == 1]
    prec = ch["correct"].mean() * 100 if len(ch) else float("nan")
    print(f"{k:9s} celle sporche={len(g):4d}  copertura={cov:6.2f}%  accuratezza={acc:6.2f}%  "
          f"precisione sulle modificate={prec:6.2f}% (n={len(ch)})")

print("\n== Invarianza: confronto con l'originale (stessa cella, stessa regola, stesso esito) ==")
base = all_res[all_res.dataset == "original"].set_index(["index", "col"])
for k in ["P1", "P2", "P3", "P4"]:
    g = all_res[all_res.dataset == k].set_index(["index", "col"])
    common = base.index.intersection(g.index)
    same_rule = (base.loc[common, "rule"] == g.loc[common, "rule"]).mean() * 100
    same_ok = (base.loc[common, "correct"] == g.loc[common, "correct"]).mean() * 100
    print(f"{k}: celle in comune={len(common)}, stessa regola={same_rule:.2f}%, stesso esito={same_ok:.2f}%, "
          f"solo nell'originale={len(base.index.difference(g.index))}, solo in {k}={len(g.index.difference(base.index))}")