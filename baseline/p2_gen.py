import os
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
# Colonne permutate e relativo shift del derangement (la permutazione è un cerchio di ampiezza shift)
SHIFTS = {
    "HospitalName": 5, "Address1": 11, "City": 7, "State": 1, "ZipCode": 13, "CountyName": 9,
    "PhoneNumber": 17, "HospitalOwner": 3, "EmergencyService": 1, "MeasureName": 9, "Condition": 2,
}
# Dipendenze funzionali che devono valere sia sul clean originale sia su quello perturbato
FD_CHECK = [(["ProviderNumber"], "HospitalName"), (["ProviderNumber"], "City"), (["ZipCode"], "City"),
            (["City"], "State"), (["City"], "CountyName"), (["MeasureCode"], "MeasureName"),
            (["MeasureCode"], "Condition"), (["State", "MeasureCode"], "Stateavg")]


# Distanza di Levenshtein tra due stringhe (usata solo per il report, non per un'asserzione)
def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# True se in df la colonna lhs determina rhs
def functional(df, lhs, rhs):
    return bool((df.groupby(lhs)[rhs].nunique() == 1).all())


# Inietta l'errore in modo proporzionale: le posizioni in cui clean e dirty originali differiscono
# vengono riproiettate sulla lunghezza del nuovo valore e sostituite con 'x'. Non preserva la
# distanza di edit in modo esatto (per questo P2 è dichiarata approssimata): in alcuni casi
# due posizioni cadono sulla stessa cella. Se il nuovo valore è vuoto la cella resta invariata.
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


# Permutazione senza punti fissi sui valori reali: ogni valore va nel successivo di shift posizioni
# (ciclica sull'ordine alfabetico). "" ed "empty" restano invariati. Con meno di due valori
# l'unica permutazione possibile è l'identità.
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
    # Caricamento: clean e dirty originali, senza spazi, dirty allineato al clean per 'index'
    clean = pd.read_csv(D + "0499ba75-clean.csv", dtype=str, keep_default_na=False)
    clean = clean.apply(lambda s: s.str.strip()).reset_index(drop=True)
    dirty = pd.read_csv(D + "3192ed70-dirty.csv", dtype=str, keep_default_na=False)
    dirty = dirty.apply(lambda s: s.str.strip())
    dirty = dirty.set_index("index", drop=False).loc[clean["index"]].reset_index(drop=True)
    n = len(clean)

    # Una permutazione per colonna. Le verifiche controllano iniettività e assenza di punti fissi
    swap_maps = {col: make_derangement_map(clean[col].tolist(), shift) for col, shift in SHIFTS.items()}
    for col, mapping in swap_maps.items():
        keys = [k for k in mapping if k not in {"", "empty"}]
        assert len(set(mapping.values())) == len(mapping), ("non iniettiva", col)
        if len(keys) > 1:
            assert all(mapping[k] != k for k in keys), ("punto fisso", col)

    # Clean e dirty perturbati: il valore pulito è permutato, l'errore viene riproiettato
    new_clean = clean.copy()
    new_dirty = dirty.copy()
    for col, mapping in swap_maps.items():
        dc = CLEAN_TO_DIRTY[col]
        for i in range(n):
            nc = mapping[clean.at[i, col]]
            new_clean.at[i, col] = nc
            new_dirty.at[i, dc] = corrupt_adversarial_value(clean.at[i, col], dirty.at[i, dc], nc)
    # Stateavg ricostruito come {State}_{MeasureCode} sui valori permutati
    for i in range(n):
        nc = f"{new_clean.at[i, 'State']}_{new_clean.at[i, 'MeasureCode']}"
        new_clean.at[i, "Stateavg"] = nc
        new_dirty.at[i, "state_average"] = corrupt_adversarial_value(
            clean.at[i, "Stateavg"], dirty.at[i, "state_average"], nc)

    # Verifiche: cardinalità per colonna e dipendenze funzionali sul clean
    for col in SHIFTS:
        assert new_clean[col].nunique() == clean[col].nunique(), ("cardinalità", col)
    for lhs, rhs in FD_CHECK:
        assert functional(clean, lhs, rhs) and functional(new_clean, lhs, rhs), (lhs, rhs)

    # La maschera degli errori deve restare identica a quella originale
    renamed_clean = new_clean.rename(columns=CLEAN_TO_DIRTY)[new_dirty.columns]
    orig_mask = dirty.ne(clean.rename(columns=CLEAN_TO_DIRTY)[dirty.columns]).values
    new_mask = new_dirty.ne(renamed_clean).values
    assert (orig_mask == new_mask).all(), "maschera degli errori diversa"

    # Solo report: quante celle sporche conservano la distanza di edit originale (non asserito)
    renamed_orig = clean.rename(columns=CLEAN_TO_DIRTY)[dirty.columns]
    exact, total = 0, 0
    for col in dirty.columns:
        for i in range(n):
            if dirty.at[i, col] != renamed_orig.at[i, col]:
                total += 1
                exact += int(lev(dirty.at[i, col], renamed_orig.at[i, col]) ==
                             lev(new_dirty.at[i, col], renamed_clean.at[i, col]))

    new_clean.to_csv(OUT + "p2_clean.csv", index=False)
    new_dirty.to_csv(OUT + "p2_dirty.csv", index=False)
    print(f"[P2] celle corrotte {int(new_mask.sum())} (originale {int(orig_mask.sum())}); "
          f"distanza di edit esatta {exact}/{total} (approssimata per costruzione)")


if __name__ == "__main__":
    main()
