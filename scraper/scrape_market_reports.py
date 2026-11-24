"""
Scraper Section D (Marche & Regulation) -- arcep.bj/telephonie-mobile/

Rapports "Telephonie mobile" : abonnements actifs par operateur (parts de marche
calculees) et trafics reseau. Les trimestres viennent de la couverture du rapport
(voir arcep_common.py) et les controles sont dans validate.py.

2026-11-24 : depuis le T2 2026 l'ARCEP ecrit "MOOV AFRICA" et "BENIN" sur deux lignes --
la comparaison exacte de libelle faisait disparaitre Moov en silence.
"""
import json
import os
import time

import arcep_common as ac

INDEX_URL = "https://arcep.bj/telephonie-mobile/"
HERE = os.path.dirname(os.path.abspath(__file__))
OBS_DIR = os.path.normpath(os.path.join(HERE, "..", "cache", "market"))
OUT_JSON = os.path.normpath(os.path.join(HERE, "..", "data", "market_data.json"))
FIRST_QUARTER = 'T3_2024'

OPERATORS = {'spacetel benin': 'mtn', 'moov africa benin': 'moov', 'celtiis': 'celtiis'}
TRAFIC = {'trafic voix': 'voix_min', 'trafic sms': 'sms_nb', 'trafic data': 'data_go'}


def extract(path, quarters):
    abo, trafics = {}, {}
    for table in ac.iter_tables(path):
        is_abo = any(ac.norm(c) == 'designations' for c in table[0] if c)
        for row in table:
            label, cells = ac.split_row(row)
            values = ac.five_values(cells)
            if values is None:
                continue
            if is_abo and label in OPERATORS:
                target, key = abo, OPERATORS[label]
            elif is_abo and label.startswith('total abonnements'):
                target, key = abo, 'total'
            else:
                key = next((k for p, k in TRAFIC.items() if label.startswith(p)), None)
                target = trafics
            if key:
                for q, v in zip(quarters, values):
                    target.setdefault(q, {})[key] = v
    return abo, trafics


def main():
    reports = ac.load_reports(INDEX_URL, OBS_DIR, min_upload_year=2025, exclude=('tarif', 'annuel'))
    old = ac.read_json(OUT_JSON)
    abonnements, trafics = {}, {}
    for period, path in reports:
        a, t = extract(path, ac.quarters_ending(period))
        print(f"  {period} {os.path.basename(path)} : {len(a)} trim. abonnements, {len(t)} trim. trafics")
        for store, new in ((abonnements, a), (trafics, t)):
            for q, vals in new.items():
                if ac.qkey(q) >= ac.qkey(FIRST_QUARTER):
                    store.setdefault(q, {}).update(vals)
    for vals in abonnements.values():
        total = vals.get('total')
        vals['parts_marche'] = {op: round(vals[op] / total * 100, 1)
                                for op in ('mtn', 'moov', 'celtiis') if total and vals.get(op) is not None}
    store = {
        'abonnements': ac.keep_missing_quarters(abonnements, old.get('abonnements')),
        'trafics': ac.keep_missing_quarters(trafics, old.get('trafics')),
        'meta': {**old.get('meta', {}), 'dernier_rapport': reports[-1][0],
                 'derniere_verification': time.strftime('%Y-%m-%d')},
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"Ecrit : {OUT_JSON}")


if __name__ == '__main__':
    main()
