"""P3 variante francese (P3FR): trapianto di dominio USA -> Francia con struttura relazionale preservata.

Costruzione:
  - stato -> parte del territorio francese: al -> Francia metropolitana (96 départements),
    ak -> dipartimenti d'oltremare (Guadeloupe, Martinique, Guyane, La Reunion, Mayotte).
    Come l'Alaska rispetto agli altri stati, l'oltremare è separato dal resto del paese;
  - ogni contea -> un département DIVERSO (la mappa delle contee è biiettiva);
  - ogni città -> una commune del département assegnato alla sua contea, con almeno tanti codici
    postali quanti ne ha la città originale (prima le communes con più codici postali);
  - codice postale dalla commune, nome dell'ospedale dalla commune ("centre hospitalier ..."),
    telefono con il prefisso geografico del département (01-05 in metropoli, 4 cifre in oltremare);
  - proprietari, condizioni e misure cliniche abbinati per significato.
Rumore: N_prop senza sovrapposizioni (stessa funzione nprop di p3it_gen.py).

Usa solo la libreria standard di Python. Lanciare dalla cartella code/:
    python baseline/p3fr_gen.py
Input:  db/clean.csv, db/dirty.csv,
        baseline/laposte_cp_map.csv (Base officielle des codes postaux, La Poste, via data.gouv.fr)
Output: db/p3fr_clean.csv, db/p3fr_dirty.csv, baseline/p3fr_geo_map.csv
Tutti i valori sono ASCII minuscoli (accenti traslitterati), come nel dataset originale."""
import csv
import re

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

# Stato originale -> départements ammessi e valore nel dataset P3FR.
# L'Alabama ha 31 contee: serve un insieme con almeno 31 départements (la metropoli ne ha 96).
STATE_NEW = {"al": "metropole", "ak": "outremer"}

# Département -> nome nel dataset e prefisso telefonico geografico.
# Metropoli: zone di numerazione 01 Ile-de-France, 02 Nord-Ouest, 03 Nord-Est, 04 Sud-Est, 05 Sud-Ouest.
DEP_METRO = {
    "01": ("ain", "04"), "02": ("aisne", "03"), "03": ("allier", "04"),
    "04": ("alpes de haute provence", "04"), "05": ("hautes alpes", "04"), "06": ("alpes maritimes", "04"),
    "07": ("ardeche", "04"), "08": ("ardennes", "03"), "09": ("ariege", "05"), "10": ("aube", "03"),
    "11": ("aude", "04"), "12": ("aveyron", "05"), "13": ("bouches du rhone", "04"), "14": ("calvados", "02"),
    "15": ("cantal", "04"), "16": ("charente", "05"), "17": ("charente maritime", "05"), "18": ("cher", "02"),
    "19": ("correze", "05"), "21": ("cote d or", "03"), "22": ("cotes d armor", "02"), "23": ("creuse", "05"),
    "24": ("dordogne", "05"), "25": ("doubs", "03"), "26": ("drome", "04"), "27": ("eure", "02"),
    "28": ("eure et loir", "02"), "29": ("finistere", "02"), "2A": ("corse du sud", "04"),
    "2B": ("haute corse", "04"), "30": ("gard", "04"), "31": ("haute garonne", "05"), "32": ("gers", "05"),
    "33": ("gironde", "05"), "34": ("herault", "04"), "35": ("ille et vilaine", "02"), "36": ("indre", "02"),
    "37": ("indre et loire", "02"), "38": ("isere", "04"), "39": ("jura", "03"), "40": ("landes", "05"),
    "41": ("loir et cher", "02"), "42": ("loire", "04"), "43": ("haute loire", "04"),
    "44": ("loire atlantique", "02"), "45": ("loiret", "02"), "46": ("lot", "05"),
    "47": ("lot et garonne", "05"), "48": ("lozere", "04"), "49": ("maine et loire", "02"),
    "50": ("manche", "02"), "51": ("marne", "03"), "52": ("haute marne", "03"), "53": ("mayenne", "02"),
    "54": ("meurthe et moselle", "03"), "55": ("meuse", "03"), "56": ("morbihan", "02"),
    "57": ("moselle", "03"), "58": ("nievre", "03"), "59": ("nord", "03"), "60": ("oise", "03"),
    "61": ("orne", "02"), "62": ("pas de calais", "03"), "63": ("puy de dome", "04"),
    "64": ("pyrenees atlantiques", "05"), "65": ("hautes pyrenees", "05"), "66": ("pyrenees orientales", "04"),
    "67": ("bas rhin", "03"), "68": ("haut rhin", "03"), "69": ("rhone", "04"), "70": ("haute saone", "03"),
    "71": ("saone et loire", "03"), "72": ("sarthe", "02"), "73": ("savoie", "04"),
    "74": ("haute savoie", "04"), "75": ("paris", "01"), "76": ("seine maritime", "02"),
    "77": ("seine et marne", "01"), "78": ("yvelines", "01"), "79": ("deux sevres", "05"),
    "80": ("somme", "03"), "81": ("tarn", "05"), "82": ("tarn et garonne", "05"), "83": ("var", "04"),
    "84": ("vaucluse", "04"), "85": ("vendee", "02"), "86": ("vienne", "05"), "87": ("haute vienne", "05"),
    "88": ("vosges", "03"), "89": ("yonne", "03"), "90": ("territoire de belfort", "03"),
    "91": ("essonne", "01"), "92": ("hauts de seine", "01"), "93": ("seine saint denis", "01"),
    "94": ("val de marne", "01"), "95": ("val d oise", "01"),
}
# Oltremare: dipartimenti d'oltremare con prefisso a 4 cifre
DEP_OUTREMER = {
    "971": ("guadeloupe", "0590"), "972": ("martinique", "0596"), "973": ("guyane", "0594"),
    "974": ("la reunion", "0262"), "976": ("mayotte", "0269"),
}
STATE_DEPS = {"al": DEP_METRO, "ak": DEP_OUTREMER}
DEPARTEMENTS = {**DEP_METRO, **DEP_OUTREMER}

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


def commune_name(raw):
    """Nome La Poste (maiuscolo, abbreviato) -> forma leggibile minuscola: "ST JEAN" -> "saint jean".
    Per Paris, Lyon e Marseille il numero dell'arrondissement viene tolto ("PARIS 01" -> "paris")."""
    s = raw.lower()
    s = re.sub(r"\bste\b", "sainte", s)
    s = re.sub(r"\bst\b", "saint", s)
    s = re.sub(r" \d+$", "", s)
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

assert {r["State"] for r in clean} == set(STATE_DEPS), {r["State"] for r in clean}
FD_ORIG = [("City", "State"), ("ZipCode", "City"), ("City", "CountyName"), ("CountyName", "State"),
           ("ProviderNumber", "City"), ("ProviderNumber", "HospitalName"), ("PhoneNumber", "City")]
checks = {f"{x}->{y}": functional(clean, x, y) for x, y in FD_ORIG}
print("FD nel dataset originale:", checks)
assert all(checks.values()), "dipendenze originali non funzionali: lo script si ferma"

# ---------- tabella communes (La Poste) ----------
with open(HERE + "laposte_cp_map.csv", newline="", encoding="latin-1") as f:
    raw = list(csv.reader(f, delimiter=";"))[1:]
groups = {}
for insee, nom, cp, _, _ in (r[:5] for r in raw):
    insee, nom, cp = insee.strip(), nom.strip(), cp.strip()
    dep = insee[:3] if insee.startswith("97") else insee[:2]
    if dep not in DEPARTEMENTS:
        continue
    g = groups.setdefault(insee, {"code": insee, "den": commune_name(nom), "dep": dep, "caps": set()})
    g["caps"].add(cp)
communes = [dict(g, caps=sorted(g["caps"])) for _, g in sorted(groups.items())]


# ---------- contea -> département, città -> commune ----------
def assign(state, pool):
    """Assegna a ogni contea dello stato un département diverso e a ogni sua città una commune di quel
    département (prima quelle con più codici postali), con abbastanza codici e nomi univoci."""
    rows = [r for r in clean if r["State"] == state]
    counties = sorted({r["CountyName"] for r in rows})
    cities_of = {c: sorted({r["City"] for r in rows if r["CountyName"] == c}) for c in counties}
    need = {ct: len({r["ZipCode"] for r in rows if r["City"] == ct}) for c in counties for ct in cities_of[c]}
    by_dep = {}
    for c in pool:
        by_dep.setdefault(c["dep"], []).append(c)
    for dp in by_dep:
        by_dep[dp].sort(key=lambda c: (-len(c["caps"]), c["code"]))
    deps = sorted(by_dep)
    assert len(deps) >= len(counties), (state, len(deps), len(counties))
    order = sorted(counties, key=lambda c: (-max(need[x] for x in cities_of[c]), -len(cities_of[c]), c))
    stride = max(1, len(deps) // len(counties))
    for k, county in enumerate(order):
        start = (k * stride) % len(deps)
        placed = None
        for off in range(len(deps)):
            dp = deps[(start + off) % len(deps)]
            if dp in used_dep:
                continue
            pick, taken = {}, set()
            for ct in sorted(cities_of[county], key=lambda x: (-need[x], x)):
                cand = next((c for c in by_dep[dp] if c["code"] not in used_com and c["code"] not in taken
                             and c["den"] not in used_names and len(c["caps"]) >= need[ct]
                             and not (set(c["caps"]) & used_caps)), None)
                if cand is None:
                    break
                pick[ct] = cand
                taken.add(cand["code"])
            if len(pick) == len(cities_of[county]):
                placed = (dp, pick)
                break
        assert placed, (state, county)
        dp, pick = placed
        used_dep.add(dp)
        county_map[(state, county)] = dp
        for ct, c in pick.items():
            used_com.add(c["code"])
            used_names.add(c["den"])
            used_caps.update(c["caps"])
            city_map[(state, ct)] = c


county_map, city_map = {}, {}
used_dep, used_com, used_names, used_caps = set(), set(), set(), set()
for st, deps in STATE_DEPS.items():
    assign(st, [c for c in communes if c["dep"] in deps])
assert len(set(county_map.values())) == len(county_map), "départements non distinti"

# ---------- codici postali: ogni CAP originale -> codice della commune ----------
zip_map = {}
for (st, ct), c in city_map.items():
    zips = sorted({r["ZipCode"] for r in clean if r["State"] == st and r["City"] == ct})
    assert len(zips) <= len(c["caps"]), (ct, len(zips), len(c["caps"]))
    for z, cp in zip(zips, c["caps"]):
        assert z not in zip_map
        zip_map[z] = cp
assert len(set(zip_map.values())) == len(zip_map), "codici postali non univoci"

# ---------- ospedale: nome dalla commune; indirizzo per valore ----------
prov_info = {}
for r in clean:
    prov_info.setdefault(r["ProviderNumber"], (r["State"], r["City"]))
by_commune = {}
for p, (s, ct) in prov_info.items():
    by_commune.setdefault(city_map[(s, ct)]["den"], []).append(p)
name_map = {}
for commune in sorted(by_commune):
    provs = sorted(by_commune[commune])
    for k, p in enumerate(provs, 1):
        name_map[p] = f"centre hospitalier {commune}" + ("" if len(provs) == 1 else f" {k}")
addr_map = {}
for i, a in enumerate(sorted({r["Address1"] for r in clean})):
    addr_map[a] = a if a == "empty" else f"rue {STREETS[i % len(STREETS)]} {1 + i // len(STREETS)}"

# ---------- codici, telefoni, misure ----------
prov_map = {v: f"{31001 + i:05d}" for i, v in enumerate(sorted({r["ProviderNumber"] for r in clean}))}
phone_map, counter = {}, {}
for r in clean:
    if r["PhoneNumber"] in phone_map:
        continue
    p = DEPARTEMENTS[city_map[(r["State"], r["City"])]["dep"]][1]
    counter[p] = counter.get(p, 0) + 1
    phone_map[r["PhoneNumber"]] = p + f"{counter[p]:0{10 - len(p)}d}"
assert all(len(v) == 10 for v in phone_map.values())
assert len(set(phone_map.values())) == len(phone_map), "telefoni non univoci"

for mp, col in [(OWNER_MAP, "HospitalOwner"), (COND_MAP, "Condition"), (TYPE_MAP, "HospitalType"),
                (EMG_MAP, "EmergencyService")]:
    assert set(mp) == {r[col] for r in clean}, ("valori originali non coperti", col)
    assert len(set(mp.values())) == len(mp), ("mappa non iniettiva", col)


def translate_code(mc):
    pre, rest = mc.split("-", 1)
    return f"{CODE_PREFIX[pre]}-{rest}"


mcode_map, mname_map = {}, {}
for mc in sorted({r["MeasureCode"] for r in clean}):
    orig_mname = next(r["MeasureName"] for r in clean if r["MeasureCode"] == mc)
    mcode_map[mc] = translate_code(mc)
    mname_map[orig_mname] = MEASURES_FR[mcode_map[mc]]
assert set(mcode_map.values()) == set(MEASURES_FR), "codici francesi mancanti o non usati"
assert len(set(mcode_map.values())) == len(mcode_map), "codici francesi non univoci"
assert len(set(mname_map.values())) == len(mname_map), "nomi delle misure non univoci"

# ---------- costruzione ----------
new_clean = [dict(r) for r in clean]
new_dirty = [dict(r) for r in dirty]
for i in range(n):
    c, nc = clean[i], new_clean[i]
    com = city_map[(c["State"], c["City"])]
    nc["State"] = STATE_NEW[c["State"]]
    nc["City"] = com["den"]
    nc["CountyName"] = DEPARTEMENTS[county_map[(c["State"], c["CountyName"])]][0]
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
    # Sample: "N patients" resta uguale (in francese si scrive allo stesso modo)

TRANSFORMED = FD_COLS + ["Stateavg"]
for i in range(n):
    for cc in TRANSFORMED:
        dc = CLEAN_TO_DIRTY[cc]
        new_dirty[i][dc] = nprop(clean[i][cc], dirty[i][dc], new_clean[i][cc])

# ---------- verifiche ----------
out = new_clean
fd_new = {f"{x}->{y}": functional(out, x, y) for x, y in FD_ORIG}
print("\nFD nel dataset P3FR:", fd_new)
assert all(fd_new.values()), "FD rotte nel dataset P3FR"
lost = [f"{a}->{b}" for a in FD_COLS for b in FD_COLS
        if a != b and functional(clean, a, b) and not functional(out, a, b)]
print("dipendenze tra coppie perse:", lost)
assert not lost
for col in FD_COLS + ["Stateavg"]:
    pairs = {(clean[i][col], out[i][col]) for i in range(n)}
    assert len({a for a, _ in pairs}) == len({b for _, b in pairs}) == len(pairs), ("mappa non biiettiva", col)
assert all(v.isascii() for r in out for v in r.values()), "valori non ASCII nel clean"
bad_phone = [i for i in range(n) if not out[i]["PhoneNumber"].startswith(
    DEPARTEMENTS[city_map[(clean[i]["State"], clean[i]["City"])]["dep"]][1])]
print("telefoni con prefisso diverso dal département:", len(bad_phone))
assert not bad_phone
table = set()
for insee, nom, cp, _, _ in (r[:5] for r in raw):
    insee = insee.strip()
    dep = insee[:3] if insee.startswith("97") else insee[:2]
    table.add((commune_name(nom.strip()), cp.strip(), dep))
bad = []
for i in range(n):
    com = city_map[(clean[i]["State"], clean[i]["City"])]
    if (out[i]["City"], out[i]["ZipCode"], com["dep"]) not in table:
        bad.append(i)
    if DEPARTEMENTS[com["dep"]][0] != out[i]["CountyName"] or com["dep"] not in STATE_DEPS[clean[i]["State"]]:
        bad.append(i)
print("righe con commune/codice postale/département non coerenti:", len(bad))
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
    print(f"valori distinti {col}: originale={distinct(clean, col)} P3FR={distinct(out, col)}")
print(f"[P3FR] celle corrotte {corrupted}; distanza di edit esatta {exact}/{corrupted}")

# ---------- salvataggio ----------
write_csv(OUT + "p3fr_clean.csv", clean_cols, new_clean)
write_csv(OUT + "p3fr_dirty.csv", dirty_cols, new_dirty)
mappa_cols = ["stato_originale", "contea_originale", "citta_originale", "stato_p3fr", "departement_p3fr",
              "code_departement", "commune_p3fr", "code_insee", "codes_postaux", "prefixe"]
mappa = []
for (st, ct), c in city_map.items():
    county = next(r["CountyName"] for r in clean if r["State"] == st and r["City"] == ct)
    mappa.append({"stato_originale": st, "contea_originale": county, "citta_originale": ct,
                  "stato_p3fr": STATE_NEW[st], "departement_p3fr": DEPARTEMENTS[c["dep"]][0],
                  "code_departement": c["dep"], "commune_p3fr": c["den"], "code_insee": c["code"],
                  "codes_postaux": " ".join(c["caps"]), "prefixe": DEPARTEMENTS[c["dep"]][1]})
mappa.sort(key=lambda m: (m["stato_originale"], m["contea_originale"], m["citta_originale"]))
write_csv(HERE + "p3fr_geo_map.csv", mappa_cols, mappa)
print("\nMappa città:")
for m in mappa:
    print("  " + " | ".join(m[k] for k in mappa_cols if k != "codes_postaux"))
print("\nSalvati:", OUT + "p3fr_clean.csv", OUT + "p3fr_dirty.csv", HERE + "p3fr_geo_map.csv")
