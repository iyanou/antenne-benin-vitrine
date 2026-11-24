"""
Scraper Section D -- volet Gestion des plaintes -- arcep.bj/observatoire-des-plaintes/

Tableau 1 (plaintes recues par categorie) et Tableau 3 (plaintes traitees). Trimestres
deduits de la couverture (arcep_common.py), controles dans validate.py.

2026-11-24 : trois defauts corriges -- (1) libelles sur deux lignes depuis le T2 2026,
(2) tableau "par genre" qui ecrasait le tableau principal, (3) en-tetes ARCEP fautifs
(T1-2024 en double, colonne T3-2026 oubliee).
"""
import json
import os
import time

import arcep_common as ac

INDEX_URL = "https://arcep.bj/observatoire-des-plaintes/"
HERE = os.path.dirname(os.path.abspath(__file__))
OBS_DIR = os.path.normpath(os.path.join(HERE, "..", "cache", "plaintes"))
OUT_JSON = os.path.normpath(os.path.join(HERE, "..", "data", "complaints_data.json"))


def row_key(kind, label):
    if label.startswith('total'):
        return 'total'
    if kind == 'traitees':
        return ('infondees' if 'infondees' in label else 'fondees' if 'fondees' in label
                else 'classees' if 'classees' in label else None)
    return ('commerciales' if 'plaintes commerciales' in label
            else 'techniques' if 'plaintes techniques' in label
            else 'postales' if 'postaux' in label else None)


def extract(path, quarters):
    out = {'recues': {}, 'traitees': {}}
    for table in ac.iter_tables(path):
        cells_all = [ac.norm(c) for row in table for c in row if c]
        if 'f' in cells_all or 'genre' in cells_all:
            continue  # tableau 2 : repartition par genre
        if any('plaintes fondees' in c for c in cells_all):
            kind = 'traitees'
        elif any('commerciales' in c for c in cells_all):
            kind = 'recues'
        else:
            continue
        for row in table:
            label, cells = ac.split_row(row)
            values, key = ac.five_values(cells), row_key(kind, label)
            if values and key:
                for q, v in zip(quarters, values):
                    out[kind].setdefault(q, {})[key] = v
    return out['recues'], out['traitees']


def main():
    reports = ac.load_reports(INDEX_URL, OBS_DIR, min_upload_year=2024)
    old = ac.read_json(OUT_JSON)
    recues, traitees = {}, {}
    for period, path in reports:
        r, t = extract(path, ac.quarters_ending(period))
        print(f"  {period} {os.path.basename(path)} : {len(r)} trim. recues, {len(t)} trim. traitees")
        for store, new in ((recues, r), (traitees, t)):
            for q, vals in new.items():
                store.setdefault(q, {}).update(vals)
    store = {
        'recues': ac.keep_missing_quarters(recues, old.get('recues')),
        'traitees': ac.keep_missing_quarters(traitees, old.get('traitees')),
        'meta': {**old.get('meta', {}), 'dernier_rapport': reports[-1][0],
                 'derniere_verification': time.strftime('%Y-%m-%d')},
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"Ecrit : {OUT_JSON}")


if __name__ == '__main__':
    main()
