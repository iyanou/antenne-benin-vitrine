"""
Scraper QoS national -- arcep.bj/performances-mtn-et-moov/

Recupere la derniere semaine publiee par l'ARCEP (page HTML, tables wpDataTable),
la compare a ce qu'on a deja dans vitrine/data/qos_national.json, et fusionne les
jours reellement nouveaux dans le bon document mensuel.

Rappel important (voir SCOPE.md section 3) : cette page n'affiche jamais que la
semaine courante -- pas d'historique recuperable apres coup. Ce script doit donc
tourner regulierement (voir SCOPE.md, tache planifiee a venir) pour ne rater
aucune semaine.
"""
import json
import os
import re
import time
import requests
import pandas as pd
from io import StringIO

URL = "https://arcep.bj/performances-mtn-et-moov/"
HERE = os.path.dirname(os.path.abspath(__file__))
QOS_JSON = os.path.normpath(os.path.join(HERE, "..", "data", "qos_national.json"))

# table_id -> (indicateur, label, unite, seuil_col_scale, conforme_si)
TABLES = {
    'table_2':  dict(indicateur='succes_voix',  label='Succes voix 2G',  unite='%'),
    'table_4':  dict(indicateur='blocage_voix', label='Blocage voix 2G', unite='%'),
    'table_6':  dict(indicateur='dl_3g',        label='Debit DL 3G',     unite='kbps'),
    'table_8':  dict(indicateur='ul_3g',        label='Debit UL 3G',     unite='kbps'),
    'table_10': dict(indicateur='dl_4g',        label='Debit DL 4G',     unite='Mbps'),
    'table_12': dict(indicateur='ul_4g',        label='Debit UL 4G',     unite='Mbps'),
}

CONFORME_SI = {
    'succes_voix': 'gte', 'blocage_voix': 'lte',
    'dl_3g': 'gte', 'ul_3g': 'gte', 'dl_4g': 'gte', 'ul_4g': 'gte',
}
SEUILS = {'succes_voix': 99, 'blocage_voix': 1, 'dl_3g': 450, 'ul_3g': 70, 'dl_4g': 5, 'ul_4g': 2}

MOIS_NUM = {1:1,2:2,3:3,4:4,5:5,6:6,7:7,8:8,9:9,10:10,11:11,12:12}


def parse_fr_number(x):
    s = str(x).strip().replace('\xa0', '').replace(' ', '')
    s = s.replace('.', '').replace(',', '.') if ',' in s else s
    try:
        return float(s)
    except ValueError:
        return None


def fetch_tables():
    resp = requests.get(URL, timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; AntenneBeninBot/1.0)'})
    resp.raise_for_status()
    html = resp.text

    out = {}
    for table_id, meta in TABLES.items():
        dfs = pd.read_html(StringIO(html), attrs={'id': table_id}, flavor='lxml')
        if not dfs:
            print(f'  ! table {table_id} introuvable')
            continue
        df = dfs[0]
        # Colonnes attendues : wdt_ID, SEMAINE, {3 operateurs}, SEUIL
        df = df.iloc[:, 1:5]  # SEMAINE + 3 operateurs (on ignore wdt_ID et SEUIL, deja connu)
        df.columns = ['date_str', 'mtn', 'moov', 'celtiis']
        rows = []
        for _, r in df.iterrows():
            date_str = str(r['date_str']).strip()
            try:
                d = pd.to_datetime(date_str, dayfirst=True)
            except Exception:
                continue
            rows.append({
                'date': d.strftime('%Y-%m-%d'),
                'mtn': parse_fr_number(r['mtn']),
                'moov': parse_fr_number(r['moov']),
                'celtiis': parse_fr_number(r['celtiis']),
            })
        out[meta['indicateur']] = dict(meta=meta, jours=rows)
        time.sleep(1)  # poli -- pas de martelage
    return out


def merge_into_store(scraped):
    with open(QOS_JSON, encoding='utf-8') as f:
        store = json.load(f)

    report = []
    for indicateur, payload in scraped.items():
        meta = payload['meta']
        new_by_month = {}
        for j in payload['jours']:
            annee, mois, _ = j['date'].split('-')
            key = f"{indicateur}_{annee}_{mois}"
            new_by_month.setdefault(key, []).append(j)

        for doc_id, jours_nouveaux in new_by_month.items():
            annee, mois = doc_id.split('_')[-2:]
            existing = store.get(doc_id)
            if existing is None:
                store[doc_id] = {
                    'indicateur': indicateur, 'label': meta['label'], 'unite': meta['unite'],
                    'seuil': SEUILS[indicateur], 'conforme_si': CONFORME_SI[indicateur],
                    'annee': int(annee), 'mois': int(mois), 'jours': jours_nouveaux,
                }
                report.append(f"  NOUVEAU document {doc_id} ({len(jours_nouveaux)} jours)")
                continue

            known_dates = {j['date'] for j in existing['jours']}
            added = [j for j in jours_nouveaux if j['date'] not in known_dates]
            if added:
                existing['jours'].extend(added)
                existing['jours'].sort(key=lambda j: j['date'])
                report.append(f"  {doc_id} : +{len(added)} jour(s) nouveau(x) -> {[j['date'] for j in added]}")
            else:
                report.append(f"  {doc_id} : rien de nouveau (semaine deja connue)")

    with open(QOS_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, separators=(',', ':'))

    return report


if __name__ == '__main__':
    print(f"Recuperation de {URL} ...")
    scraped = fetch_tables()
    total_jours = sum(len(p['jours']) for p in scraped.values())
    print(f"{len(scraped)} indicateurs recuperes, {total_jours} lignes au total (semaine courante ARCEP)\n")

    report = merge_into_store(scraped)
    print("Fusion dans qos_national.json :")
    for line in report:
        print(line)
