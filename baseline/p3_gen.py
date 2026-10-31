"""P3 corretta: dominio italiano con geografia coerente.
Stato -> regione (blocco), città -> comune della regione, provincia/CAP/ospedale derivati dal comune.
Output nella cartella di lavoro: p3_clean.csv, p3_dirty.csv, p3_mappa_geografica.csv"""
import os
import pandas as pd

# I file CSV di partenza devono stare nella stessa cartella di questo script
D = os.path.dirname(os.path.abspath(__file__)) + os.sep
OUT = D  # tutti i file nella stessa cartella dello script

CLEAN_TO_DIRTY = {
    "index": "index", "ProviderNumber": "provider_number", "HospitalName": "name",
    "Address1": "address_1", "Address2": "address_2", "Address3": "address_3",
    "City": "city", "State": "state", "ZipCode": "zip", "CountyName": "county",
    "PhoneNumber": "phone", "HospitalType": "type", "HospitalOwner": "owner",
    "EmergencyService": "emergency_service", "Condition": "condition",
    "MeasureCode": "measure_code", "MeasureName": "measure_name",
    "Score": "score", "Sample": "sample", "Stateavg": "state_average",
}

# Stato originale -> regione ISTAT (codice) e sigla di stato nel dataset P3
STATE_REGION = {"al": "03", "ak": "05"}      # Lombardia, Veneto
STATE_NEW = {"al": "lo", "ak": "ve"}

STREETS = ["garibaldi", "mazzini", "cavour", "dante alighieri", "verdi", "roma", "milano",
    "matteotti", "gramsci", "leopardi", "manzoni", "carducci", "pascoli", "petrarca",
    "boccaccio", "galilei", "fermi", "marconi", "volta", "torricelli", "vespucci", "colombo",
    "da vinci", "michelangelo", "raffaello", "donatello", "tiziano", "tintoretto", "tiepolo",
    "canova", "rossini", "bellini", "donizetti", "puccini", "vivaldi", "corelli", "toscanini",
    "de gasperi", "einaudi", "turati", "gobetti", "amendola", "calamandrei", "parri", "pertini"]

OWNERS_ITALIANI = [
    "azienda socio sanitaria territoriale - asst", "azienda ulss regionale",
    "ente ecclesiastico civilmente riconosciuto", "fondazione irccs di diritto pubblico",
    "istituto di ricovero e cura a carattere scientifico", "ospedale classificato no-profit",
    "presidio ospedaliero a gestione diretta", "struttura sanitaria privata accreditata ssn"]
CONDITIONS_ITALIANE = [
    "cura dell asma pediatrico", "infarto miocardico acuto", "insufficienza cardiaca congestizia",
    "polmonite acquisita in comunita", "prevenzione delle infezioni chirurgiche"]
MEASURES_ITALIANE = [
    ("ima-1", "pazienti con infarto miocardico acuto a cui e stata somministrata aspirina all arrivo in pronto soccorso"),
    ("ima-2", "pazienti con infarto miocardico acuto a cui e stata prescritta aspirina alla dimissione ospedaliera"),
    ("ima-3", "pazienti con infarto miocardico e disfunzione ventricolare sinistra trattati con ace-inibitore o sartano"),
    ("ima-4", "pazienti con infarto miocardico acuto che hanno ricevuto consulenza per la cessazione del fumo"),
    ("ima-5", "pazienti con infarto miocardico acuto a cui e stato prescritto un betabloccante alla dimissione"),
    ("ima-7a", "pazienti con infarto miocardico sottoposti a trombolisi entro 30 minuti dall ingresso in ospedale"),
    ("ima-8a", "pazienti con infarto miocardico sottoposti ad angioplastica primaria entro 90 minuti dall arrivo"),
    ("asm-1", "bambini ricoverati per asma che hanno ricevuto farmaci broncodilatatori a breve durata d azione"),
    ("asm-2", "bambini ricoverati per asma che hanno ricevuto corticosteroidi sistemici durante la degenza"),
    ("asm-3", "bambini e familiari che hanno ricevuto un piano terapeutico domiciliare scritto prima della dimissione"),
    ("icc-1", "pazienti con insufficienza cardiaca dimessi con istruzioni scritte complete per il monitoraggio clinico"),
    ("icc-2", "pazienti con insufficienza cardiaca sottoposti a valutazione della funzione ventricolare sinistra"),
    ("icc-3", "pazienti con insufficienza cardiaca e disfunzione ventricolare trattati con ace-inibitore o sartano"),
    ("icc-4", "pazienti fumatori con insufficienza cardiaca che hanno ricevuto supporto antifumo durante il ricovero"),
    ("pol-2", "pazienti anziani ricoverati per polmonite sottoposti a screening e vaccinazione antipneumococcica"),
    ("pol-3b", "pazienti in pronto soccorso per polmonite con emocoltura eseguita prima della terapia antibiotica"),
    ("pol-4", "pazienti fumatori ricoverati per polmonite che hanno ricevuto consulenza per smettere di fumare"),
    ("pol-5c", "pazienti ospedalizzati per polmonite trattati con antibiotico entro 6 ore dall accesso in ospedale"),
    ("pol-6", "pazienti con polmonite acquisita in comunita trattati con regime antibiotico appropriato secondo linee guida"),
    ("pol-7", "pazienti ricoverati per polmonite valutati e sottoposti a vaccinazione antinfluenzale stagionale"),
    ("pic-card-2", "pazienti chirurgici in terapia cronica con betabloccanti che hanno mantenuto il trattamento nel periodo perioperatorio"),
    ("pic-inf-1", "pazienti chirurgici sottoposti a profilassi antibiotica entro un ora prima dell incisione chirurgica"),
    ("pic-inf-2", "pazienti chirurgici che hanno ricevuto il principio attivo antibiotico appropriato per il tipo di intervento"),
    ("pic-inf-3", "pazienti chirurgici la cui profilassi antibiotica e stata sospesa entro 24 ore dal termine della chirurgia"),
    ("pic-inf-4", "pazienti cardiochirurgici con glicemia postoperatoria mantenuta sotto controllo nei primi giorni dopo l intervento"),
    ("pic-inf-6", "pazienti chirurgici sottoposti a tricotomia preoperatoria mediante clipper elettrico e non con rasoio"),
    ("pic-vte-1", "pazienti chirurgici per i quali il medico ha prescritto trattamenti per prevenire la formazione di coaguli di sangue dopo alcuni tipi di intervento"),
    ("pic-vte-2", "pazienti chirurgici sottoposti a profilassi del tromboembolismo venoso entro 24 ore dall intervento"),
]

# Corrispondenza per significato clinico: codice originale -> codice italiano (opzione A)
MEASURE_MAP = {
    "ami-1": "ima-1", "ami-2": "ima-2", "ami-3": "ima-3", "ami-4": "ima-4", "ami-5": "ima-5",
    "ami-7a": "ima-7a", "ami-8a": "ima-8a",
    "cac-1": "asm-1", "cac-2": "asm-2", "cac-3": "asm-3",
    "hf-1": "icc-1", "hf-2": "icc-2", "hf-3": "icc-3", "hf-4": "icc-4",
    "pn-2": "pol-2", "pn-3b": "pol-3b", "pn-4": "pol-4", "pn-5c": "pol-5c", "pn-6": "pol-6", "pn-7": "pol-7",
    "scip-card-2": "pic-card-2", "scip-inf-1": "pic-inf-1", "scip-inf-2": "pic-inf-2",
    "scip-inf-3": "pic-inf-3", "scip-inf-4": "pic-inf-4", "scip-inf-6": "pic-inf-6",
    "scip-vte-1": "pic-vte-1", "scip-vte-2": "pic-vte-2",
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

# ---------- caricamento ----------
clean = pd.read_csv(D + "0499ba75-clean.csv", dtype=str, keep_default_na=False).apply(lambda s: s.str.strip())
dirty = pd.read_csv(D + "3192ed70-dirty.csv", dtype=str, keep_default_na=False).apply(lambda s: s.str.strip())
dirty = dirty.set_index("index", drop=False).loc[clean["index"]].reset_index(drop=True)
clean = clean.reset_index(drop=True)

assert set(clean.State.unique()) == {"al", "ak"}, clean.State.unique()
checks = {
    "City->State": functional(clean, "City", "State"),
    "ZipCode->City": functional(clean, "ZipCode", "City"),
    "City->CountyName": functional(clean, "City", "CountyName"),
    "ProviderNumber->City": functional(clean, "ProviderNumber", "City"),
    "ProviderNumber->HospitalName": functional(clean, "ProviderNumber", "HospitalName"),
}
print("FD nel dataset originale:", checks)
assert all(checks.values()), "dipendenze originali non funzionali: lo script si ferma"

# ---------- tabella comuni (ISTAT + CAP) ----------
cap = pd.read_csv(D + "f9c7760a-gi_comuni_cap.csv", sep=";", dtype=str, keep_default_na=False)
cap = cap.apply(lambda s: s.str.strip())
comuni = (cap.groupby("codice_istat")
          .agg(den=("denominazione_ita", "first"), prov=("denominazione_provincia", "first"),
               reg=("codice_regione", "first"), caps=("cap", lambda x: sorted(set(x))))
          .reset_index().sort_values("codice_istat").reset_index(drop=True))
comuni = comuni.rename(columns={"codice_istat": "codice_istat"})

# ---------- città -> comune (stessa regione dello stato, abbastanza CAP per le città) ----------
city_map = {}
used = set()
used_caps = set()
for st, reg in STATE_REGION.items():
    pool = comuni[comuni.reg == reg].reset_index(drop=True)
    cities = sorted(clean.loc[clean.State == st, "City"].unique())
    need = {c: clean.loc[(clean.State == st) & (clean.City == c), "ZipCode"].nunique() for c in cities}
    stride = max(1, len(pool) // (len(cities) * 2))
    for i, c in enumerate(cities):
        cands = [j for j in range(len(pool)) if len(pool.at[j, "caps"]) >= need[c]
                 and pool.at[j, "codice_istat"] not in used
                 and not (set(pool.at[j, "caps"]) & used_caps)]
        start = (i * stride) % len(pool)
        ordered = sorted(cands, key=lambda j: (j - start) % len(pool))
        assert ordered, (st, c, need[c])
        j = ordered[0]
        used.add(pool.at[j, "codice_istat"])
        used_caps |= set(pool.at[j, "caps"])
        city_map[(st, c)] = pool.iloc[j]

# ---------- CAP: ogni CAP originale -> CAP del comune ----------
zip_map = {}
for (st, c), row in city_map.items():
    zips = sorted(clean.loc[(clean.State == st) & (clean.City == c), "ZipCode"].unique())
    assert len(zips) <= len(row.caps), (c, len(zips), len(row.caps))
    for z, cp in zip(zips, row.caps):
        assert z not in zip_map
        zip_map[z] = cp
assert len(set(zip_map.values())) == len(zip_map), "CAP non univoci"

# ---------- ospedale: nome dal comune; indirizzo per valore ----------
prov_info = clean.drop_duplicates("ProviderNumber")[["ProviderNumber", "State", "City"]].copy()
assert prov_info.ProviderNumber.is_unique
prov_info["comune"] = [city_map[(s, c)].den for s, c in zip(prov_info.State, prov_info.City)]
name_map = {}
for comune, grp in prov_info.groupby("comune"):
    provs = sorted(grp.ProviderNumber)
    for k, p in enumerate(provs, 1):
        name_map[p] = f"presidio ospedaliero {comune.lower()}" + ("" if len(provs) == 1 else f" {k}")

addr_map = {}
for i, a in enumerate(sorted(clean.Address1.unique())):
    addr_map[a] = a if a == "empty" else f"via {STREETS[i % len(STREETS)]} {1 + i // len(STREETS)}"

# ---------- prefissi telefonici per comune (fonti: schede tuttitalia, pagine provinciali) ----------
PREFIX = {
    "Agra": "0332", "Brunello": "0332", "Castelseprio": "0331", "Ispra": "0332",
    "Oggiona con Santo Stefano": "0331", "Travedona-Monate": "0332",
    "Milano": "02", "Abbiategrasso": "02", "Busto Garolfo": "0331", "Colturano": "02",
    "Legnano": "0331", "Ozzero": "02", "Turbigo": "0331",
    "Alzate Brianza": "031", "Caglio": "031", "Grandate": "031", "Mariano Comense": "031",
    "Plesio": "0344", "Tavernerio": "031", "Centro Valle Intelvi": "031",
    "Bergamo": "035", "Alzano Lombardo": "035", "Bolgare": "035", "Capizzone": "035",
    "Cerete": "0346", "Dalmine": "035", "Ghisalba": "035", "Martinengo": "0363",
    "Pagazzano": "0363", "Romano di Lombardia": "0363",   # provvisorio, non verificato
    "Sedrina": "0345", "Trescore Balneario": "035", "Villa d'Almè": "035",  # provvisorio, non verificato
    "Brescia": "030", "Lovero": "0342", "Sondalo": "0342", "Montalto Pavese": "0383",
    "Affi": "045", "Laghi": "0445",
}

# ---------- mappe per le colonne non geografiche (come prima) ----------
def simple_map(vals, fn):
    return {v: fn(i, v) for i, v in enumerate(sorted(vals))}

prov_map = simple_map(clean.ProviderNumber.unique(), lambda i, v: f"{30101 + i:05d}")
# telefono: prefisso del comune assegnato + cifre rimanenti, lunghezza totale 10
phone_rows = clean.drop_duplicates("PhoneNumber")[["PhoneNumber", "State", "City"]]
phone_map, counter = {}, {}
for _, r in phone_rows.iterrows():
    comune = city_map[(r.State, r.City)].den
    p = PREFIX[comune]
    counter[p] = counter.get(p, 0) + 1
    phone_map[r.PhoneNumber] = p + f"{counter[p]:0{10 - len(p)}d}"
assert all(len(v) == 10 for v in phone_map.values())
owner_map = simple_map(clean.HospitalOwner.unique(), lambda i, v: OWNERS_ITALIANI[i])
cond_map = simple_map(clean.Condition.unique(), lambda i, v: CONDITIONS_ITALIANE[i])
type_map = {"acute care hospitals": "presidi ospedalieri per acuti"}
emg_map = {"yes": "si", "no": "no"}
IT_NAME = dict(MEASURES_ITALIANE)
assert set(MEASURE_MAP) == set(clean.MeasureCode.unique()), "codici originali non coperti"
assert set(MEASURE_MAP.values()) == set(IT_NAME), "codici italiani mancanti o non usati"
mcode_map, mname_map = {}, {}
for mc in sorted(clean.MeasureCode.unique()):
    orig_mname = clean.loc[clean.MeasureCode == mc, "MeasureName"].iloc[0]
    mcode_map[mc] = MEASURE_MAP[mc]
    mname_map[orig_mname] = IT_NAME[MEASURE_MAP[mc]]
assert len(set(mcode_map.values())) == len(mcode_map), "codici italiani non univoci"

# ---------- costruzione ----------
new_clean = clean.copy()
new_dirty = dirty.copy()

for i in range(len(clean)):
    st, ct = clean.at[i, "State"], clean.at[i, "City"]
    row = city_map[(st, ct)]
    new_clean.at[i, "State"] = STATE_NEW[st]
    new_clean.at[i, "City"] = row.den.lower()
    new_clean.at[i, "CountyName"] = row.prov.lower()
    new_clean.at[i, "ZipCode"] = zip_map[clean.at[i, "ZipCode"]]
    new_clean.at[i, "HospitalName"] = name_map[clean.at[i, "ProviderNumber"]]
    new_clean.at[i, "Address1"] = addr_map[clean.at[i, "Address1"]]
    new_clean.at[i, "ProviderNumber"] = prov_map[clean.at[i, "ProviderNumber"]]
    new_clean.at[i, "PhoneNumber"] = phone_map[clean.at[i, "PhoneNumber"]]
    new_clean.at[i, "HospitalType"] = type_map.get(clean.at[i, "HospitalType"], clean.at[i, "HospitalType"])
    new_clean.at[i, "HospitalOwner"] = owner_map[clean.at[i, "HospitalOwner"]]
    new_clean.at[i, "EmergencyService"] = emg_map.get(clean.at[i, "EmergencyService"], clean.at[i, "EmergencyService"])
    new_clean.at[i, "Condition"] = cond_map[clean.at[i, "Condition"]]
    new_clean.at[i, "MeasureCode"] = mcode_map[clean.at[i, "MeasureCode"]]
    new_clean.at[i, "MeasureName"] = mname_map[clean.at[i, "MeasureName"]]

geo_and_other = ["State", "City", "CountyName", "ZipCode", "HospitalName", "Address1", "ProviderNumber",
                 "PhoneNumber", "HospitalType", "HospitalOwner", "EmergencyService", "Condition",
                 "MeasureCode", "MeasureName"]
for i in range(len(clean)):
    new_clean.at[i, "Stateavg"] = f"{new_clean.at[i, 'State']}_{new_clean.at[i, 'MeasureCode']}"
    c_smp = clean.at[i, "Sample"]
    new_clean.at[i, "Sample"] = c_smp.replace("patients", "pazienti") if c_smp != "empty" else "empty"

for i in range(len(clean)):
    for cc in geo_and_other + ["Sample", "Stateavg"]:
        dc = CLEAN_TO_DIRTY[cc]
        new_dirty.at[i, dc] = corrupt(clean.at[i, cc], dirty.at[i, dc], new_clean.at[i, cc])

# ---------- verifiche ----------
out = new_clean.copy()
print("\nFD nel dataset P3 corretto:", {
    "City->State": functional(out, "City", "State"),
    "ZipCode->City": functional(out, "ZipCode", "City"),
    "City->CountyName": functional(out, "City", "CountyName"),
    "ProviderNumber->HospitalName": functional(out, "ProviderNumber", "HospitalName"),
    "ProviderNumber->City": functional(out, "ProviderNumber", "City"),
})

PREFIX_LC = {k.lower(): v for k, v in PREFIX.items()}
phone_bad = [i for i in range(len(out)) if not out.at[i, "PhoneNumber"].startswith(PREFIX_LC[out.at[i, "City"]])]
print("telefoni con prefisso diverso dal comune:", len(phone_bad))
assert not phone_bad
caps_set = set(zip(cap.denominazione_ita.str.lower(), cap.cap, cap.denominazione_provincia.str.lower(),
                   cap.codice_regione))
bad = []
for i in range(len(out)):
    st_orig = clean.at[i, "State"]
    reg = STATE_REGION[st_orig]
    key = (out.at[i, "City"], out.at[i, "ZipCode"], out.at[i, "CountyName"], reg)
    if key not in caps_set:
        bad.append(key)
print("righe con comune/CAP/provincia non coerenti:", len(bad))
assert not bad, bad[:5]

for col in ["State", "City", "ZipCode", "CountyName", "HospitalName", "Address1", "ProviderNumber"]:
    print(f"valori distinti {col}: originale={clean[col].nunique()} P3={out[col].nunique()}")

diffs = int(new_dirty.ne(new_clean.rename(columns=CLEAN_TO_DIRTY)).to_numpy().sum())
print("celle corrotte (tutte le colonne):", diffs)

# ---------- salvataggio ----------
new_clean.to_csv(OUT + "p3_clean.csv", index=False)
new_dirty.to_csv(OUT + "p3_dirty.csv", index=False)
mappa = pd.DataFrame([{"stato_originale": st, "citta_originale": c, "stato_p3": STATE_NEW[st],
                       "comune_p3": r.den, "provincia_p3": r.prov, "regione_codice": r.reg, "prefisso": PREFIX[r.den]}
                      for (st, c), r in city_map.items()])
mappa.to_csv(OUT + "p3_mappa_geografica.csv", index=False)
print("\nMappa città:")
print(mappa.to_string(index=False))
print("\nSalvati:", OUT + "p3_clean.csv", OUT + "p3_dirty.csv", OUT + "p3_mappa_geografica.csv")
