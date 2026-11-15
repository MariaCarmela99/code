"""P3 variante italiana (P3IT): trapianto di dominio USA -> Italia con struttura relazionale preservata.

Costruzione:
  - stato -> macroarea ISTAT: al -> Italia settentrionale (Nord-ovest + Nord-est), ak -> Italia centrale;
  - ogni contea -> una provincia DIVERSA della macroarea (la mappa delle contee è biiettiva);
  - ogni città -> un comune della provincia assegnata alla sua contea, con almeno tanti CAP
    quanti ne ha la città originale;
  - CAP dal comune, nome dell'ospedale dal comune, telefono con il prefisso del capoluogo di provincia;
  - proprietari, condizioni e misure cliniche abbinati per significato.
Rumore: N_prop senza sovrapposizioni (stesse regole di p3fr_gen.py, vedi la funzione nprop).

Usa solo la libreria standard di Python. Lanciare dalla cartella code/:
    python baseline/p3it_gen.py
Input:  db/clean.csv, db/dirty.csv, baseline/comuni_cap_map.csv (ISTAT, comuni con CAP)
Output: db/p3it_clean.csv, db/p3it_dirty.csv, baseline/p3it_geo_map.csv
Tutti i valori sono ASCII minuscoli (accenti traslitterati, apostrofi sostituiti da spazi),
come nel dataset originale."""
import csv
import unicodedata

HERE = "./baseline/"  # path relativi alla directory code (lanciare gli script da code/)
D = "./db/"           # i CSV stanno in code/db/
OUT = D

CLEAN_TO_DIRTY = {
    "index": "index", "ProviderNumber": "provider_number", "HospitalName": "name",
    "Address1": "address_1", "Address2": "address_2", "Address3": "address_3",
    "City": "city", "State": "state", "ZipCode": "zip", "CountyName": "county",
    "PhoneNumber": "phone", "HospitalType": "type", "HospitalOwner": "owner",
    "EmergencyService": "emergency_service", "Condition": "condition",
    "MeasureCode": "measure_code", "MeasureName": "measure_name",
    "Score": "score", "Sample": "sample", "Stateavg": "state_average",
}
FD_COLS = ["ProviderNumber", "HospitalName", "Address1", "City", "State", "ZipCode", "CountyName",
           "PhoneNumber", "HospitalType", "HospitalOwner", "EmergencyService", "Condition",
           "MeasureCode", "MeasureName"]

# Stato originale -> macroarea ISTAT (colonna ripartizione_geografica) e valore nel dataset P3IT.
# L'Alabama ha 31 contee: serve un'area con almeno 31 province (il Nord ne ha 47).
STATE_AREA = {"al": ("Nord-ovest", "Nord-est"), "ak": ("Centro",)}
STATE_NEW = {"al": "nord", "ak": "centro"}

# Provincia (sigla ISTAT) -> nome nel dataset e prefisso telefonico del capoluogo.
# Per le province con due capoluoghi (FC, MS, PU) il secondo capoluogo ha il proprio prefisso (PREFIX_COMUNE).
PROVINCE = {
    "AL": ("alessandria", "0131"), "AN": ("ancona", "071"), "AO": ("aosta", "0165"),
    "AP": ("ascoli piceno", "0736"), "AR": ("arezzo", "0575"), "AT": ("asti", "0141"),
    "BG": ("bergamo", "035"), "BI": ("biella", "015"), "BL": ("belluno", "0437"),
    "BO": ("bologna", "051"), "BS": ("brescia", "030"), "BZ": ("bolzano", "0471"),
    "CN": ("cuneo", "0171"), "CO": ("como", "031"), "CR": ("cremona", "0372"),
    "FC": ("forli cesena", "0543"), "FE": ("ferrara", "0532"), "FI": ("firenze", "055"),
    "FM": ("fermo", "0734"), "FR": ("frosinone", "0775"), "GE": ("genova", "010"),
    "GO": ("gorizia", "0481"), "GR": ("grosseto", "0564"), "IM": ("imperia", "0183"),
    "LC": ("lecco", "0341"), "LI": ("livorno", "0586"), "LO": ("lodi", "0371"),
    "LT": ("latina", "0773"), "LU": ("lucca", "0583"), "MB": ("monza e brianza", "039"),
    "MC": ("macerata", "0733"), "MI": ("milano", "02"), "MN": ("mantova", "0376"),
    "MO": ("modena", "059"), "MS": ("massa carrara", "0585"), "NO": ("novara", "0321"),
    "PC": ("piacenza", "0523"), "PD": ("padova", "049"), "PG": ("perugia", "075"),
    "PI": ("pisa", "050"), "PN": ("pordenone", "0434"), "PO": ("prato", "0574"),
    "PR": ("parma", "0521"), "PT": ("pistoia", "0573"), "PU": ("pesaro e urbino", "0721"),
    "PV": ("pavia", "0382"), "RA": ("ravenna", "0544"), "RE": ("reggio emilia", "0522"),
    "RI": ("rieti", "0746"), "RM": ("roma", "06"), "RN": ("rimini", "0541"),
    "RO": ("rovigo", "0425"), "SI": ("siena", "0577"), "SO": ("sondrio", "0342"),
    "SP": ("la spezia", "0187"), "SV": ("savona", "019"), "TN": ("trento", "0461"),
    "TO": ("torino", "011"), "TR": ("terni", "0744"), "TS": ("trieste", "040"),
    "TV": ("treviso", "0422"), "UD": ("udine", "0432"), "VA": ("varese", "0332"),
    "VB": ("verbano cusio ossola", "0323"), "VC": ("vercelli", "0161"), "VE": ("venezia", "041"),
    "VI": ("vicenza", "0444"), "VR": ("verona", "045"), "VT": ("viterbo", "0761"),
}

PREFIX_COMUNE = {"cesena": "0547", "urbino": "0722"}


def prefix_of(comune):
    """Prefisso telefonico usato per un comune: quello del suo capoluogo di provincia."""
    return PREFIX_COMUNE.get(comune["den"], PROVINCE[comune["sigla"]][1])


STREETS = ["garibaldi", "mazzini", "cavour", "dante alighieri", "verdi", "roma", "milano",
    "matteotti", "gramsci", "leopardi", "manzoni", "carducci", "pascoli", "petrarca",
    "boccaccio", "galilei", "fermi", "marconi", "volta", "torricelli", "vespucci", "colombo",
    "da vinci", "michelangelo", "raffaello", "donatello", "tiziano", "tintoretto", "tiepolo",
    "canova", "rossini", "bellini", "donizetti", "puccini", "vivaldi", "corelli", "toscanini",
    "de gasperi", "einaudi", "turati", "gobetti", "amendola", "calamandrei", "parri", "pertini"]

# Corrispondenze per significato (non per posizione)
OWNER_MAP = {
    "government - federal": "fondazione irccs di diritto pubblico",
    "government - hospital district or authority": "azienda socio sanitaria territoriale - asst",
    "government - local": "presidio ospedaliero a gestione diretta",
    "government - state": "azienda ulss regionale",
    "proprietary": "struttura sanitaria privata accreditata ssn",
    "voluntary non-profit - church": "ente ecclesiastico civilmente riconosciuto",
    "voluntary non-profit - other": "ospedale classificato no-profit",
    "voluntary non-profit - private": "istituto di ricovero e cura a carattere scientifico",
}
COND_MAP = {
    "children s asthma care": "cura dell asma pediatrico",
    "heart attack": "infarto miocardico acuto",
    "heart failure": "insufficienza cardiaca congestizia",
    "pneumonia": "polmonite acquisita in comunita",
    "surgical infection prevention": "prevenzione delle infezioni chirurgiche",
}
TYPE_MAP = {"acute care hospitals": "presidi ospedalieri per acuti"}
EMG_MAP = {"yes": "si", "no": "no"}

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
    ("pic-vte-1", "pazienti chirurgici per i quali il medico ha prescritto trattamenti per prevenire la formazione di coaguli dopo determinati interventi"),
    ("pic-vte-2", "pazienti chirurgici sottoposti a profilassi del tromboembolismo venoso entro 24 ore dall intervento"),
]
# Corrispondenza per significato clinico: codice originale -> codice italiano
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

# Simboli di rumore, nell'ordine in cui vengono provati (come in P1)
MARKERS = ["x", "q", "z", "j", "k", "w", "v"]


# ---------- funzioni di supporto ----------
def read_csv(path, sep=",", encoding="utf-8"):
    with open(path, newline="", encoding=encoding) as f:
        r = csv.DictReader(f, delimiter=sep)
        cols = r.fieldnames
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in r]
    return cols, rows


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def ascii_name(s):
    """Nome leggibile in ASCII minuscolo: accenti tolti, apostrofi e trattini sostituiti da spazi."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().replace("'", " ").replace("-", " ")
    return " ".join(s.split())


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def edit_script(a, b):
    """Sequenza ottima di operazioni da a a b (ricostruzione all'indietro di Wagner e Fischer).
    Restituisce coppie (op, i) con op in C (copia), S (sostituzione), D (cancellazione), I (inserimento);
    i è la posizione in a a cui l'operazione si riferisce (per I, la posizione davanti a cui si inserisce)."""
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
            ops.append(("C" if a[i - 1] == b[j - 1] else "S", i - 1))
            i, j = i - 1, j - 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            ops.append(("D", i - 1))
            i -= 1
        else:
            ops.append(("I", i))
            j -= 1
    return ops[::-1]


def nprop(orig_clean, orig_dirty, new_clean):
    """Operatore N_prop senza sovrapposizioni.
    Ogni operazione di edit che trasforma il pulito originale nello sporco originale viene proiettata
    in proporzione sulla nuova stringa pulita; se la posizione è già occupata da un'altra operazione,
    si usa la posizione libera più vicina. In ogni posizione si scrive un simbolo di rumore: il primo di
    MARKERS che è diverso da tutti i caratteri sostituiti e per cui la distanza di Levenshtein tra nuovo
    sporco e nuovo pulito è uguale a quella originale. Se nessun simbolo la preserva, lo script si ferma."""
    if orig_clean == orig_dirty:
        return new_clean
    target = lev(orig_clean, orig_dirty)
    ops = [(op, i) for op, i in edit_script(orig_clean, orig_dirty) if op != "C"]
    assert len(ops) == target
    n0, n1 = len(orig_clean), len(new_clean)
    assert target <= n1, ("valore troppo corto per preservare la distanza", orig_clean, new_clean)
    used, positions = set(), []
    for _, i in ops:
        i = min(i, n0 - 1)
        q = int(round(i * (n1 - 1) / max(1, n0 - 1)))
        for d in range(n1):
            free = [p for p in (q + d, q - d) if 0 <= p < n1 and p not in used]
            if free:
                q = free[0]
                break
        used.add(q)
        positions.append(q)
    for m in MARKERS:
        if any(new_clean[p] == m for p in positions):
            continue
        chars = list(new_clean)
        for p in positions:
            chars[p] = m
        cand = "".join(chars)
        if lev(cand, new_clean) == target:
            return cand
    raise AssertionError(("distanza di edit non preservabile", orig_clean, orig_dirty, new_clean))


def functional(rows, x, y):
    seen = {}
    for r in rows:
        if seen.setdefault(r[x], r[y]) != r[y]:
            return False
    return True


def distinct(rows, col):
    return len({r[col] for r in rows})


# ---------- caricamento ----------
clean_cols, clean = read_csv(D + "clean.csv")
dirty_cols, dirty_rows = read_csv(D + "dirty.csv")
by_idx = {r["index"]: r for r in dirty_rows}
dirty = [by_idx[r["index"]] for r in clean]
n = len(clean)

assert {r["State"] for r in clean} == set(STATE_AREA), {r["State"] for r in clean}
FD_ORIG = [("City", "State"), ("ZipCode", "City"), ("City", "CountyName"), ("CountyName", "State"),
           ("ProviderNumber", "City"), ("ProviderNumber", "HospitalName"), ("PhoneNumber", "City")]
checks = {f"{x}->{y}": functional(clean, x, y) for x, y in FD_ORIG}
print("FD nel dataset originale:", checks)
assert all(checks.values()), "dipendenze originali non funzionali: lo script si ferma"

# ---------- tabella comuni (ISTAT + CAP) ----------
_, cap = read_csv(HERE + "comuni_cap_map.csv", sep=";")
groups = {}
for r in cap:
    g = groups.setdefault(r["codice_istat"], {
        "code": r["codice_istat"], "den": ascii_name(r["denominazione_ita"]), "sigla": r["sigla_provincia"],
        "area": r["ripartizione_geografica"], "capoluogo": r["flag_capoluogo"] == "SI", "caps": set()})
    g["caps"].add(r["cap"])
comuni = [dict(g, caps=sorted(g["caps"])) for _, g in sorted(groups.items())]


# ---------- contea -> provincia, città -> comune ----------
def assign(state, pool):
    """Assegna a ogni contea dello stato una provincia diversa e a ogni sua città un comune di quella
    provincia (capoluogo per primo, poi i comuni con più CAP), con abbastanza CAP e nomi univoci."""
    rows = [r for r in clean if r["State"] == state]
    counties = sorted({r["CountyName"] for r in rows})
    cities_of = {c: sorted({r["City"] for r in rows if r["CountyName"] == c}) for c in counties}
    need = {ct: len({r["ZipCode"] for r in rows if r["City"] == ct}) for c in counties for ct in cities_of[c]}
    by_prov = {}
    for c in pool:
        by_prov.setdefault(c["sigla"], []).append(c)
    for sg in by_prov:
        by_prov[sg].sort(key=lambda c: (not c["capoluogo"], -len(c["caps"]), c["code"]))
    provs = sorted(by_prov)
    assert len(provs) >= len(counties), (state, len(provs), len(counties))
    order = sorted(counties, key=lambda c: (-max(need[x] for x in cities_of[c]), -len(cities_of[c]), c))
    stride = max(1, len(provs) // len(counties))
    for k, county in enumerate(order):
        start = (k * stride) % len(provs)
        placed = None
        for off in range(len(provs)):
            sg = provs[(start + off) % len(provs)]
            if sg in used_prov:
                continue
            pick, taken = {}, set()
            for ct in sorted(cities_of[county], key=lambda x: (-need[x], x)):
                cand = next((c for c in by_prov[sg] if c["code"] not in used_com and c["code"] not in taken
                             and c["den"] not in used_names and len(c["caps"]) >= need[ct]
                             and not (set(c["caps"]) & used_caps)), None)
                if cand is None:
                    break
                pick[ct] = cand
                taken.add(cand["code"])
            if len(pick) == len(cities_of[county]):
                placed = (sg, pick)
                break
        assert placed, (state, county)
        sg, pick = placed
        used_prov.add(sg)
        county_map[(state, county)] = sg
        for ct, c in pick.items():
            used_com.add(c["code"])
            used_names.add(c["den"])
            used_caps.update(c["caps"])
            city_map[(state, ct)] = c


county_map, city_map = {}, {}
used_prov, used_com, used_names, used_caps = set(), set(), set(), set()
for st, areas in STATE_AREA.items():
    assign(st, [c for c in comuni if c["area"] in areas and c["sigla"] in PROVINCE])
assert len(set(county_map.values())) == len(county_map), "province non distinte"

# ---------- CAP: ogni CAP originale -> CAP del comune ----------
zip_map = {}
for (st, ct), c in city_map.items():
    zips = sorted({r["ZipCode"] for r in clean if r["State"] == st and r["City"] == ct})
    assert len(zips) <= len(c["caps"]), (ct, len(zips), len(c["caps"]))
    for z, cp in zip(zips, c["caps"]):
        assert z not in zip_map
        zip_map[z] = cp
assert len(set(zip_map.values())) == len(zip_map), "CAP non univoci"

# ---------- ospedale: nome dal comune; indirizzo per valore ----------
prov_info = {}
for r in clean:
    prov_info.setdefault(r["ProviderNumber"], (r["State"], r["City"]))
by_comune = {}
for p, (s, ct) in prov_info.items():
    by_comune.setdefault(city_map[(s, ct)]["den"], []).append(p)
name_map = {}
for comune in sorted(by_comune):
    provs = sorted(by_comune[comune])
    for k, p in enumerate(provs, 1):
        name_map[p] = f"presidio ospedaliero {comune}" + ("" if len(provs) == 1 else f" {k}")
addr_map = {}
for i, a in enumerate(sorted({r["Address1"] for r in clean})):
    addr_map[a] = a if a == "empty" else f"via {STREETS[i % len(STREETS)]} {1 + i // len(STREETS)}"

# ---------- codici, telefoni, misure ----------
prov_map = {v: f"{30101 + i:05d}" for i, v in enumerate(sorted({r["ProviderNumber"] for r in clean}))}
phone_map, counter = {}, {}
for r in clean:
    if r["PhoneNumber"] in phone_map:
        continue
    p = prefix_of(city_map[(r["State"], r["City"])])
    counter[p] = counter.get(p, 0) + 1
    phone_map[r["PhoneNumber"]] = p + f"{counter[p]:0{10 - len(p)}d}"
assert all(len(v) == 10 for v in phone_map.values())
assert len(set(phone_map.values())) == len(phone_map), "telefoni non univoci"

for mp, col in [(OWNER_MAP, "HospitalOwner"), (COND_MAP, "Condition"), (TYPE_MAP, "HospitalType"),
                (EMG_MAP, "EmergencyService")]:
    assert set(mp) == {r[col] for r in clean}, ("valori originali non coperti", col)
    assert len(set(mp.values())) == len(mp), ("mappa non iniettiva", col)
IT_NAME = dict(MEASURES_ITALIANE)
assert set(MEASURE_MAP) == {r["MeasureCode"] for r in clean}, "codici originali non coperti"
assert set(MEASURE_MAP.values()) == set(IT_NAME), "codici italiani mancanti o non usati"
mcode_map, mname_map = {}, {}
for mc in sorted(MEASURE_MAP):
    orig_mname = next(r["MeasureName"] for r in clean if r["MeasureCode"] == mc)
    mcode_map[mc] = MEASURE_MAP[mc]
    mname_map[orig_mname] = IT_NAME[MEASURE_MAP[mc]]
assert len(set(mcode_map.values())) == len(mcode_map)

# ---------- costruzione ----------
new_clean = [dict(r) for r in clean]
new_dirty = [dict(r) for r in dirty]
for i in range(n):
    c, nc = clean[i], new_clean[i]
    com = city_map[(c["State"], c["City"])]
    nc["State"] = STATE_NEW[c["State"]]
    nc["City"] = com["den"]
    nc["CountyName"] = PROVINCE[county_map[(c["State"], c["CountyName"])]][0]
    nc["ZipCode"] = zip_map[c["ZipCode"]]
    nc["HospitalName"] = name_map[c["ProviderNumber"]]
    nc["Address1"] = addr_map[c["Address1"]]
    nc["ProviderNumber"] = prov_map[c["ProviderNumber"]]
    nc["PhoneNumber"] = phone_map[c["PhoneNumber"]]
    nc["HospitalType"] = TYPE_MAP[c["HospitalType"]]
    nc["HospitalOwner"] = OWNER_MAP[c["HospitalOwner"]]
    nc["EmergencyService"] = EMG_MAP[c["EmergencyService"]]
    nc["Condition"] = COND_MAP[c["Condition"]]
    nc["MeasureCode"] = mcode_map[c["MeasureCode"]]
    nc["MeasureName"] = mname_map[c["MeasureName"]]
    nc["Stateavg"] = f"{nc['State']}_{nc['MeasureCode']}"
    nc["Sample"] = c["Sample"].replace("patients", "pazienti") if c["Sample"] != "empty" else "empty"

TRANSFORMED = FD_COLS + ["Sample", "Stateavg"]
for i in range(n):
    for cc in TRANSFORMED:
        dc = CLEAN_TO_DIRTY[cc]
        new_dirty[i][dc] = nprop(clean[i][cc], dirty[i][dc], new_clean[i][cc])

# ---------- verifiche ----------
out = new_clean
fd_new = {f"{x}->{y}": functional(out, x, y) for x, y in FD_ORIG}
print("\nFD nel dataset P3IT:", fd_new)
assert all(fd_new.values()), "FD rotte nel dataset P3IT"
# tutte le dipendenze tra coppie di attributi valide nell'originale devono valere anche in P3IT
lost = [f"{a}->{b}" for a in FD_COLS for b in FD_COLS
        if a != b and functional(clean, a, b) and not functional(out, a, b)]
print("dipendenze tra coppie perse:", lost)
assert not lost
for col in FD_COLS + ["Sample", "Stateavg"]:
    pairs = {(clean[i][col], out[i][col]) for i in range(n)}
    assert len({a for a, _ in pairs}) == len({b for _, b in pairs}) == len(pairs), ("mappa non biiettiva", col)
assert all(v.isascii() for r in out for v in r.values()), "valori non ASCII nel clean"
bad_phone = [i for i in range(n) if not out[i]["PhoneNumber"].startswith(
    prefix_of(city_map[(clean[i]["State"], clean[i]["City"])]))]
print("telefoni con prefisso diverso dalla provincia:", len(bad_phone))
assert not bad_phone
table = {(ascii_name(r["denominazione_ita"]), r["cap"], r["sigla_provincia"], r["ripartizione_geografica"]) for r in cap}
bad = []
for i in range(n):
    com = city_map[(clean[i]["State"], clean[i]["City"])]
    if (out[i]["City"], out[i]["ZipCode"], com["sigla"], com["area"]) not in table:
        bad.append(i)
    if PROVINCE[com["sigla"]][0] != out[i]["CountyName"] or com["area"] not in STATE_AREA[clean[i]["State"]]:
        bad.append(i)
print("righe con comune/CAP/provincia/macroarea non coerenti:", len(bad))
assert not bad

inv = {v: k for k, v in CLEAN_TO_DIRTY.items()}
corrupted = exact = 0
for i in range(n):
    for dc in dirty_cols:
        cc = inv[dc]
        o = dirty[i][dc] != clean[i][cc]
        m = new_dirty[i][dc] != new_clean[i][cc]
        assert o == m, ("maschera degli errori diversa", i, dc)
        if o:
            corrupted += 1
            exact += int(lev(dirty[i][dc], clean[i][cc]) == lev(new_dirty[i][dc], new_clean[i][cc]))
assert exact == corrupted, ("distanza di edit", exact, corrupted)
for col in ["State", "City", "ZipCode", "CountyName", "HospitalName", "Address1", "ProviderNumber"]:
    print(f"valori distinti {col}: originale={distinct(clean, col)} P3IT={distinct(out, col)}")
print(f"[P3IT] celle corrotte {corrupted}; distanza di edit esatta {exact}/{corrupted}")

# ---------- salvataggio ----------
write_csv(OUT + "p3it_clean.csv", clean_cols, new_clean)
write_csv(OUT + "p3it_dirty.csv", dirty_cols, new_dirty)
mappa_cols = ["stato_originale", "contea_originale", "citta_originale", "stato_p3it", "provincia_p3it",
              "sigla_provincia", "comune_p3it", "codice_istat", "macroarea", "cap", "prefisso"]
mappa = []
for (st, ct), c in city_map.items():
    county = next(r["CountyName"] for r in clean if r["State"] == st and r["City"] == ct)
    mappa.append({"stato_originale": st, "contea_originale": county, "citta_originale": ct,
                  "stato_p3it": STATE_NEW[st], "provincia_p3it": PROVINCE[c["sigla"]][0], "sigla_provincia": c["sigla"],
                  "comune_p3it": c["den"], "codice_istat": c["code"], "macroarea": c["area"],
                  "cap": " ".join(c["caps"]), "prefisso": prefix_of(c)})
mappa.sort(key=lambda m: (m["stato_originale"], m["contea_originale"], m["citta_originale"]))
write_csv(HERE + "p3it_geo_map.csv", mappa_cols, mappa)
print("\nMappa città:")
for m in mappa:
    print("  " + " | ".join(m[k] for k in mappa_cols if k != "cap"))
print("\nSalvati:", OUT + "p3it_clean.csv", OUT + "p3it_dirty.csv", HERE + "p3it_geo_map.csv")
