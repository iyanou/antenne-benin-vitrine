"""
Construit le seed initial de la collection `qos_national` a partir des CSV deja traites
(mars, mai, juin, aout 2026). Sortie : un JSON pret a etre pousse en base via l'action
write_db (batch) de l'outil Artifact -- voir vitrine/DATA_SCHEMA.md pour le schema exact.
"""
import pandas as pd
import json
import os

BASE = r"D:\eraste\Products\Telecom Data Analysis\Benin\arcep\data\qos"
OUT  = r"D:\eraste\Products\Telecom Data Analysis\Benin\vitrine\data\seed"
os.makedirs(OUT, exist_ok=True)

MOIS_NUM = {
    'janvier': 1, 'fevrier': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
    'juillet': 7, 'aout': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'decembre': 12,
}

INDICATEURS = {
    'succes_voix':  dict(label='Succes voix 2G',  unite='%',    seuil=99,  conforme_si='gte',
                          cols=['TAUX_SUCCES_MTN_%', 'TAUX_SUCCES_MOOV_%', 'TAUX_SUCCES_CELTIIS_%']),
    'blocage_voix': dict(label='Blocage voix 2G',  unite='%',    seuil=1,   conforme_si='lte',
                          cols=['TAUX_BLOCAGE_MTN_%', 'TAUX_BLOCAGE_MOOV_%', 'TAUX_BLOCAGE_CELTIIS_%']),
    'dl_4g':        dict(label='Debit DL 4G',      unite='Mbps', seuil=5,   conforme_si='gte',
                          cols=['DEBIT_DL_4G_MTN_Mbps', 'DEBIT_DL_4G_MOOV_Mbps', 'DEBIT_DL_4G_CELTIIS_Mbps']),
    'dl_3g':        dict(label='Debit DL 3G',      unite='kbps', seuil=450, conforme_si='gte',
                          cols=['DEBIT_DL_3G_MTN_kbps', 'DEBIT_DL_3G_MOOV_kbps', 'DEBIT_DL_3G_CELTIIS_kbps']),
    'ul_4g':        dict(label='Debit UL 4G',      unite='Mbps', seuil=2,   conforme_si='gte',
                          cols=['DEBIT_UL_4G_MTN_Mbps', 'DEBIT_UL_4G_MOOV_Mbps', 'DEBIT_UL_4G_CELTIIS_Mbps']),
    'ul_3g':        dict(label='Debit UL 3G',      unite='kbps', seuil=70,  conforme_si='gte',
                          cols=['DEBIT_UL_3G_MTN_kbps', 'DEBIT_UL_3G_MOOV_kbps', 'DEBIT_UL_3G_CELTIIS_kbps']),
}

MOIS_DISPONIBLES = ['mars', 'mai', 'juin', 'aout']


def build():
    writes = []
    for mois in MOIS_DISPONIBLES:
        mois_num = MOIS_NUM[mois]
        for indicateur, spec in INDICATEURS.items():
            fname = os.path.join(BASE, mois, f'{indicateur}_{mois}_2026.csv')
            if not os.path.exists(fname):
                print(f'  (absent, ignore) {fname}')
                continue
            df = pd.read_csv(fname, parse_dates=['DATE'], dayfirst=True)
            jours = []
            for _, row in df.iterrows():
                jours.append({
                    'date':    row['DATE'].strftime('%Y-%m-%d'),
                    'mtn':     float(row[spec['cols'][0]]),
                    'moov':    float(row[spec['cols'][1]]),
                    'celtiis': float(row[spec['cols'][2]]),
                })
            doc_id = f'{indicateur}_2026_{mois_num:02d}'
            data = {
                'indicateur': indicateur,
                'label': spec['label'],
                'unite': spec['unite'],
                'seuil': spec['seuil'],
                'conforme_si': spec['conforme_si'],
                'annee': 2026,
                'mois': mois_num,
                'jours': jours,
            }
            writes.append({
                'op': 'set',
                'collection': 'qos_national',
                'doc_id': doc_id,
                'data': data,
            })
            print(f'  OK {doc_id}  ({len(jours)} jours)')

    out_path = os.path.join(OUT, 'qos_national_seed.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(writes, f, ensure_ascii=False, indent=2)
    print(f'\n{len(writes)} documents prets : {out_path}')


if __name__ == '__main__':
    build()
