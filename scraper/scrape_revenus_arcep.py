"""
Scraper Section D -- volet Revenus sectoriels / redevances -- arcep.bj/rapports/

Deux chiffres par annee, extraits du rapport annuel d'activites (section
"1.3.2 Ressources financieres") :
  - ressources_propres : budget de fonctionnement du regulateur lui-meme
  - recouvre_pour_etat : redevances/taxes sectorielles reversees au Tresor public
    (absent de la structure du rapport avant 2023, et pas encore publie au moment
    de la redaction du rapport 2025 -- normal, pas un bug d'extraction)

Rapports annuels tres volumineux (80-280+ pages, gros PDF avec images) -- on ne
telecharge et parse que la page contenant la section 1.3.2, pas tout le document.
"""
import json
import os
import re
import time
import requests
import pdfplumber
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
