"""
Scraper Section D -- volet Revenus sectoriels / redevances -- arcep.bj/rapports/

Deux chiffres par annee, extraits du rapport annuel d'activites (section
"1.3.2 Ressources financieres") :
  - ressources_propres : budget de fonctionnement du regulateur lui-meme
  - recouvre_pour_etat : redevances/taxes sectorielles reversees au Tresor public
    (absent de la structure du rapport avant 2023, et pas encore publie au moment
    de la redaction du rapport 2025 -- normal, pas un bug d'extraction)

Ajoute le 2026-11-24 : chiffres cles du marche ("chiffres_cles" par annee), lus dans le
texte du rapport par des phrases types (chiffre d'affaires, abonnes uniques, penetration,
ARPU, trafics, plaintes, investissements, parts de marche en valeur, Mobile Money,
sanctions). Un indicateur dont la phrase n'est pas trouvee est simplement absent : il
n'est jamais devine. Les phrases ont ete verifiees sur les rapports 2023, 2024 et 2025.
"""
import json
import os
import re
import time
import requests
import pdfplumber

import arcep_common as ac
from urllib.parse import unquote

INDEX_URL = "https://arcep.bj/rapports/"
PDF_LINK_RE = re.compile(r'href=\s*"(https://arcep\.bj/wp-content/uploads/[^"]+\.pdf)"')

HERE = os.path.dirname(os.path.abspath(__file__))
OBS_DIR = os.path.normpath(os.path.join(HERE, "..", "cache", "rapports-annuels"))
OUT_JSON = os.path.normpath(os.path.join(HERE, "..", "data", "revenus_arcep_data.json"))

OWN_RESOURCES_PATTERNS = [
    re.compile(r"total des ressources[^(]*\(([\d\s]+)\)\s*francs", re.I),
    re.compile(r"budget approuv[ée][^(]*\(([\d\s]+)\)\s*de\s*francs", re.I),
]
STATE_REMIT_RE = re.compile(
    r"pour le compte de l.?Etat un\s*montant de[^(]*\(([\d\s]+)\)\s*(?:de\s*)?francs", re.I
)
YEAR_RE = re.compile(r"(?:au titre de l.?ann[ée]e|au cours de l.?ann[ée]e|au titre de la gestion)\s*(\d{4})", re.I)


MIN_REPORT_YEAR = 2022  # avant 2022, la section "recouvre pour l'Etat" n'existe pas encore


def discover_reports():
    r = requests.get(INDEX_URL, timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; AntenneBeninBot/1.0)'})
    r.raise_for_status()
    urls = list(dict.fromkeys(PDF_LINK_RE.findall(r.text)))
    out = []
    for u in urls:
        if 'rapport' not in u.lower() or 'communique' in u.lower():
            continue
        m = re.search(r'(20[12]\d)', u)
        if m and int(m.group(1)) < MIN_REPORT_YEAR:
            continue
        out.append(u)
    return out


def ensure_downloaded(url):
    fname = unquote(url.rsplit('/', 1)[-1])
    os.makedirs(OBS_DIR, exist_ok=True)
    path = os.path.join(OBS_DIR, fname)
    if os.path.exists(path):
        return path, False
    r = requests.get(url, timeout=90, headers={'User-Agent': 'Mozilla/5.0 (compatible; AntenneBeninBot/1.0)'})
    r.raise_for_status()
    with open(path, 'wb') as f:
        f.write(r.content)
    return path, True


def parse_fcfa(s):
    return int(re.sub(r'\s+', '', s))


def extract_revenus(pdf_path):
    """{'annee': int, 'ressources_propres': int, 'recouvre_pour_etat': int|None}"""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ''
            # evite le faux-positif de la liste des graphiques / sommaire, qui cite les
            # memes titres de section sans les chiffres
            if 'ressources financi' not in text.lower() or 'francs' not in text.lower():
                continue
            # la sous-section "recouvre pour l'Etat" est parfois sur la page suivante
            window = text
            if i + 1 < len(pdf.pages):
                window += ' ' + (pdf.pages[i + 1].extract_text() or '')
            norm = re.sub(r'\s+', ' ', window)
            year_m = YEAR_RE.search(norm)
            if not year_m:
                continue
            own = None
            for pat in OWN_RESOURCES_PATTERNS:
                m = pat.search(norm)
                if m:
                    own = parse_fcfa(m.group(1))
                    break
            if own is None:
                continue
            state_m = STATE_REMIT_RE.search(norm)
            state = parse_fcfa(state_m.group(1)) if state_m else None
            return {
                'annee': int(year_m.group(1)),
                'ressources_propres': own,
                'recouvre_pour_etat': state,
            }
    return None


def num(s):
    s = re.sub(r'\s', '', s).replace(',', '.')
    return float(s) if '.' in s else int(s)


N = r'(\d[\d\s]*(?:,\d+)?)'
OPS3 = ('mtn', 'moov', 'celtiis')
KEY_FIGURES = {
    # cle : (motif sur le texte normalise -- minuscules, sans accents --, groupes -> valeurs)
    'ca_marche_mds': r"marche des communications electroniques affiche au 31 decembre 20\d\d, un chiffre d'affaires (?:estime a |de )" + N + " milliards",
    'ca_mobile_mds': r"operateurs de reseaux de communications electroniques mobiles en 20\d\d (?:est|a ete)(?: estime a| evalue a| de)? " + N + " milliards",
    'investissements_mds': r"volume global des investissements dans les reseaux de communications electroniques (?:est|de) (?:estime a |evalue a |de )?" + N + " milliards",
    'cartes_sim_millions': r"nombre de cartes sim actives connectees aux reseaux de communications electroniques mobiles est (?:estime|evalue) a " + N + " millions",
    'abonnes_uniques': r"nombre d'abonnes\d* a la telephonie mobile est (?:estime|evalue) a " + N + " au 31 decembre",
    'penetration_mobile_pct': r"soit une penetration mobile de " + N + r" ?%",
    'penetration_internet_pct': r"soit une penetration internet mobile de " + N + r" ?%",
    'arpu_fcfa': r"\(average revenue per user . arpu\) au cours de l'annee(?: 20\d\d)? est evalue a " + N + " fcfa",
    'trafic_voix_mds_min': r"trafic voix[^.]*?" + N + " milliards de minutes",
    'trafic_data_millions_go': r"trafic internet mobile[^.]*?" + N + " millions de g",
    'sms_millions': r"volume des sms echanges[^.]*?" + N + " millions",
    'plaintes': r"\((\d+)\) plaintes ont ete enregistrees",
    'ca_sfm_mds': r"chiffre d'affaires des fournisseurs du service financier mobile est de " + N + " milliards",
}
GROUPS = {
    'investissements_par_operateur_mds': (r"spacetel benin sa, moov ?africa benin sa,? et sbin sa,? ont investi[^.]*?montants de "
                                          + N + " ; " + N + " et " + N + " milliards", OPS3),
    'parts_valeur_pct': (r"spacetel benin, moov africa benin et sbin, qui detiennent respectivement des parts de marche de "
                         + N + "%, " + N + "% et " + N + "%", OPS3),
    'sfm_parts_comptes_pct': (r"mtn mobile money, moov money et celtiis cash detiennent respectivement "
                              + N + "%, " + N + "% et " + N + "% des comptes", OPS3),
    'sfm_parts_ca_pct': (r"environ " + N + "% pour mtn mobile money, " + N + "% pour moov money et " + N + "% pour celtiis cash", OPS3),
}
SANCTION_RE = re.compile(r"sanctions pecuniaires des montants respectifs[^(]*\(([\d\s]+)\) francs cfa a l'encontre de "
                         r"([a-z ]+?) sa et[^(]*\(([\d\s]+)\) francs cfa a l'encontre de ([a-z ]+?) sa")
OP_NAMES = {'spacetel benin': 'mtn', 'moov africa benin': 'moov', 'sbin': 'celtiis'}


def report_text(path):
    """Texte complet normalise, mis en cache a cote du PDF (gros rapports)."""
    cache = path + '.txt'
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(path):
        with open(cache, encoding='utf-8') as f:
            return f.read()
    with pdfplumber.open(path) as pdf:
        text = ac.norm(' '.join(page.extract_text() or '' for page in pdf.pages))
    with open(cache, 'w', encoding='utf-8') as f:
        f.write(text)
    return text


def extract_key_figures(text):
    out = {}
    for key, pattern in KEY_FIGURES.items():
        m = re.search(pattern, text)
        if m:
            out[key] = num(m.group(1))
    for key, (pattern, names) in GROUPS.items():
        m = re.search(pattern, text)
        if m:
            out[key] = {n: num(v) for n, v in zip(names, m.groups())}
    m = SANCTION_RE.search(text)
    if m:
        out['sanctions_couverture_fcfa'] = {OP_NAMES.get(m.group(2).strip(), m.group(2).strip()): num(m.group(1)),
                                           OP_NAMES.get(m.group(4).strip(), m.group(4).strip()): num(m.group(3))}
    return out


def main():
    print(f"Verification des rapports sur {INDEX_URL} ...")
    urls = discover_reports()
    print(f"{len(urls)} rapports annuels detectes")

    if os.path.exists(OUT_JSON):
        with open(OUT_JSON, encoding='utf-8') as f:
            store = json.load(f)
    else:
        store = {'par_annee': {}, 'meta': {}}

    for url in urls:
        path, is_new = ensure_downloaded(url)
        print(f"  {'telecharge' if is_new else 'deja present'} : {os.path.basename(path)}")
        result = extract_revenus(path)
        if not result:
            print(f"    ! rien extrait -- section absente ou structure differente")
            continue
        annee = str(result.pop('annee'))
        store['par_annee'][annee] = result
        print(f"    OK {annee} : {result}")
        figures = extract_key_figures(report_text(path))
        if figures:
            store.setdefault('chiffres_cles', {})[annee] = figures
            print(f"    chiffres cles {annee} : {len(figures)} indicateurs")
        time.sleep(1)

    store['meta']['derniere_verification'] = time.strftime('%Y-%m-%d')
    store['meta'].setdefault('verifie', True)
    store['meta']['note'] = (
        "Source : rapports annuels d'activites ARCEP Benin, section 'Ressources financieres'. "
        "'recouvre_pour_etat' absent avant 2023 (structure du rapport ne separait pas encore ce "
        "poste) et pas encore publie pour 2025 au moment de l'extraction -- pas une erreur, "
        "l'information n'existe simplement pas dans le rapport source a ce jour."
    )

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"\nEcrit : {OUT_JSON}")


if __name__ == '__main__':
    main()
