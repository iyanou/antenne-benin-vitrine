"""
Scraper Section D (Marche & Regulation) -- volet Gestion des plaintes
-- arcep.bj/observatoire-des-plaintes/

Noms de fichiers non uniformes (comme pour SFM) -- detection par ORDRE D'APPARITION sur
la page plutot que par regex de nom. Note : le HTML de cette page melange
`href="..."` et `href= "..."` (espace variable) -- la regex tolere les deux.

Extraction : Tableau 1 (plaintes recues par categorie : Commerciales/Techniques/Postales,
total, taux de croissance) et Tableau 3 (plaintes traitees : fondees/infondees/classees).
Meme structure DESIGNATION + trimestres que le rapport Telephonie Mobile.
"""
import json
import os
import re
import time
import requests
import pdfplumber
from urllib.parse import unquote

INDEX_URL = "https://arcep.bj/observatoire-des-plaintes/"
PDF_LINK_RE = re.compile(r'href=\s*"(https://arcep\.bj/wp-content/uploads/(\d{4})/\d{2}/[^"]+\.pdf)"')

OBS_DIR = r"D:\eraste\Products\Telecom Data Analysis\Benin\arcep\data\observatoire\plaintes"
OUT_JSON = r"D:\eraste\Products\Telecom Data Analysis\Benin\vitrine\data\complaints_data.json"

MIN_YEAR = 2024

RECUES_LABELS = {
    'Plaintes Commerciales': 'commerciales',
    'Plaintes Techniques': 'techniques',
    'Plaintes Services postaux': 'postales',
    'Total Plaintes traitées': 'total',
}
TRAITEES_LABELS = {
    'Plaintes fondées': 'fondees',
    'Plaintes infondées': 'infondees',
    'Plaintes classées': 'classees',
    'Total plaintes traitées': 'total',
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
    return ordered  # ordre de la page = plus recent en premier


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
    s = str(s).strip().replace('\xa0', '').replace(' ', '').replace('-', '') if str(s).strip() == '-' else str(s).strip()
    if s in ('-', ''):
        return None
    s = s.replace(' ', '')
    try:
        return int(s)
    except ValueError:
        try:
            return float(s.replace(',', '.'))
        except ValueError:
            return None


def clean_quarter(q):
    return q.replace('-', '_')


QUARTER_RE = re.compile(r'^T\d[-_]\d{4}$')


def extract_table(pdf_path, label_map):
    """Peu importe la position/le remplissage des cellules d'en-tete (None,
    chaines vides, colonne DESIGNATION ou pas) : on repere les trimestres par
    motif (T1-2025, T2_2025...) et les lignes de donnees par leur libelle connu."""
    out = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                header = table[0]
                quarters = [clean_quarter(c.strip()) for c in header if c and QUARTER_RE.match(c.strip())]
                if not quarters:
                    continue
                for row in table[1:]:
                    cells = [c for c in row if c not in (None, '')]
                    if not cells:
                        continue
                    label = cells[0].strip()
                    if label not in label_map:
                        continue
                    key = label_map[label]
                    values = cells[1:]
                    for q, v in zip(quarters, values):
                        out.setdefault(q, {})[key] = parse_number(v)
    return out


def main():
    print(f"Verification des rapports sur {INDEX_URL} ...")
    urls = discover_reports()
    print(f"{len(urls)} rapports (>= {MIN_YEAR}) detectes")

    if os.path.exists(OUT_JSON):
        with open(OUT_JSON, encoding='utf-8') as f:
            store = json.load(f)
    else:
        store = {'recues': {}, 'traitees': {}, 'meta': {}}

    for url in reversed(urls):  # plus ancien -> plus recent, le plus recent gagne
        path, is_new = ensure_downloaded(url)
        print(f"  {'telecharge' if is_new else 'deja present'} : {os.path.basename(path)}")
        recues = extract_table(path, RECUES_LABELS)
        traitees = extract_table(path, TRAITEES_LABELS)
        if not recues and not traitees:
            print(f"    ! rien extrait de ce fichier -- structure differente, ignore")
            continue
        for q, vals in recues.items():
            store['recues'][q] = vals
        for q, vals in traitees.items():
            # garde-fou : fondees + infondees + classees doit egaler le total, sinon
            # extraction suspecte (cellules fusionnees mal reconstruites) -- on rejette
            parts = [vals.get(k) for k in ('fondees', 'infondees', 'classees')]
            if vals.get('total') is not None and all(p is not None for p in parts):
                if sum(parts) != vals['total']:
                    print(f"    ! {q} : incoherent (fondees+infondees+classees != total) -- rejete")
                    continue
            store['traitees'][q] = vals
        time.sleep(1)

    store['meta']['derniere_verification'] = time.strftime('%Y-%m-%d')
    store['meta']['verifie'] = False

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"\nEcrit : {OUT_JSON}")


if __name__ == '__main__':
    main()
