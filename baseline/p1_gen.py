import os
import random
import pandas as pd

# Input originali e cartella di output della versione 2
# I CSV originali devono stare nella stessa cartella di questo script
D = os.path.dirname(os.path.abspath(__file__)) + os.sep
OUT = D  # p1_clean.csv e p1_dirty.csv vengono scritti nella stessa cartella

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


# True se in df la colonna lhs determina rhs (ogni valore di lhs ha un solo valore di rhs)
def functional(df, lhs, rhs):
    return bool((df.groupby(lhs)[rhs].nunique() == 1).all())


def main():
    # Caricamento: clean e dirty originali, senza spazi, dirty allineato al clean per 'index'
    clean = pd.read_csv(D + "0499ba75-clean.csv", dtype=str, keep_default_na=False)
    clean = clean.apply(lambda s: s.str.strip()).reset_index(drop=True)
    dirty = pd.read_csv(D + "3192ed70-dirty.csv", dtype=str, keep_default_na=False)
    dirty = dirty.apply(lambda s: s.str.strip())
    dirty = dirty.set_index("index", drop=False).loc[clean["index"]].reset_index(drop=True)
    n = len(clean)

    # Una mappa biiettiva per ogni colonna perturbata
    maps = {col: build_map(clean[col].tolist(), col) for col in PERTURB}
    # Nessun valore sintetico deve coincidere con un valore reale della stessa colonna
    for col in PERTURB:
        mapped_values = set(maps[col].values()) - {"", "empty"}
        assert not (mapped_values & set(clean[col])), ("valore sintetico uguale a un reale", col)

    new_clean = clean.copy()
    new_dirty = dirty.copy()
    # Clean perturbato: ogni valore sostituito con il sintetico della sua mappa
    for col in PERTURB:
        for i in range(n):
            new_clean.at[i, col] = maps[col][clean.at[i, col]]
    # Stateavg ricostruito come {State}_{MeasureCode}, coerente con i valori perturbati
    for i in range(n):
        new_clean.at[i, "Stateavg"] = f"{new_clean.at[i, 'State']}_{new_clean.at[i, 'MeasureCode']}"

    # Dirty perturbato: stessi errori della versione originale, trasferiti sul nuovo valore pulito
    for col in PERTURB:
        dc = CLEAN_TO_DIRTY[col]
        for i in range(n):
            new_dirty.at[i, dc] = corrupt_like(clean.at[i, col], dirty.at[i, dc], new_clean.at[i, col])
    for i in range(n):
        new_dirty.at[i, "state_average"] = corrupt_like(clean.at[i, "Stateavg"], dirty.at[i, "state_average"],
                                                        new_clean.at[i, "Stateavg"])

    # Verifiche: stessa cardinalità e stessa lunghezza delle celle, dipendenze funzionali preservate
    for col in PERTURB + ["Stateavg"]:
        assert new_clean[col].nunique() == clean[col].nunique(), ("cardinalità", col)
        assert all(len(a) == len(b) for a, b in zip(new_clean[col], clean[col])), ("lunghezza", col)
    for lhs, rhs in FD_CHECK + [(("State", "MeasureCode"), "Stateavg")]:
        if isinstance(lhs, tuple):
            assert functional(clean, list(lhs), rhs) and functional(new_clean, list(lhs), rhs), (lhs, rhs)
        else:
            assert functional(clean, [lhs], rhs) and functional(new_clean, [lhs], rhs), (lhs, rhs)

    # La maschera degli errori (celle sporche) deve restare identica a quella originale
    renamed_clean = new_clean.rename(columns=CLEAN_TO_DIRTY)[new_dirty.columns]
    orig_mask = dirty.ne(clean.rename(columns=CLEAN_TO_DIRTY)[dirty.columns]).values
    new_mask = new_dirty.ne(renamed_clean).values
    assert (orig_mask == new_mask).all(), "maschera degli errori diversa"

    # Distanza di edit: per ogni cella sporca, deve essere uguale a quella originale
    renamed_orig = clean.rename(columns=CLEAN_TO_DIRTY)
    exact, total = 0, 0
    for col in new_dirty.columns:
        for i in range(n):
            if dirty.at[i, col] != renamed_orig.at[i, col]:
                total += 1
                e0 = lev(dirty.at[i, col], renamed_orig.at[i, col])
                e1 = lev(new_dirty.at[i, col], renamed_clean.at[i, col])
                exact += int(e0 == e1)
    assert exact == total, ("distanza di edit", exact, total)

    new_clean.to_csv(OUT + "p1_clean.csv", index=False)
    new_dirty.to_csv(OUT + "p1_dirty.csv", index=False)
    print(f"[P1] celle corrotte {int(new_mask.sum())} (originale {int(orig_mask.sum())}); "
          f"distanza di edit esatta {exact}/{total}")


if __name__ == "__main__":
    main()
