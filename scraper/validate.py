"""
Controles de coherence des fichiers data/*.json.

Appele par orchestrate.py apres chaque scraper : si un controle echoue, le fichier
precedent est restaure et l'execution est signalee en echec. Un operateur, une colonne ou
un trimestre ne peut donc plus disparaitre en silence.

Usage : python validate.py            -> controle tous les fichiers, code 1 si erreur
"""
import json
import os
import sys

import arcep_common as ac

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))
OPS = ('mtn', 'moov', 'celtiis')


def series(errors, name, data, last=None, contiguous=True):
    """Trimestres tous consecutifs, et dernier trimestre = dernier rapport publie."""
    qs = sorted(data, key=ac.qkey)
    if not qs:
        errors.append(f"{name} : vide")
        return
    if contiguous and qs != ac.quarters_ending(qs[-1], len(qs)):
        errors.append(f"{name} : trimestre(s) manquant(s) dans {qs}")
    if last and qs[-1] != last:
        errors.append(f"{name} : s'arrete a {qs[-1]}, alors que le dernier rapport est {last}")
    for a, b in zip(qs, qs[1:]):
        if data[a] == data[b]:
            errors.append(f"{name} : {a} et {b} identiques")


def same(errors, label, a, b, tol=0):
    if a is None or b is None or abs(a - b) > tol:
        errors.append(f"{label} : {a} != {b}")


def check_market(d):
    e, last = [], d['meta'].get('dernier_rapport')
    series(e, 'abonnements', d['abonnements'], last)
    series(e, 'trafics', d['trafics'], last)
    for q, v in d['abonnements'].items():
        missing = [op for op in OPS if not v.get(op)]
        if missing:
            e.append(f"abonnements {q} : operateur absent {missing}")
        else:
            same(e, f"abonnements {q} somme/total", sum(v[op] for op in OPS), v.get('total'))
    for q, v in d['trafics'].items():
        if not all(v.get(k) for k in ('voix_min', 'sms_nb', 'data_go')):
            e.append(f"trafics {q} : valeur absente")
    series(e, 'technologies', d['technologies'], last)
    for q, v in d['technologies'].items():
        same(e, f"technologies {q} 2G+3G+4G/total", sum(v.get(k) or 0 for k in ('2g', '3g', '4g')),
             d['abonnements'].get(q, {}).get('total'))
    series(e, 'parts_valeur', d['parts_valeur'], last)
    for q, v in d['parts_valeur'].items():
        if not all(v.get(op) for op in OPS):
            e.append(f"parts_valeur {q} : operateur absent")
        same(e, f"parts_valeur {q} somme", sum(v.get(op) or 0 for op in OPS), 100, 0.3)
    e += check_gender('genre', d.get('genre', {}))
    return e


def check_gender(name, g):
    return [f"{name} {q} : hommes + femmes != 100" for q, v in g.items()
            if abs((v.get('hommes') or 0) + (v.get('femmes') or 0) - 100) > 0.2]


def check_sfm(d):
    e, last = [], d['meta'].get('dernier_rapport')
    series(e, 'comptes', d['comptes'], last)
    series(e, 'transactions', d['transactions'], last)
    for q, v in d['comptes'].items():
        p = v.get('parts_marche', {})
        missing = [op for op in OPS if p.get(op) is None and not (op == 'celtiis' and q == 'T3_2022')]
        if missing:
            e.append(f"comptes {q} : part de marche absente {missing}")
        same(e, f"comptes {q} somme des parts", sum(x for x in p.values() if x), 100, 0.1)
        act, dorm = v.get('comptes_actifs'), v.get('comptes_dormants')
        if not act or not dorm or v.get('taux_penetration') is None:
            e.append(f"comptes {q} : valeur absente")
        else:
            same(e, f"comptes {q} taux d'activite", v.get('taux_activite'), act / (act + dorm) * 100, 1.5)
    for q, v in d['transactions'].items():
        for m in ('volume', 'valeur_mds_fcfa'):
            dep, ret = v.get('depots', {}).get(m), v.get('retraits', {}).get(m)
            # historiquement retraits = 75 a 93 % des depots ; tres loin = mauvaise ligne lue
            if not dep or not ret or not 0.5 <= ret / dep <= 1.3:
                e.append(f"transactions {q} {m} : depots={dep} retraits={ret} incoherent")
    return e


def check_complaints(d):
    e, last = [], d['meta'].get('dernier_rapport')
    series(e, 'recues', d['recues'], last)
    series(e, 'traitees', d['traitees'], last)
    for q, v in d['recues'].items():
        same(e, f"recues {q} somme/total",
             sum(v.get(k) or 0 for k in ('commerciales', 'techniques', 'postales')), v.get('total'))
        if v.get('commerciales') is None or v.get('techniques') is None:
            e.append(f"recues {q} : categorie absente")
    for q, v in d['traitees'].items():
        parts = [v.get(k) for k in ('fondees', 'infondees', 'classees')]
        same(e, f"traitees {q} somme/total", None if None in parts else sum(parts), v.get('total'))
        same(e, f"{q} recues/traitees", d['recues'].get(q, {}).get('total'), v.get('total'))
    return e


def check_internet(d):
    e, last = [], d['meta'].get('dernier_rapport')
    series(e, 'fixe', d['fixe'], last)
    series(e, 'mobile', d['mobile'], last)
    for q, v in d['fixe'].items():
        same(e, f"fixe {q} somme FAI/total", sum(x or 0 for x in v.get('isp', {}).values()), v.get('total'))
    for q, v in d['mobile'].items():
        o = v.get('operateurs', {})
        if not all(o.get(op) for op in OPS) and ac.qkey(q) >= ac.qkey('T1_2023'):
            e.append(f"mobile {q} : operateur absent")
        same(e, f"mobile {q} somme/total", sum(x or 0 for x in o.values()), v.get('total'))
    e += check_gender('genre_mobile', d.get('genre_mobile', {}))
    return e


def check_fixe(d):
    e = []
    series(e, 'fixe', d['donnees'], d['meta'].get('dernier_rapport'))
    for q, v in d['donnees'].items():
        if not v.get('parc_abonnes'):
            e.append(f"fixe {q} : parc absent")
    return e


def check_postal(d):
    e = []
    series(e, 'recettes', d['recettes'], d['meta'].get('dernier_rapport'))
    for q, v in d['recettes'].items():
        same(e, f"recettes {q} somme/total", sum(x or 0 for k, x in v.items() if k != 'total'), v.get('total'), 10)
    for seg, by in d['parts_marche'].items():
        for measure, qs in by.items():
            series(e, f"parts {seg}/{measure}", qs, d['meta'].get('dernier_rapport'), contiguous=False)
    return e


def check_tarifs(d):
    e, m = [], d['meta']
    if not all(op in d['ftth'].get('installation', {}) for op in ('sbin', 'isocel', 'gva_benin')):
        e.append('ftth : frais de raccordement incomplets')
    if not d['ftth'].get('redevances', {}).get('partage') or not d['ftth']['redevances'].get('dedie'):
        e.append('ftth : redevances absentes')
    common = [o for o in d['mobile'] if all(op in o for op in ('mtn', 'moov', 'sbin'))]
    if len(common) < 3:
        e.append(f"mobile : seulement {len(common)} palier(s) communs aux 3 operateurs")
    for o in d['mobile']:
        for op in ('mtn', 'moov', 'sbin'):
            if op in o and not any(u in o[op].get('volume', '') for u in ('Mo', 'Go')):
                e.append(f"mobile {o['prix']} {op} : volume illisible {o[op]}")
    hm, hf = d.get('historique_mobile', {}), d.get('historique_ftth', {})
    if len(hm) < 2 or max(hm, key=ac.qkey) != m.get('mobile_periode') or hm[m['mobile_periode']] != d['mobile']:
        e.append('historique_mobile : absent, ou dernier catalogue different du catalogue affiche')
    for q, offers in hm.items():
        for o in offers:
            for op in ('mtn', 'moov', 'sbin'):
                if op in o and not o[op].get('mo'):
                    e.append(f"historique_mobile {q} {o['prix']} {op} : volume non converti {o[op].get('volume')}")
        for op in ('mtn', 'moov', 'sbin'):
            f = sorted((o['prix'], o[op]['mo']) for o in offers if o['fup'] and op in o)
            for (p1, v1), (p2, v2) in zip(f, f[1:]):
                if v2 < v1:
                    e.append(f"historique_mobile {q} {op} : {p2} FCFA donne moins ({v2} Mo) que {p1} FCFA ({v1} Mo)")
    if len(hf) < 2 or ac.qkey(max(hf, key=ac.qkey)) > ac.qkey(m.get('ftth_periode', 'T1_2000')):
        e.append('historique_ftth : absent ou incoherent avec le dernier rapport')
    if m.get('mobile_periode') != m.get('dernier_rapport') or m.get('ftth_periode') != m.get('dernier_rapport'):
        print(f"  (info) tarifs : mobile {m.get('mobile_periode')}, fibre {m.get('ftth_periode')}, "
              f"dernier rapport {m.get('dernier_rapport')}")
    return e


def check_revenus(d):
    e = [f"revenus {y} : ressources propres absentes" for y, v in d['par_annee'].items()
         if not v.get('ressources_propres')] or ([] if d['par_annee'] else ['revenus : vide'])
    cc = d.get('chiffres_cles', {})
    if not cc or max(cc) != max(d['par_annee']):
        e.append('chiffres_cles : absents pour la derniere annee publiee')
    for y, v in cc.items():
        if not v.get('ca_marche_mds'):
            e.append(f"chiffres_cles {y} : chiffre d'affaires du marche absent")
        for k in ('parts_valeur_pct', 'sfm_parts_comptes_pct', 'sfm_parts_ca_pct'):
            if k in v:
                same(e, f"chiffres_cles {y} {k} somme", sum(v[k].values()), 100, 0.5)
        if v.get('abonnes_uniques') and v.get('cartes_sim_millions') and not (
                1 < v['cartes_sim_millions'] * 1e6 / v['abonnes_uniques'] < 3):
            e.append(f"chiffres_cles {y} : SIM / abonnes uniques invraisemblable")
    return e


RANGES = {'succes_voix': (50, 100), 'blocage_voix': (0, 50), 'dl_3g': (50, 20000),
          'ul_3g': (10, 5000), 'dl_4g': (0.5, 200), 'ul_4g': (0.1, 100)}


def check_qos_national(d):
    e, ends = [], {}
    for doc in d.values():
        lo, hi = RANGES[doc['indicateur']]
        dates = [j['date'] for j in doc['jours']]
        if len(dates) != len(set(dates)):
            e.append(f"{doc['indicateur']} {doc['annee']}-{doc['mois']} : jour en double")
        for j in doc['jours']:
            for op in OPS:
                if j.get(op) is None:
                    e.append(f"{doc['indicateur']} {j['date']} {op} : valeur absente")
                elif not lo <= j[op] <= hi:
                    e.append(f"{doc['indicateur']} {j['date']} {op} : {j[op]} hors plage {lo}-{hi}")
        ends[doc['indicateur']] = max(ends.get(doc['indicateur'], ''), max(dates))
    if len(set(ends.values())) > 1 or set(ends) != set(RANGES):
        e.append(f"indicateurs pas tous a la meme date : {ends}")
    return e


def check_qos_regional(d):
    e = []
    for kind, n in (('departments', 12), ('cities', 77)):
        if len(d.get(kind, {})) != n:
            e.append(f"{kind} : {len(d.get(kind, {}))} zones au lieu de {n}")
        for op in OPS:
            if sum(op in z['operateurs'] for z in d[kind].values()) < 0.8 * n:
                e.append(f"{kind} : {op} absent de plus de 20 % des zones")
    return e


CHECKS = {
    'qos_national.json': check_qos_national, 'qos_regional.json': check_qos_regional,
    'market_data.json': check_market, 'sfm_data.json': check_sfm,
    'complaints_data.json': check_complaints, 'internet_data.json': check_internet,
    'fixe_data.json': check_fixe, 'postal_data.json': check_postal,
    'tarifs_data.json': check_tarifs, 'revenus_arcep_data.json': check_revenus,
}


def quarters_of(node):
    """{chemin: ensemble de trimestres} pour chaque serie trimestrielle du fichier."""
    out = {}

    def walk(n, path):
        if isinstance(n, dict):
            qs = {k for k in n if len(k) == 7 and k[0] == 'T' and k[2] == '_'}
            if qs:
                out[path] = qs
            for k, v in n.items():
                if k not in qs:
                    walk(v, path + '/' + k)
    walk(node, '')
    return out


def validate_file(fname, previous=None):
    """Liste d'erreurs ; previous = contenu precedent, pour detecter une regression."""
    try:
        with open(os.path.join(DATA_DIR, fname), encoding='utf-8') as f:
            data = json.load(f)
        errors = CHECKS[fname](data)
        if previous:
            now = quarters_of(data)
            for path, qs in quarters_of(json.loads(previous)).items():
                lost = qs - now.get(path, set())
                if lost and path in now:
                    errors.append(f"{path} : trimestre(s) disparu(s) {sorted(lost)}")
    except (KeyError, TypeError, ValueError, AttributeError, OSError) as ex:
        errors = [f"structure inattendue : {type(ex).__name__} {ex}"]
    return [f"{fname} : {x}" for x in errors]


if __name__ == '__main__':
    errs = [x for name in CHECKS for x in validate_file(name)]
    for x in errs:
        print('  ! ' + x)
    print(f"{len(CHECKS)} fichiers controles, {len(errs)} erreur(s)")
    sys.exit(1 if errs else 0)
