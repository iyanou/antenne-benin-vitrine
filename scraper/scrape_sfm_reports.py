"""
Scraper Section D -- volet Services Financiers Mobiles (Mobile Money)
-- arcep.bj/services-financiers-mobiles/

Extrait : comptes actifs/dormants, parts de marche, taux de penetration et d'activite,
depots et retraits (volume + valeur en milliards de FCFA). Trimestres deduits de la
couverture (arcep_common.py), controles dans validate.py.

2026-11-24 : l'ancienne version gardait le contexte "Retraits" jusqu'a la fin du tableau
et finissait par stocker la valeur des transferts internationaux sortants (19,8 Mds au
lieu de 910,57). Chaque couple (type, mesure) n'est plus lu qu'une seule fois.
"""
import json
import os
import re
import time

import arcep_common as ac

INDEX_URL = "https://arcep.bj/services-financiers-mobiles/"
HERE = os.path.dirname(os.path.abspath(__file__))
OBS_DIR = os.path.normpath(os.path.join(HERE, "..", "cache", "sfm"))
OUT_JSON = os.path.normpath(os.path.join(HERE, "..", "data", "sfm_data.json"))

SHARE_OPS = ('mtn', 'moov', 'celtiis')
MEASURE_RE = re.compile(r'(volume|valeur)\s*\(.*$')


def compte_key(label):
    if 'comptes' in label:
        if 'actifs' in label:
            return 'comptes_actifs'
        # "dormants" passe parfois a la ligne suivante, seul
        return 'comptes_dormants' if 'dormants' in label or label.endswith('sfm') else None
    if label.startswith('taux de penetration'):
        return 'taux_penetration'
    if label.startswith("taux d'activite"):
        return 'taux_activite'
    if label.startswith(('part de marche', 'pdm')):
        return next((op for op in SHARE_OPS if op in label), None)
    return None


def extract(path, quarters):
    comptes, transactions, seen = {}, {}, set()
    for table in ac.iter_tables(path):
        current = None
        for row in table:
            label, cells = ac.split_row(row)
            m = MEASURE_RE.search(label)
            if m:
                name = label[:m.start()].strip()
                if 'depots' in name:
                    current = 'depots'
                elif 'retraits' in name:
                    current = 'retraits'
                elif name:
                    current = None
                metric = 'volume' if m.group(1) == 'volume' else 'valeur_mds_fcfa'
                values = ac.five_values(cells, variation=True)
                if current and values and (current, metric) not in seen:
                    seen.add((current, metric))
                    for q, v in zip(quarters, values):
                        transactions.setdefault(q, {}).setdefault(current, {})[metric] = v
                if metric == 'valeur_mds_fcfa':
                    current = None
                continue
            key = compte_key(label)
            values = ac.five_values(cells)
            if key and values and key not in seen:
                seen.add(key)
                for q, v in zip(quarters, values):
                    d = comptes.setdefault(q, {})
                    (d.setdefault('parts_marche', {}) if key in SHARE_OPS else d)[key] = v
    return comptes, transactions


def main():
    reports = ac.load_reports(INDEX_URL, OBS_DIR, min_upload_year=2024)
    old = ac.read_json(OUT_JSON)
    comptes, transactions = {}, {}
    for period, path in reports:
        c, t = extract(path, ac.quarters_ending(period))
        print(f"  {period} {os.path.basename(path)} : {len(c)} trim. comptes, {len(t)} trim. transactions")
        for q, vals in c.items():
            d = comptes.setdefault(q, {})
            d.setdefault('parts_marche', {}).update(vals.pop('parts_marche', {}))
            d.update(vals)
        for q, vals in t.items():
            for kind, mv in vals.items():
                transactions.setdefault(q, {}).setdefault(kind, {}).update(mv)
    store = {
        'comptes': ac.keep_missing_quarters(comptes, old.get('comptes')),
        'transactions': ac.keep_missing_quarters(transactions, old.get('transactions')),
        'meta': {**old.get('meta', {}), 'dernier_rapport': reports[-1][0],
                 'derniere_verification': time.strftime('%Y-%m-%d')},
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"Ecrit : {OUT_JSON}")


if __name__ == '__main__':
    main()
