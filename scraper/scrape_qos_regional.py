"""
Scraper QoS regional -- atlas.arcep.bj/api/

Recupere les indicateurs QoS par departement (12) et par commune (77) depuis l'API
Atlas de l'ARCEP. Contrairement a la page nationale, ces donnees viennent de
campagnes d'audit terrain (pas d'un cycle hebdomadaire) -- chaque operateur porte
sa propre date de derniere mesure (qos_day). Voir SCOPE.md section 3bis.

Poliment : delai entre chaque appel, pas de martelage (documentation Swagger
etiquetee "pre-prod", pas de garantie de disponibilite a long terme).
"""
import json
import time
import requests

BASE = "https://atlas.arcep.bj/api"
OUT  = r"D:\eraste\Products\Telecom Data Analysis\Benin\vitrine\data\qos_regional.json"
DELAY = 1.2  # secondes entre chaque appel

FIELDS = ['2g_voice', '2g_sms', '3g_voice', '3g_sms', '3g_internet', '4g_internet', 'qos_day']

# Couverture : structure {"geo": {"<seuil_dBm>": pct, ...}, "pop": {...}}, plusieurs seuils
# de signal par technologie. La couverture "population" n'est renseignee que pour les
# combinaisons multi-operateurs (vide par operateur) -- on garde donc la couverture
# "geo" (surface du territoire), au seuil le plus permissif ("0", tout signal detectable),
# le chiffre le plus proche de ce qu'un dashboard de couverture affiche generalement.
COVERAGE_FIELDS = {'2g_coverage': 'couverture_2g', '3g_coverage': 'couverture_3g', '4g_coverage': 'couverture_4g'}


def get(path):
    r = requests.get(f"{BASE}/{path}", timeout=20, headers={'Accept': 'application/json'})
    r.raise_for_status()
    return r.json()['data']


def extract_operators(qos_payload):
    out = {}
    for op in ('MTN', 'MOOV', 'CELTIIS'):
        rec = qos_payload.get(op)
        if not rec:
            continue
        entry = {f: rec.get(f) for f in FIELDS if f in rec}
        for raw_key, out_key in COVERAGE_FIELDS.items():
            cov = rec.get(raw_key)
            geo = cov.get('geo') if isinstance(cov, dict) else None
            entry[out_key] = geo.get('0') if isinstance(geo, dict) else None
        out[op.lower()] = entry
    return out


def scrape():
    departments = get('departments')
    cities = get('cities')
    print(f"{len(departments)} departements, {len(cities)} communes a interroger...")

    result = {'departments': {}, 'cities': {}}

    for d in departments:
        qos = get(f"qos-data/department/{d['id']}")
        result['departments'][str(d['id'])] = {'name': d['name'], 'operateurs': extract_operators(qos)}
        print(f"  departement {d['name']} OK")
        time.sleep(DELAY)

    for c in cities:
        qos = get(f"qos-data/city/{c['id']}")
        result['cities'][str(c['id'])] = {'name': c['name'], 'operateurs': extract_operators(qos)}
        time.sleep(DELAY)
    print(f"  {len(cities)} communes recuperees")

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, separators=(',', ':'))
    print(f"\nEcrit : {OUT}")


if __name__ == '__main__':
    scrape()
