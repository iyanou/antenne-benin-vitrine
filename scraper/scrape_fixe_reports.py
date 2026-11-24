"""
Scraper Section D -- volet Telephonie Fixe -- arcep.bj/telephonie-fixe/

Rapport le plus simple de tous : un seul petit tableau (Parc abonne + tele densite).
Segment marginal (quelques milliers de lignes), mais interessant analytiquement : un
saut brutal du parc observe entre T3_2025 (1214) et T4_2025 (78938) -- x65, a signaler
comme piste d'analyse plutot qu'a expliquer ici (reclassification methodologique
probable, non confirmee).
"""
import json
import os
import re
import time
import requests
import pdfplumber

import arcep_common as ac

INDEX_URL = "https://arcep.bj/telephonie-fixe/"
QUARTER_RE = re.compile(r'^T\d\s*[-_]\s*\d{4}$')

HERE = os.path.dirname(os.path.abspath(__file__))
OBS_DIR = os.path.normpath(os.path.join(HERE, "..", "cache", "fixe"))
OUT_JSON = os.path.normpath(os.path.join(HERE, "..", "data", "fixe_data.json"))
MIN_YEAR = 2024

LABELS = {
    'Parc abonné': 'parc_abonnes',
    'Télé densité (%)': 'tele_densite_pct',
}


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
    return re.sub(r'\s+', '', q).replace('-', '_')


def extract(pdf_path):
    out = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
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
    reports = ac.load_reports(INDEX_URL, OBS_DIR, min_upload_year=MIN_YEAR)
    print(f"{len(reports)} rapports (>= {MIN_YEAR}) detectes")

    if os.path.exists(OUT_JSON):
        with open(OUT_JSON, encoding='utf-8') as f:
            store = json.load(f)
    else:
        store = {'donnees': {}, 'meta': {}}

    for period, path in reports:  # plus ancien -> plus recent
        print(f"  {period} {os.path.basename(path)}")
        data = extract(path)
        if not data:
            print(f"    ! rien extrait -- structure differente, ignore")
            continue
        for q, vals in data.items():
            store['donnees'][q] = vals

    store['meta']['dernier_rapport'] = reports[-1][0]
    store['meta']['derniere_verification'] = time.strftime('%Y-%m-%d')
    store['meta'].setdefault('verifie', False)

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"\nEcrit : {OUT_JSON}")


if __name__ == '__main__':
    main()
