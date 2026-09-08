"""
Scraper Section D (Marche & Regulation) -- arcep.bj/telephonie-mobile/

Detecte les nouveaux rapports "Observatoire Telephonie Mobile" publies par l'ARCEP,
telecharge les PDF pas encore presents localement, extrait les tableaux (abonnements
actifs par operateur, trafics reseau) via pdfplumber, calcule les parts de marche, et
ecrit le resultat dans vitrine/data/market_data.json.

IMPORTANT : contrairement au scraper QoS national, cette donnee vient de PDF -- moins
fiable a 100% automatiquement. Le champ "verifie": false doit etre repasse a true
manuellement (ou via revue rapide) avant que le chiffre ne soit considere fiable pour
affichage public. Voir SCOPE.md section 4 (D).
"""
import json
import os
import re
import time
import requests
import pdfplumber

INDEX_URL = "https://arcep.bj/telephonie-mobile/"
PDF_LINK_RE = re.compile(
    r'href="(https://arcep\.bj/wp-content/uploads/[^"]*Observatoire-T[ée]l[ée]phonie-Mobile-T(\d)_(\d{4})\.pdf)"'
)

HERE = os.path.dirname(os.path.abspath(__file__))
OBS_DIR = os.path.normpath(os.path.join(HERE, "..", "cache", "market"))
OUT_JSON = os.path.normpath(os.path.join(HERE, "..", "data", "market_data.json"))

OP_MAP = {
    'SPACETEL BENIN': 'mtn',
    'MOOV AFRICA BENIN': 'moov',
    'CELTIIS': 'celtiis',
}


def discover_reports():
    r = requests.get(INDEX_URL, timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; AntenneBeninBot/1.0)'})
    r.raise_for_status()
    seen = {}
    for url, quarter, year in PDF_LINK_RE.findall(r.text):
        key = f"T{quarter}_{year}"
        seen[key] = url  # dedoublonne (le lien apparait 2x sur la page)
    return seen


def ensure_downloaded(key, url):
    folder = os.path.join(OBS_DIR, key)
    os.makedirs(folder, exist_ok=True)
    fname = url.rsplit('/', 1)[-1]
    # decode les %xx eventuels dans le nom de fichier
    from urllib.parse import unquote
    fname = unquote(fname)
    path = os.path.join(folder, fname)
    if os.path.exists(path):
        return path, False
    r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; AntenneBeninBot/1.0)'})
    r.raise_for_status()
    with open(path, 'wb') as f:
        f.write(r.content)
    return path, True


def parse_number(s):
    s = str(s).strip().replace('\xa0', '').replace(' ', '')
    try:
        return int(s)
    except ValueError:
        try:
            return float(s.replace(',', '.'))
        except ValueError:
            return None


def extract_abonnements(pdf_path):
    """Extrait le Tableau 1 (abonnements actifs par operateur) du rapport."""
    abonnements = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                rows = [[c for c in row if c not in (None, '')] for row in table]
                rows = [r for r in rows if r]
                if not rows:
                    continue
                header = rows[0]
                if header and header[0] == 'DESIGNATIONS':
                    quarters = header[1:]
                    for row in rows[1:]:
                        label = row[0].strip()
                        values = row[1:]
                        if label in OP_MAP:
                            op = OP_MAP[label]
                            for q, v in zip(quarters, values):
                                abonnements.setdefault(q, {})[op] = parse_number(v)
                        elif 'Total' in label:
                            for q, v in zip(quarters, values):
                                abonnements.setdefault(q, {})['total'] = parse_number(v)
    return abonnements


TRAFIC_LABELS = {
    'Trafic Voix (min)': 'voix_min',
    'Trafic SMS (Nbre)': 'sms_nb',
    'Trafic Data (Go)': 'data_go',
}


def extract_trafics(pdf_path, quarters_order):
    """Le tableau des trafics a des cellules fusionnees mal reconstruites par
    pdfplumber (en-tete eclate sur 2 lignes) -- on reutilise l'ordre des trimestres
    deja fiabilise via le tableau des abonnements du meme PDF plutot que de re-parser
    un en-tete ambigu."""
    trafics = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cells = [c for c in row if c not in (None, '')]
                    if not cells:
                        continue
                    label = cells[0].strip()
                    if label in TRAFIC_LABELS:
                        key = TRAFIC_LABELS[label]
                        values = [parse_number(v) for v in cells[1:]]
                        if len(values) == len(quarters_order):
                            for q, v in zip(quarters_order, values):
                                trafics.setdefault(q, {})[key] = v
    return trafics


def compute_parts_marche(abonnements):
    for q, vals in abonnements.items():
        total = vals.get('total')
        if not total:
            continue
        vals['parts_marche'] = {
            op: round(vals[op] / total * 100, 1)
            for op in ('mtn', 'moov', 'celtiis') if vals.get(op) is not None
        }


def main():
    print(f"Verification des rapports sur {INDEX_URL} ...")
    reports = discover_reports()
    print(f"{len(reports)} rapports detectes : {sorted(reports.keys())}")

    if os.path.exists(OUT_JSON):
        with open(OUT_JSON, encoding='utf-8') as f:
            store = json.load(f)
    else:
        store = {'abonnements': {}, 'trafics': {}, 'meta': {}}

    for key, url in sorted(reports.items()):
        path, is_new = ensure_downloaded(key, url)
        print(f"  {key} : {'telecharge' if is_new else 'deja present'} ({os.path.basename(path)})")
        abonnements = extract_abonnements(path)
        trafics = extract_trafics(path, list(abonnements.keys()))
        compute_parts_marche(abonnements)
        for q, vals in abonnements.items():
            store['abonnements'][q] = vals
        for q, vals in trafics.items():
            store['trafics'][q] = vals
        time.sleep(1)

    store['meta']['derniere_verification'] = time.strftime('%Y-%m-%d')
    store['meta'].setdefault('verifie', False)  # a repasser a true apres revue humaine

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"\nEcrit : {OUT_JSON}")
    print("STATUT : verifie=false -- revue humaine recommandee avant affichage public.")


if __name__ == '__main__':
    main()
