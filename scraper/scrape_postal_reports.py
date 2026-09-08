"""
Scraper Section D -- volet Marche Postal -- arcep.bj/observatoire-postal/

Categorie basse priorite (hors positionnement telecom/data) et rapport le plus complexe
de tous (9 pages, nombreuses sous-tables SPU/SPNR par segment/operateur). Extraction
volontairement minimale : seulement le tableau des RECETTES DES SERVICES POSTAUX
(le plus propre, le plus parlant -- revenu total du secteur postal par trimestre).
Le detail par operateur (La Poste SA, DHL, Top Chrono, Baobab Express...) n'est pas
extrait dans cette premiere passe.
"""
import json
import os
import re
import time
import requests
import pdfplumber
from urllib.parse import unquote

INDEX_URL = "https://arcep.bj/observatoire-postal/"
PDF_LINK_RE = re.compile(r'href=\s*"(https://arcep\.bj/wp-content/uploads/(\d{4})/\d{2}/[^"]+\.pdf)"')
QUARTER_RE = re.compile(r'^T\d[-_]\d{4}$')

OBS_DIR = r"D:\eraste\Products\Telecom Data Analysis\Benin\arcep\data\observatoire\postal"
OUT_JSON = r"D:\eraste\Products\Telecom Data Analysis\Benin\vitrine\data\postal_data.json"
MIN_YEAR = 2024

LABELS = {
    'Courriers ordinaires': 'courriers_ordinaires',
    'Courriers Express': 'courriers_express',
    'Colis Postaux': 'colis_postaux',
    'Service de logistique': 'logistique',
    'Autres recettes': 'autres',
    'TOTALES RECETTES': 'total',
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
    s = s.replace('\xa0', '').replace(' ', '')
    try:
        return int(s)
    except ValueError:
        try:
            return float(s.replace(',', '.'))
        except ValueError:
            return None


def clean_quarter(q):
    return q.replace('-', '_')


OPERATOR_PATTERNS = [
    (re.compile(r'POSTE', re.I), 'la_poste'),
    (re.compile(r'DHL', re.I), 'dhl'),
    (re.compile(r'TOP\s*CHRONO', re.I), 'top_chrono'),
    (re.compile(r'BAOBAB', re.I), 'baobab_express'),
    (re.compile(r'CARS\s*ATT', re.I), 'cars_att'),
    (re.compile(r'AFRICA\s*GLOBAL|\bAGL\b', re.I), 'africa_global_logistics'),
    (re.compile(r'^AUTRES$', re.I), 'autres'),
]
PERCENT_RE = re.compile(r'^-?\d+[.,]?\d*\s*%$')
HEAD_RE = re.compile(
    r'PART\s+DE\s+MARCHE\s*(?:EN\s+(VOLUME|VALEUR)\s+)?DES?\s+OPERATEURS?.{0,80}?'
    r'(COURRIER\w*(?:\s+EXPRESS)?|COLIS\w*)',
    re.I | re.S,
)


def normalize_operator(name):
    for pat, key in OPERATOR_PATTERNS:
        if pat.search(name):
            return key
    return None


def segment_key(raw):
    raw = raw.upper()
    if 'COURRIER' in raw:
        return 'courrier_express'
    if 'COLIS' in raw:
        return 'colis'
    return None


def extract_operator_shares(pdf_path, debug=False):
    """{(segment, measure): {quarter: {operateur: pct}}} -- part de marche par operateur."""
    out = {}
    with pdfplumber.open(pdf_path) as pdf:
        for pnum, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            if not text:
                continue
            norm_text = ' '.join(text.split())
            headings = []
            for m in HEAD_RE.finditer(norm_text):
                measure = (m.group(1) or 'valeur').lower()
                seg = segment_key(m.group(2))
                if seg:
                    headings.append((seg, measure))
            if not headings:
                continue
            tables = [
                t for t in page.extract_tables()
                if t and any(c and PERCENT_RE.match(c.strip()) for row in t for c in row if c)
            ]
            if debug:
                print(f"    page {pnum}: {len(headings)} en-tetes {headings} / {len(tables)} tableaux")
            if len(headings) != len(tables):
                if debug:
                    print(f"    ! decalage en-tetes/tableaux page {pnum}, page ignoree")
                continue
            for (seg, measure), table in zip(headings, tables):
                header_row = table[0]
                quarters = list(dict.fromkeys(
                    clean_quarter(re.sub(r'\s+', '', c.strip()))
                    for c in header_row if c and QUARTER_RE.match(re.sub(r'\s+', '', c.strip()))
                ))
                if not quarters:
                    continue
                for row in table[1:]:
                    value_cells = [c.strip() for c in row if c and (PERCENT_RE.match(c.strip()) or c.strip() == '-')]
                    if not value_cells:
                        continue
                    name_cells = [c.strip() for c in row if c and c.strip() not in value_cells]
                    op_key = normalize_operator(' '.join(name_cells))
                    if not op_key or len(value_cells) != len(quarters):
                        continue
                    for q, v in zip(quarters, value_cells):
                        pct = None if v == '-' else float(v.replace('%', '').replace(',', '.').strip())
                        out.setdefault((seg, measure), {}).setdefault(q, {})[op_key] = pct
    return out


def extract_recettes(pdf_path):
    out = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            if 'RECETTES DES SERVICES POSTAUX' not in text.upper():
                continue
            for table in page.extract_tables():
                if not table:
                    continue
                header = table[0]
                quarters = list(dict.fromkeys(
                    clean_quarter(c.strip()) for c in header if c and QUARTER_RE.match(c.strip())
                ))
                if not quarters:
                    continue
                for row in table[1:]:
                    cells = [c for c in row if c not in (None, '')]
                    if not cells:
                        continue
                    label = cells[0].strip()
                    if label not in LABELS:
                        continue
                    key = LABELS[label]
                    values = [parse_number(v) for v in cells[1:]]
                    for q, v in zip(quarters, values):
                        out.setdefault(q, {})[key] = v
    return out


def main():
    print(f"Verification des rapports sur {INDEX_URL} ...")
    urls = discover_reports()
    print(f"{len(urls)} rapports (>= {MIN_YEAR}) detectes")

    if os.path.exists(OUT_JSON):
        with open(OUT_JSON, encoding='utf-8') as f:
            store = json.load(f)
    else:
        store = {'recettes': {}, 'parts_marche': {}, 'meta': {}}
    store.setdefault('parts_marche', {})

    for url in reversed(urls):
        path, is_new = ensure_downloaded(url)
        print(f"  {'telecharge' if is_new else 'deja present'} : {os.path.basename(path)}")
        recettes = extract_recettes(path)
        if not recettes:
            print(f"    ! rien extrait (recettes) -- structure differente, ignore")
        else:
            for q, vals in recettes.items():
                store['recettes'][q] = vals

        parts = extract_operator_shares(path)
        if not parts:
            print(f"    ! rien extrait (parts de marche operateurs)")
        else:
            for (seg, measure), quarters in parts.items():
                seg_store = store['parts_marche'].setdefault(seg, {}).setdefault(measure, {})
                for q, ops in quarters.items():
                    seg_store[q] = ops
        time.sleep(1)

    store['meta']['derniere_verification'] = time.strftime('%Y-%m-%d')
    store['meta']['verifie'] = False
    store['meta']['note'] = (
        "Recettes : extraction minimale (total uniquement) -- categorie basse priorite. "
        "Parts de marche par operateur (courrier express / colis, volume / valeur) ajoutees "
        "le 2026-09-08. Les rapports anterieurs a mi-2024 ne listent pas encore Cars ATT SARL "
        "ni Africa Global Logistics comme operateurs distincts -- les sommes par trimestre pour "
        "T1-T2 2023 peuvent donc etre inferieures a 100%."
    )

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"\nEcrit : {OUT_JSON}")


if __name__ == '__main__':
    main()
