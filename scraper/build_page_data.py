"""
Transforme le seed qos_national_seed.json (liste de {op, collection, doc_id, data})
en un objet plat {doc_id: data} pret a etre integre tel quel dans la page HTML
(pas de base live -- voir SCOPE.md section 5, correction du 2026-09-07).
"""
import json
import os

SEED = r"D:\eraste\Products\Telecom Data Analysis\Benin\vitrine\data\seed\qos_national_seed.json"
OUT  = r"D:\eraste\Products\Telecom Data Analysis\Benin\vitrine\data\qos_national.json"

with open(SEED, encoding='utf-8') as f:
    writes = json.load(f)

flat = {w['doc_id']: w['data'] for w in writes}

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(flat, f, ensure_ascii=False, separators=(',', ':'))

print(f'{len(flat)} documents -> {OUT}')
print(f'Taille : {os.path.getsize(OUT)} octets')
