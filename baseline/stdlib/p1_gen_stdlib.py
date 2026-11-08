import os
import random
import csv

# Input originali e cartella di output della versione 2
# I CSV originali devono stare nella stessa cartella di questo script
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

# Colonne sostituite con valori sintetici. Rispetto alla v1 è inclusa EmergencyService.
PERTURB = ["ProviderNumber", "HospitalName", "Address1", "Address2", "Address3", "City", "State",
           "ZipCode", "CountyName", "PhoneNumber", "HospitalType", "HospitalOwner",
           "EmergencyService", "Condition", "MeasureCode", "MeasureName"]

# Dipendenze funzionali che devono valere sia sul clean originale sia su quello perturbato
FD_CHECK = [("ProviderNumber", "HospitalName"), ("ProviderNumber", "City"), ("ZipCode", "City"),
            ("City", "State"), ("City", "CountyName"), ("MeasureCode", "MeasureName"),
            ("MeasureCode", "Condition")]

# Carattere marcatore per sostituzioni e inserimenti nel dirty: si usa il primo compatibile
MARKERS = ["x", "q", "z", "j", "k", "w", "v"]
VOW = "aeiou"
CONS = "bcdfghjklmnpqrstvwyz"


# Sostituisce ogni lettera con una lettera della stessa classe (vocale o consonante),
# ogni cifra con una cifra, e lascia invariati spazi e punteggiatura.
# Così la lunghezza del valore non cambia e la struttura resta riconoscibile.
def synth(value, rng):
    out = []
    for ch in value:
        if ch.isascii() and ch.isalpha():
            c = rng.choice(VOW) if ch.lower() in VOW else rng.choice(CONS)
            out.append(c.upper() if ch.isupper() else c)
        elif ch.isdigit():
            out.append(str(rng.randrange(10)))
        else:
            out.append(ch)
    return "".join(out)


# Costruisce la mappa valore reale -> valore sintetico per una colonna.
# Il seme dipende da colonna, valore e tentativo, quindi il risultato è deterministico.
# Ogni sintetico è diverso dall'originale, non è già assegnato a un altro valore e non
# coincide con un valore reale della stessa colonna. "" ed "empty" restano invariati.
def build_map(values, col):
    originals = set(values)
    mapping = {"": "", "empty": "empty"}
    used = {"", "empty"}
    for v in sorted(originals):
        if v in mapping:
            continue
        # Un valore senza lettere né cifre non si può sostituire: lo script si ferma
        assert any(ch.isalnum() for ch in v), ("valore senza caratteri sostituibili", col, v)
        k = 0
        while True:
            cand = synth(v, random.Random(f"{col}|{v}|{k}"))
            if cand != v and cand not in used and cand not in originals:
                break
            k += 1
        mapping[v] = cand
        used.add(cand)
    assert len(set(mapping.values())) == len(mapping), col
    return mapping


# Distanza di Levenshtein tra due stringhe
def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# Allineamento ottimo tra a (clean) e b (dirty), come sequenza di operazioni:
# ("M", i) carattere uguale, ("S", i) sostituzione del carattere i di a,
# ("D", i) carattere i di a cancellato, ("I", None) carattere inserito in b.
def edit_ops(a, b):
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    ops, i, j = [], n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + (a[i - 1] != b[j - 1]):
            ops.append(("M" if a[i - 1] == b[j - 1] else "S", i - 1))
            i, j = i - 1, j - 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            ops.append(("D", i - 1))
            i -= 1
        else:
            ops.append(("I", None))
            j -= 1
    return ops[::-1]


# Riporta sul valore sintetico le stesse operazioni che separano il clean dallo sporco originale:
# i caratteri uguali restano quelli sintetici, le sostituzioni e gli inserimenti usano un marcatore,
# le cancellazioni non producono output. Il marcatore è scelto in modo che la distanza di Levenshtein
# tra sporco e pulito sintetici sia uguale a quella originale; se nessuno la preserva, lo script si ferma.
def corrupt_like(orig_clean, orig_dirty, new_clean):
    if orig_clean == orig_dirty:
        return new_clean
    ops = edit_ops(orig_clean, orig_dirty)
    target = lev(orig_clean, orig_dirty)
    for m in MARKERS:
        out, ok = [], True
        for op, i in ops:
            if op == "M":
                out.append(new_clean[i])
            elif op == "S":
                if new_clean[i] == m:
                    ok = False
                    break
                out.append(m)
            elif op == "I":
                out.append(m)
        if not ok:
            continue
        cand = "".join(out)
        if cand != new_clean and lev(cand, new_clean) == target:
            return cand
    raise AssertionError(("distanza di edit non preservabile", orig_clean, orig_dirty))



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


# True se nelle righe la colonna (o le colonne) lhs determina rhs
def functional(rows, lhs, rhs):
    seen = {}
    for r in rows:
        key = tuple(r[c] for c in lhs)
        if seen.setdefault(key, r[rhs]) != r[rhs]:
            return False
    return True


def main():
    # Caricamento: clean e dirty originali, senza spazi, dirty allineato al clean per 'index'
    clean_cols, clean = read_csv(D + "clean.csv")
    dirty_cols, dirty_rows = read_csv(D + "dirty.csv")
    by_idx = {r["index"]: r for r in dirty_rows}
    dirty = [by_idx[r["index"]] for r in clean]
    n = len(clean)

    # Una mappa biiettiva per ogni colonna perturbata
    maps = {col: build_map([r[col] for r in clean], col) for col in PERTURB}
    for col in PERTURB:
        mapped_values = set(maps[col].values()) - {"", "empty"}
        assert not (mapped_values & {r[col] for r in clean}), ("valore sintetico uguale a un reale", col)

    new_clean = [dict(r) for r in clean]
    new_dirty = [dict(r) for r in dirty]
    for col in PERTURB:
        for i in range(n):
            new_clean[i][col] = maps[col][clean[i][col]]
    for i in range(n):
        new_clean[i]["Stateavg"] = f"{new_clean[i]['State']}_{new_clean[i]['MeasureCode']}"

    # Dirty perturbato: stessi errori della versione originale, trasferiti sul nuovo valore pulito
    for col in PERTURB:
        dc = CLEAN_TO_DIRTY[col]
        for i in range(n):
            new_dirty[i][dc] = corrupt_like(clean[i][col], dirty[i][dc], new_clean[i][col])
    for i in range(n):
        new_dirty[i]["state_average"] = corrupt_like(clean[i]["Stateavg"], dirty[i]["state_average"],
                                                     new_clean[i]["Stateavg"])

    # Verifiche: stessa cardinalità e lunghezza, dipendenze funzionali preservate
    for col in PERTURB + ["Stateavg"]:
        assert len({r[col] for r in new_clean}) == len({r[col] for r in clean}), ("cardinalità", col)
        assert all(len(a[col]) == len(b[col]) for a, b in zip(new_clean, clean)), ("lunghezza", col)
    for lhs, rhs in FD_CHECK + [(("State", "MeasureCode"), "Stateavg")]:
        lhs = list(lhs) if isinstance(lhs, tuple) else [lhs]
        assert functional(clean, lhs, rhs) and functional(new_clean, lhs, rhs), (lhs, rhs)

    # Maschera degli errori e distanza di edit, cella per cella sulle colonne del dirty
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
    assert exact == total, ("distanza di edit", exact, total)

    write_csv(OUT + "p1_clean.csv", clean_cols, new_clean)
    write_csv(OUT + "p1_dirty.csv", dirty_cols, new_dirty)
    print(f"[P1] celle corrotte {corrupted_new} (originale {corrupted_orig}); "
          f"distanza di edit esatta {exact}/{total}")


if __name__ == "__main__":
    main()
