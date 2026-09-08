"""
Scraper Section D -- volet Internet (fixe + mobile) -- arcep.bj/internet/

Noms de fichiers non uniformes -- detection par ordre d'apparition sur la page.
Tableau 1 (Internet Fixe) a une liste d'operateurs DYNAMIQUE (beaucoup de petits FAI,
qui apparaissent/disparaissent d'un trimestre a l'autre) -- pas de mapping fixe, on
capture tout ce qui n'est pas une ligne d'agregat connue (Parc/Penetration).
Tableau 2 (Internet Mobile) reutilise les memes 3 gros operateurs que les autres rapports.
"""
import json
import os
import re
import time
import requests
import pdfplumber
from urllib.parse import unquote

INDEX_URL = "https://arcep.bj/internet/"
PDF_LINK_RE = re.compile(r'href=\s*"(https://arcep\.bj/wp-content/uploads/(\d{4})/\d{2}/[^"]+\.pdf)"')
QUARTER_RE = re.compile(r'^T\d[-_]\d{4}$')

OBS_DIR = r"D:\eraste\Products\Telecom Data Analysis\Benin\arcep\data\observatoire\internet"
OUT_JSON = r"D:\eraste\Products\Telecom Data Analysis\Benin\vitrine\data\internet_data.json"
MIN_YEAR = 2024

MOBILE_OP_MAP = {
    'SPACETEL BENIN': 'mtn',
    'MOOV AFRICA BENIN': 'moov',
    'CELTIIS': 'celtiis',
}
MOBILE_TOTAL_LABEL = 'Total Abonnement Internet mobile'

# Un meme FAI change parfois de raison sociale d'un rapport a l'autre (ex. "JENY" ->
# "JENY SAS" a partir de T1_2025) -- sans ca, le meme operateur apparait comme disparu
# puis un nouvel entrant apparait a sa place.
ISP_RENAMES = {
    'JENY SAS': 'JENY',
}


def discover_reports():
    r = requests.get(INDEX_URL, timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; AntenneBeninBot/1.0)'})
    r.raise_for_status()
    seen, ordered = set(), []
    for url, year in PDF_LINK_RE.findall(r.text):
        if url in seen or 'COMMUNIQUE' in url.upper():
            continue
        seen.add(url)
        if int(year) >= MIN_YEAR:
            ordered.append(url)
    return ordered


def ensure_downloaded(url):
    fname = unquote(url.rsplit('/', 1)[-1])
    os.makedirs(OBS_DIR, exist_ok=True)
    path = os.path.join(OBS_DIR, fname)
    if os.path.exists(path):
        return path, False
    r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; AntenneBeninBot/1.0)'})
    r.raise_for_status()
    with open(path, 'wb') as f:
        f.write(r.content)
    return path, True


def parse_number(s):
    s = str(s).strip()
    if s in ('-', '', None):
        return None
    s = s.replace('\xa0', '').replace(' ', '').replace('\n', '').replace('%', '')
    try:
        return int(s)
    except ValueError:
        try:
            return float(s.replace(',', '.'))
        except ValueError:
            return None


def clean_quarter(q):
    return q.replace('-', '_')


def header_positions(header):
    """[(trimestre, index)] pour chaque trimestre de l'en-tete, dans l'ordre. Certains
    rapports affichent le meme trimestre sur 2 colonnes consecutives (cellule fusionnee
    mal eclatee par pdfplumber, ex. 'T4_2024' repete a deux index de suite) -- on ne
    garde que la premiere occurrence pour eviter un decalage entre le nombre de
    trimestres uniques et le nombre de positions repere."""
    out = []
    for i, c in enumerate(header):
        if not c or not QUARTER_RE.match(c.strip()):
            continue
        q = clean_quarter(c.strip())
        if out and out[-1][0] == q:
            continue
        out.append((q, i))
    return out


def values_by_position(row, positions):
    """Associe a chaque trimestre la premiere cellule non-vide dans sa 'colonne' --
    definie comme [index d'en-tete du trimestre, index d'en-tete du trimestre suivant[.
    Les rapports ARCEP ne placent pas tous la valeur au meme index relatif a son en-tete
    (parfois le meme index, parfois un index avant) -- on elargit donc la fenetre d'un
    cran a gauche pour couvrir les deux cas."""
    values = []
    for i, pos in enumerate(positions):
        lo = pos - 1 if i > 0 else pos
        hi = positions[i + 1] - 2 if i + 1 < len(positions) else len(row) - 1
        cell = next((row[j] for j in range(max(lo, 0), min(hi, len(row) - 1) + 1) if row[j] not in (None, '')), None)
        values.append(cell)
    return values


def values_for_quarters(row, positions, label_index):
    """Valeurs d'une ligne de tableau alignees sur les trimestres de l'en-tete.
    Cas normal (ligne entierement renseignee) : l'ordre gauche-a-droite des cellules
    non vides (etiquette exclue) suffit et evite les soucis d'index de colonne qui
    varient d'un rapport a l'autre. Cas eparse (operateur recemment ajoute, cellules
    reellement vides sur les trimestres ou il n'existait pas encore) : le nombre de
    valeurs trouvees est inferieur au nombre de trimestres -- on bascule alors sur un
    alignement par position d'en-tete pour savoir a quels trimestres precis elles
    appartiennent."""
    compact = [c for i, c in enumerate(row) if i != label_index and c not in (None, '')]
    if len(compact) == len(positions):
        return compact
    return values_by_position(row, positions)


def extract_fixe(pdf_path):
    out = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                header = table[0]
                if not header or header[0] != 'OPERATEURS':
                    continue
                hp = header_positions(header)
                if not hp:
                    continue
                quarters, positions = [q for q, _ in hp], [i for _, i in hp]
                for row in table[1:]:
                    found = next(((i, c) for i, c in enumerate(row[:positions[0]]) if c not in (None, '')), None)
                    if not found:
                        continue
                    label_index, label_cell = found
                    label = label_cell.strip()
                    values = [parse_number(v) for v in values_for_quarters(row, positions, label_index)]
                    if 'Parc Internet fixe' in label:
                        key = 'total'
                    elif 'Pénétration' in label:
                        key = 'penetration_pct'
                    else:
                        key = None  # ISP -> son propre nom
                    for q, v in zip(quarters, values):
                        if key:
                            out.setdefault(q, {})[key] = v
                        else:
                            # normalisation minimale : la casse varie d'un rapport a l'autre
                            # pour le meme FAI (ex. "FirstNet" / "FIRSTNET") -- on uniformise
                            # en majuscules pour eviter de dupliquer le meme operateur sous
                            # deux cles differentes dans le temps.
                            isp_name = ISP_RENAMES.get(label.upper(), label.upper())
                            out.setdefault(q, {}).setdefault('isp', {})[isp_name] = v
    return out


def extract_mobile(pdf_path):
    out = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                header = table[0]
                hp = header_positions(header)
                if not hp:
                    continue
                quarters, positions = [q for q, _ in hp], [i for _, i in hp]
                for row in table[1:]:
                    found = next(((i, c) for i, c in enumerate(row[:positions[0]]) if c not in (None, '')), None)
                    if not found:
                        continue
                    label_index, label_cell = found
                    label = re.sub(r'\s+', ' ', label_cell).strip()
                    values = [parse_number(v) for v in values_for_quarters(row, positions, label_index)]
                    if label in MOBILE_OP_MAP:
                        op = MOBILE_OP_MAP[label]
                        for q, v in zip(quarters, values):
                            out.setdefault(q, {}).setdefault('operateurs', {})[op] = v
                    elif label.startswith(MOBILE_TOTAL_LABEL):
                        for q, v in zip(quarters, values):
                            out.setdefault(q, {})['total'] = v
    return out


def main():
    print(f"Verification des rapports sur {INDEX_URL} ...")
    urls = discover_reports()
    print(f"{len(urls)} rapports (>= {MIN_YEAR}) detectes")

    if os.path.exists(OUT_JSON):
        with open(OUT_JSON, encoding='utf-8') as f:
            store = json.load(f)
    else:
        store = {'fixe': {}, 'mobile': {}, 'meta': {}}

    for url in reversed(urls):
        path, is_new = ensure_downloaded(url)
        print(f"  {'telecharge' if is_new else 'deja present'} : {os.path.basename(path)}")
        fixe = extract_fixe(path)
        mobile = extract_mobile(path)
        if not fixe and not mobile:
            print(f"    ! rien extrait -- structure differente, ignore")
            continue
        for q, vals in fixe.items():
            store['fixe'][q] = vals
        for q, vals in mobile.items():
            store['mobile'][q] = vals
        time.sleep(1)

    store['meta']['derniere_verification'] = time.strftime('%Y-%m-%d')
    store['meta']['verifie'] = False

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"\nEcrit : {OUT_JSON}")

    # Garde-fou : deux trimestres consecutifs avec des valeurs operateurs identiques
    # sont suspects (probable mislabeling d'un rapport source) -- signale, pas corrige
    # automatiquement (a verifier manuellement lors de la passe qualite).
    def qkey(q):
        t, y = q.split('_')
        return int(y) * 10 + int(t[1:])
    mob_quarters = sorted(store['mobile'].keys(), key=qkey)
    for a, b in zip(mob_quarters, mob_quarters[1:]):
        oa, ob = store['mobile'][a].get('operateurs', {}), store['mobile'][b].get('operateurs', {})
        if oa and oa == ob:
            print(f"  ! SUSPECT : {a} et {b} ont des valeurs operateurs mobile identiques -- a verifier manuellement")


if __name__ == '__main__':
    main()
