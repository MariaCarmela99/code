"""Generatore di P2 (rimappatura avversariale) senza pandas: usa solo la libreria standard.
Stessa logica di p2_gen.py. Lanciare dalla cartella code/: i CSV stanno in code/db/;
p2_clean.csv e p2_dirty.csv vengono scritti in code/db/."""
import csv
import os

D = "./db/"  # i CSV stanno in code/db/ (lanciare lo script dalla directory code)
OUT = D

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
# Colonne permutate e relativo spostamento del derangement
SHIFTS = {
    "HospitalName": 5, "Address1": 11, "City": 7, "State": 1, "ZipCode": 13, "CountyName": 9,
    "PhoneNumber": 17, "HospitalOwner": 3, "EmergencyService": 1, "MeasureName": 9, "Condition": 2,
}
# Dipendenze funzionali che devono valere sia sul clean originale sia su quello perturbato
FD_CHECK = [(["ProviderNumber"], "HospitalName"), (["ProviderNumber"], "City"), (["ZipCode"], "City"),
            (["City"], "State"), (["City"], "CountyName"), (["MeasureCode"], "MeasureName"),
            (["MeasureCode"], "Condition"), (["State", "MeasureCode"], "Stateavg")]


def read_csv(path):
    """Legge un CSV come (intestazione, lista di righe-dizionario), con gli spazi ai bordi rimossi."""
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


# Distanza di Levenshtein (solo per il report)
def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# True se nelle righe le colonne lhs determinano rhs
def functional(rows, lhs, rhs):
    seen = {}
    for r in rows:
        key = tuple(r[c] for c in lhs)
        if seen.setdefault(key, r[rhs]) != r[rhs]:
            return False
    return True


# Operatore N_prop: le posizioni corrotte vengono riproiettate in modo proporzionale sul nuovo valore
# e sostituite con 'x'. Non preserva la distanza di edit in modo esatto (P2 è dichiarata approssimata).
def corrupt_adversarial_value(clean_orig, dirty_orig, new_clean):
    if clean_orig == dirty_orig or not new_clean:
        return new_clean
    x_positions = [i for i, (c, d) in enumerate(zip(clean_orig, dirty_orig)) if c != d]
    chars = list(new_clean)
    for pos in x_positions:
        mapped_pos = int(round(pos * (len(chars) - 1) / max(1, len(clean_orig) - 1)))
        chars[mapped_pos] = "x"
    res = "".join(chars)
    return res if res != new_clean else ("x" + new_clean[1:])


# Derangement ciclico su U_j (dominio senza "" ed "empty"); con meno di due valori è l'identità
def make_derangement_map(values, shift):
    uniq = [v for v in sorted(set(values)) if v not in {"", "empty"}]
    n = len(uniq)
    mapping = {"": "", "empty": "empty"}
    if n <= 1:
        for v in uniq:
            mapping[v] = v
        return mapping
    eff_shift = shift % n or 1
    for i, val in enumerate(uniq):
        mapping[val] = uniq[(i + eff_shift) % n]
    return mapping


def main():
    clean_cols, clean = read_csv(D + "clean.csv")
    dirty_cols, dirty_rows = read_csv(D + "dirty.csv")
    by_idx = {r["index"]: r for r in dirty_rows}
    dirty = [by_idx[r["index"]] for r in clean]
    n = len(clean)

    # Una permutazione per colonna, con controllo di iniettività e assenza di punti fissi
    swap_maps = {col: make_derangement_map([r[col] for r in clean], s) for col, s in SHIFTS.items()}
    for col, mapping in swap_maps.items():
        keys = [k for k in mapping if k not in {"", "empty"}]
        assert len(set(mapping.values())) == len(mapping), ("non iniettiva", col)
        if len(keys) > 1:
            assert all(mapping[k] != k for k in keys), ("punto fisso", col)

    new_clean = [dict(r) for r in clean]
    new_dirty = [dict(r) for r in dirty]
    for col, mapping in swap_maps.items():
        dc = CLEAN_TO_DIRTY[col]
        for i in range(n):
            nc = mapping[clean[i][col]]
            new_clean[i][col] = nc
            new_dirty[i][dc] = corrupt_adversarial_value(clean[i][col], dirty[i][dc], nc)
    # Stateavg ricostruito come {State}_{MeasureCode} sui valori permutati
    for i in range(n):
        nc = f"{new_clean[i]['State']}_{new_clean[i]['MeasureCode']}"
        new_clean[i]["Stateavg"] = nc
        new_dirty[i]["state_average"] = corrupt_adversarial_value(
            clean[i]["Stateavg"], dirty[i]["state_average"], nc)

    # Verifiche: cardinalità per colonna e dipendenze funzionali
    for col in SHIFTS:
        assert len({r[col] for r in new_clean}) == len({r[col] for r in clean}), ("cardinalità", col)
    for lhs, rhs in FD_CHECK:
        assert functional(clean, lhs, rhs) and functional(new_clean, lhs, rhs), (lhs, rhs)

    # Maschera degli errori identica all'originale; report della distanza di edit
    inv = {v: k for k, v in CLEAN_TO_DIRTY.items()}
    corrupted_orig = corrupted_new = exact = total = 0
    for i in range(n):
        for dc in dirty_cols:
            cc = inv[dc]
            o = dirty[i][dc] != clean[i][cc]
            m = new_dirty[i][dc] != new_clean[i][cc]
            assert o == m, ("maschera degli errori diversa", i, dc)
            corrupted_orig += o
            corrupted_new += m
            if o:
                total += 1
                exact += int(lev(dirty[i][dc], clean[i][cc]) == lev(new_dirty[i][dc], new_clean[i][cc]))

    write_csv(OUT + "p2_clean.csv", clean_cols, new_clean)
    write_csv(OUT + "p2_dirty.csv", dirty_cols, new_dirty)
    print(f"[P2] celle corrotte {corrupted_new} (originale {corrupted_orig}); "
          f"distanza di edit esatta {exact}/{total} (approssimata per costruzione)")


if __name__ == "__main__":
    main()
