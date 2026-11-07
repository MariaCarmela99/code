"""P3 variante francese: trapianto di dominio USA -> Francia con geografia coerente.
Stato -> région (blocco), città -> commune della région, département/CAP/ospedale derivati dalla commune.
Input aggiuntivo: baseline/laposte_cp_map.csv (Base officielle des codes postaux, La Poste, via data.gouv.fr)
Output: db/p3fr_clean.csv, db/p3fr_dirty.csv, baseline/p3fr_geo_map.csv
Tutti i valori sono ASCII minuscoli (accenti traslitterati), come nel dataset originale."""
import re
import pandas as pd

# I CSV di partenza stanno in code/db/ (lanciare lo script dalla directory code)
HERE = "./baseline/"  # path relativi alla directory code (lanciare gli script da code/)
D = "./db/"  # i CSV stanno in code/db/
OUT = D  # anche i dataset perturbati stanno in code/db/

CLEAN_TO_DIRTY = {
    "index": "index", "ProviderNumber": "provider_number", "HospitalName": "name",
    "Address1": "address_1", "Address2": "address_2", "Address3": "address_3",
    "City": "city", "State": "state", "ZipCode": "zip", "CountyName": "county",
    "PhoneNumber": "phone", "HospitalType": "type", "HospitalOwner": "owner",
    "EmergencyService": "emergency_service", "Condition": "condition",
    "MeasureCode": "measure_code", "MeasureName": "measure_name",
    "Score": "score", "Sample": "sample", "Stateavg": "state_average",
}

# Stato originale -> région INSEE (codice) e sigla di stato nel dataset P3FR.
# 'al' ha 37 città (alcune con più CAP) e va alla région più grande; 'ak' ha 2 città.
STATE_REGION = {"al": "76", "ak": "53"}      # Occitanie, Bretagne
STATE_NEW = {"al": "oc", "ak": "br"}

# Départements delle due région (codice = prime due cifre del codice INSEE della commune)
DEPARTEMENTS = {
    "53": {"22": "cotes d armor", "29": "finistere", "35": "ille et vilaine", "56": "morbihan"},
    "76": {"09": "ariege", "11": "aude", "12": "aveyron", "30": "gard", "31": "haute garonne",
           "32": "gers", "34": "herault", "46": "lot", "48": "lozere", "65": "hautes pyrenees",
           "66": "pyrenees orientales", "81": "tarn", "82": "tarn et garonne"},
}
# Prefisso telefonico geografico francese (numeri a 10 cifre): 02 Nord-Ovest, 04 Sud-Est, 05 Sud-Ovest
PREFIX_DEP = {"22": "02", "29": "02", "35": "02", "56": "02",
              "11": "04", "30": "04", "34": "04", "48": "04", "66": "04",
              "09": "05", "12": "05", "31": "05", "32": "05", "46": "05", "65": "05", "81": "05", "82": "05"}

STREETS = ["victor hugo", "jean jaures", "pasteur", "gambetta", "de la republique", "nationale",
    "du general de gaulle", "jules ferry", "voltaire", "moliere", "emile zola", "de la paix",
    "des ecoles", "du moulin", "de l eglise", "de la gare", "carnot", "jean moulin", "foch",
    "clemenceau", "aristide briand", "anatole france", "louis pasteur", "de verdun", "des lilas",
    "du chateau", "de la liberte", "jean jacques rousseau", "alsace lorraine", "saint martin",
    "des tilleuls", "du stade", "lamartine", "georges brassens", "marcel pagnol", "paul bert",
    "des acacias", "du marche", "de la fontaine", "hoche", "kleber", "danton", "condorcet",
    "denis diderot", "pierre curie"]

# Corrispondenza per significato: proprietario originale -> natura giuridica francese
OWNER_MAP = {
    "government - federal": "etablissement public national",
    "government - hospital district or authority": "groupement hospitalier de territoire",
    "government - local": "etablissement public communal",
    "government - state": "etablissement public regional",
    "proprietary": "clinique privee a but lucratif",
    "voluntary non-profit - church": "etablissement prive confessionnel",
    "voluntary non-profit - other": "etablissement prive d interet collectif",
    "voluntary non-profit - private": "fondation privee a but non lucratif",
}
COND_MAP = {
    "children s asthma care": "asthme de l enfant",
    "heart attack": "infarctus du myocarde",
    "heart failure": "insuffisance cardiaque",
    "pneumonia": "pneumonie",
    "surgical infection prevention": "prevention des infections chirurgicales",
}
TYPE_MAP = {"acute care hospitals": "centres hospitaliers de soins aigus"}
EMG_MAP = {"yes": "oui", "no": "non"}

# Codice originale -> codice francese (stesso significato clinico): solo il prefisso cambia
CODE_PREFIX = {"ami": "ima", "cac": "ase", "hf": "ic", "pn": "pne", "scip": "pic"}
MEASURES_FR = {
    "ima-1": "patients atteints d infarctus aigu du myocarde ayant recu de l aspirine a l arrivee aux urgences",
    "ima-2": "patients atteints d infarctus aigu du myocarde avec aspirine prescrite a la sortie de l hopital",
    "ima-3": "patients avec infarctus du myocarde et dysfonction ventriculaire gauche traites par iec ou ara2",
    "ima-4": "patients atteints d infarctus aigu du myocarde ayant recu des conseils pour arreter de fumer",
    "ima-5": "patients atteints d infarctus aigu du myocarde avec betabloquant prescrit a la sortie",
    "ima-7a": "patients avec infarctus du myocarde ayant recu une thrombolyse dans les 30 minutes suivant l arrivee",
    "ima-8a": "patients avec infarctus du myocarde ayant eu une angioplastie primaire dans les 90 minutes suivant l arrivee",
    "ase-1": "enfants hospitalises pour asthme ayant recu des bronchodilatateurs a courte duree d action",
    "ase-2": "enfants hospitalises pour asthme ayant recu des corticoides systemiques pendant le sejour",
    "ase-3": "enfants et familles ayant recu un plan de soins ecrit pour le domicile avant la sortie",
    "ic-1": "patients atteints d insuffisance cardiaque sortis avec des instructions ecrites completes pour le suivi",
    "ic-2": "patients atteints d insuffisance cardiaque ayant eu une evaluation de la fonction ventriculaire gauche",
    "ic-3": "patients avec insuffisance cardiaque et dysfonction ventriculaire traites par iec ou ara2",
    "ic-4": "patients fumeurs atteints d insuffisance cardiaque ayant recu une aide au sevrage tabagique",
    "pne-2": "patients ages hospitalises pour pneumonie ayant eu un depistage et une vaccination antipneumococcique",
    "pne-3b": "patients aux urgences pour pneumonie avec hemoculture realisee avant l antibiotherapie",
    "pne-4": "patients fumeurs hospitalises pour pneumonie ayant recu des conseils pour arreter de fumer",
    "pne-5c": "patients hospitalises pour pneumonie traites par antibiotique dans les 6 heures suivant l arrivee",
    "pne-6": "patients atteints de pneumonie communautaire traites par un antibiotique adapte selon les recommandations",
    "pne-7": "patients hospitalises pour pneumonie evalues et vaccines contre la grippe saisonniere",
    "pic-card-2": "patients chirurgicaux sous betabloquant au long cours ayant poursuivi le traitement en periode perioperatoire",
    "pic-inf-1": "patients chirurgicaux ayant recu une antibioprophylaxie dans l heure precedant l incision",
    "pic-inf-2": "patients chirurgicaux ayant recu l antibiotique adapte au type d intervention",
    "pic-inf-3": "patients chirurgicaux dont l antibioprophylaxie a ete arretee dans les 24 heures suivant l intervention",
    "pic-inf-4": "patients de chirurgie cardiaque avec glycemie postoperatoire controlee dans les premiers jours",
    "pic-inf-6": "patients chirurgicaux ayant eu une depilation preoperatoire a la tondeuse electrique et non au rasoir",
    "pic-vte-1": "patients chirurgicaux pour lesquels le medecin a prescrit un traitement preventif des caillots sanguins apres certaines interventions",
    "pic-vte-2": "patients chirurgicaux ayant recu une prophylaxie de la thrombose veineuse dans les 24 heures suivant l intervention",
}


def corrupt(clean_orig, dirty_orig, new_clean):
    if clean_orig == dirty_orig or not new_clean:
        return new_clean
    xs = [i for i, (c, d) in enumerate(zip(clean_orig, dirty_orig)) if c != d]
    chars = list(new_clean)
    for pos in xs:
        mp = int(round(pos * (len(chars) - 1) / max(1, len(clean_orig) - 1)))
        chars[mp] = "x"
    res = "".join(chars)
    return res if res != new_clean else ("x" + new_clean[1:])

def functional(df, x, y):
    return bool((df.groupby(x)[y].nunique() == 1).all())

# Nome commune La Poste (maiuscolo, abbreviato) -> forma leggibile minuscola: "ST JEAN" -> "saint jean"
def commune_name(raw):
    s = raw.lower()
    s = re.sub(r"\bste\b", "sainte", s)
    s = re.sub(r"\bst\b", "saint", s)
    return s

def translate_code(mc):
    pre, rest = mc.split("-", 1)
    return f"{CODE_PREFIX[pre]}-{rest}"

# ---------- caricamento ----------
clean = pd.read_csv(D + "clean.csv", dtype=str, keep_default_na=False).apply(lambda s: s.str.strip())
dirty = pd.read_csv(D + "dirty.csv", dtype=str, keep_default_na=False).apply(lambda s: s.str.strip())
dirty = dirty.set_index("index", drop=False).loc[clean["index"]].reset_index(drop=True)
clean = clean.reset_index(drop=True)

assert set(clean.State.unique()) == {"al", "ak"}, clean.State.unique()
checks = {
    "City->State": functional(clean, "City", "State"),
    "ZipCode->City": functional(clean, "ZipCode", "City"),
    "City->CountyName": functional(clean, "City", "CountyName"),
    "ProviderNumber->City": functional(clean, "ProviderNumber", "City"),
    "ProviderNumber->HospitalName": functional(clean, "ProviderNumber", "HospitalName"),
    "PhoneNumber->City": functional(clean, "PhoneNumber", "City"),
}
print("FD nel dataset originale:", checks)
assert all(checks.values()), "dipendenze originali non funzionali: lo script si ferma"

# ---------- tabella communes (La Poste) ----------
cp = pd.read_csv(HERE + "laposte_cp_map.csv", sep=";", dtype=str, keep_default_na=False, encoding="latin-1")
cp.columns = ["insee", "nom", "cp", "acheminement", "ligne_5"]
cp = cp.apply(lambda s: s.str.strip())
cp["dep"] = cp.insee.str[:2]
dep2reg = {dep: reg for reg, deps in DEPARTEMENTS.items() for dep in deps}
cp = cp[cp.dep.isin(dep2reg)].copy()
cp["reg"] = cp.dep.map(dep2reg)
comuni = (cp.groupby("insee")
          .agg(den=("nom", lambda x: commune_name(x.iloc[0])), dep=("dep", "first"),
               reg=("reg", "first"), caps=("cp", lambda x: sorted(set(x))))
          .reset_index().sort_values("insee").reset_index(drop=True))
comuni["prov"] = [DEPARTEMENTS[r][d] for r, d in zip(comuni.reg, comuni.dep)]

# ---------- città -> commune (stessa région dello stato, abbastanza CAP per le città) ----------
# Le città con più CAP vengono assegnate per prime: i comuni con più CAP sono pochi
# (in Occitanie solo Toulouse, Montpellier, Nimes, Perpignan) e non devono finire a città con un CAP solo.
city_map = {}
used, used_names, used_caps = set(), set(), set()
for st, reg in STATE_REGION.items():
    pool = comuni[comuni.reg == reg].reset_index(drop=True)
    cities = sorted(clean.loc[clean.State == st, "City"].unique())
    need = {c: clean.loc[(clean.State == st) & (clean.City == c), "ZipCode"].nunique() for c in cities}
    order = sorted(cities, key=lambda c: (-need[c], c))
    stride = max(1, len(pool) // (len(cities) * 2))
    for i, c in enumerate(order):
        cands = [j for j in range(len(pool)) if len(pool.at[j, "caps"]) >= need[c]
                 and pool.at[j, "insee"] not in used
                 and pool.at[j, "den"] not in used_names
                 and not (set(pool.at[j, "caps"]) & used_caps)]
        start = (i * stride) % len(pool)
        ordered = sorted(cands, key=lambda j: (j - start) % len(pool))
        assert ordered, (st, c, need[c])
        j = ordered[0]
        used.add(pool.at[j, "insee"])
        used_names.add(pool.at[j, "den"])
        used_caps |= set(pool.at[j, "caps"])
        city_map[(st, c)] = pool.iloc[j]

# ---------- CAP: ogni CAP originale -> CAP della commune ----------
zip_map = {}
for (st, c), row in city_map.items():
    zips = sorted(clean.loc[(clean.State == st) & (clean.City == c), "ZipCode"].unique())
    assert len(zips) <= len(row.caps), (c, len(zips), len(row.caps))
    for z, code in zip(zips, row.caps):
        assert z not in zip_map
        zip_map[z] = code
assert len(set(zip_map.values())) == len(zip_map), "CAP non univoci"

# ---------- ospedale: nome dalla commune; indirizzo per valore ----------
prov_info = clean.drop_duplicates("ProviderNumber")[["ProviderNumber", "State", "City"]].copy()
assert prov_info.ProviderNumber.is_unique
prov_info["comune"] = [city_map[(s, c)].den for s, c in zip(prov_info.State, prov_info.City)]
name_map = {}
for comune, grp in prov_info.groupby("comune"):
    provs = sorted(grp.ProviderNumber)
    for k, p in enumerate(provs, 1):
        name_map[p] = f"centre hospitalier {comune}" + ("" if len(provs) == 1 else f" {k}")

addr_map = {}
for i, a in enumerate(sorted(clean.Address1.unique())):
    addr_map[a] = a if a == "empty" else f"rue {STREETS[i % len(STREETS)]} {1 + i // len(STREETS)}"

# ---------- mappe per le colonne non geografiche ----------
def simple_map(vals, fn):
    return {v: fn(i, v) for i, v in enumerate(sorted(vals))}

prov_map = simple_map(clean.ProviderNumber.unique(), lambda i, v: f"{31001 + i:05d}")
# telefono: prefisso geografico del département della commune + cifre rimanenti, 10 cifre in totale
phone_rows = clean.drop_duplicates("PhoneNumber")[["PhoneNumber", "State", "City"]]
phone_map, counter = {}, {}
for _, r in phone_rows.iterrows():
    p = PREFIX_DEP[city_map[(r.State, r.City)].dep]
    counter[p] = counter.get(p, 0) + 1
    phone_map[r.PhoneNumber] = p + f"{counter[p]:0{10 - len(p)}d}"
assert all(len(v) == 10 for v in phone_map.values())
assert len(set(phone_map.values())) == len(phone_map), "telefoni non univoci"

assert set(OWNER_MAP) == set(clean.HospitalOwner.unique()), "proprietari originali non coperti"
assert set(COND_MAP) == set(clean.Condition.unique()), "condizioni originali non coperte"
assert set(TYPE_MAP) == set(clean.HospitalType.unique()), "tipi originali non coperti"
assert set(EMG_MAP) == set(clean.EmergencyService.unique()), "valori emergency non coperti"
mcode_map, mname_map = {}, {}
for mc in sorted(clean.MeasureCode.unique()):
    orig_mname = clean.loc[clean.MeasureCode == mc, "MeasureName"].iloc[0]
    mcode_map[mc] = translate_code(mc)
    mname_map[orig_mname] = MEASURES_FR[mcode_map[mc]]
assert set(mcode_map.values()) == set(MEASURES_FR), "codici francesi mancanti o non usati"
assert len(set(mcode_map.values())) == len(mcode_map), "codici francesi non univoci"
assert len(set(mname_map.values())) == len(mname_map), "nomi delle misure non univoci"

# ---------- costruzione ----------
new_clean = clean.copy()
new_dirty = dirty.copy()

for i in range(len(clean)):
    st, ct = clean.at[i, "State"], clean.at[i, "City"]
    row = city_map[(st, ct)]
    new_clean.at[i, "State"] = STATE_NEW[st]
    new_clean.at[i, "City"] = row.den
    new_clean.at[i, "CountyName"] = row.prov
    new_clean.at[i, "ZipCode"] = zip_map[clean.at[i, "ZipCode"]]
    new_clean.at[i, "HospitalName"] = name_map[clean.at[i, "ProviderNumber"]]
    new_clean.at[i, "Address1"] = addr_map[clean.at[i, "Address1"]]
    new_clean.at[i, "ProviderNumber"] = prov_map[clean.at[i, "ProviderNumber"]]
    new_clean.at[i, "PhoneNumber"] = phone_map[clean.at[i, "PhoneNumber"]]
    new_clean.at[i, "HospitalType"] = TYPE_MAP[clean.at[i, "HospitalType"]]
    new_clean.at[i, "HospitalOwner"] = OWNER_MAP[clean.at[i, "HospitalOwner"]]
    new_clean.at[i, "EmergencyService"] = EMG_MAP[clean.at[i, "EmergencyService"]]
    new_clean.at[i, "Condition"] = COND_MAP[clean.at[i, "Condition"]]
    new_clean.at[i, "MeasureCode"] = mcode_map[clean.at[i, "MeasureCode"]]
    new_clean.at[i, "MeasureName"] = mname_map[clean.at[i, "MeasureName"]]
    new_clean.at[i, "Stateavg"] = f"{new_clean.at[i, 'State']}_{new_clean.at[i, 'MeasureCode']}"
    # Sample: "N patients" resta uguale (in francese si scrive allo stesso modo)

geo_and_other = ["State", "City", "CountyName", "ZipCode", "HospitalName", "Address1", "ProviderNumber",
                 "PhoneNumber", "HospitalType", "HospitalOwner", "EmergencyService", "Condition",
                 "MeasureCode", "MeasureName", "Stateavg"]
for i in range(len(clean)):
    for cc in geo_and_other:
        dc = CLEAN_TO_DIRTY[cc]
        new_dirty.at[i, dc] = corrupt(clean.at[i, cc], dirty.at[i, dc], new_clean.at[i, cc])

# ---------- verifiche ----------
out = new_clean
fd_new = {
    "City->State": functional(out, "City", "State"),
    "ZipCode->City": functional(out, "ZipCode", "City"),
    "City->CountyName": functional(out, "City", "CountyName"),
    "ProviderNumber->HospitalName": functional(out, "ProviderNumber", "HospitalName"),
    "ProviderNumber->City": functional(out, "ProviderNumber", "City"),
    "PhoneNumber->City": functional(out, "PhoneNumber", "City"),
}
print("\nFD nel dataset P3FR:", fd_new)
assert all(fd_new.values()), "FD rotte nel dataset P3FR"

assert all(v.isascii() for col in out.columns for v in out[col]), "valori non ASCII nel clean"
den2dep = {r.den: r.dep for r in city_map.values()}
phone_bad = [i for i in range(len(out)) if not out.at[i, "PhoneNumber"].startswith(PREFIX_DEP[den2dep[out.at[i, "City"]]])]
print("telefoni con prefisso diverso dal département:", len(phone_bad))
assert not phone_bad
caps_set = set(zip(cp.nom.map(commune_name), cp.cp, cp.dep.map(lambda d: DEPARTEMENTS[dep2reg[d]][d]), cp.reg))
bad = []
for i in range(len(out)):
    key = (out.at[i, "City"], out.at[i, "ZipCode"], out.at[i, "CountyName"], STATE_REGION[clean.at[i, "State"]])
    if key not in caps_set:
        bad.append(key)
print("righe con commune/CAP/département non coerenti:", len(bad))
assert not bad, bad[:5]

orig_mask = dirty.ne(clean.rename(columns=CLEAN_TO_DIRTY)).to_numpy()
new_mask = new_dirty.ne(new_clean.rename(columns=CLEAN_TO_DIRTY)).to_numpy()
assert (orig_mask == new_mask).all(), "maschera degli errori diversa"

for col in ["State", "City", "ZipCode", "CountyName", "HospitalName", "Address1", "ProviderNumber"]:
    print(f"valori distinti {col}: originale={clean[col].nunique()} P3FR={out[col].nunique()}")
print("celle corrotte (tutte le colonne):", int(new_mask.sum()), f"(originale {int(orig_mask.sum())})")

# ---------- salvataggio ----------
new_clean.to_csv(OUT + "p3fr_clean.csv", index=False)
new_dirty.to_csv(OUT + "p3fr_dirty.csv", index=False)
mappa = pd.DataFrame([{"stato_originale": st, "citta_originale": c, "stato_p3fr": STATE_NEW[st],
                       "commune_p3fr": r.den, "code_insee": r.insee, "departement_p3fr": r.prov,
                       "region_code": r.reg, "codes_postaux": " ".join(r.caps), "prefixe": PREFIX_DEP[r.dep]}
                      for (st, c), r in city_map.items()])
mappa.to_csv(HERE + "p3fr_geo_map.csv", index=False)
print("\nMappa città:")
print(mappa.to_string(index=False))
print("\nSalvati:", OUT + "p3fr_clean.csv", OUT + "p3fr_dirty.csv", HERE + "p3fr_geo_map.csv")
