"""
Scraper Section D (Marche & Regulation) -- volet Services Financiers Mobiles (Mobile Money)
-- arcep.bj/services-financiers-mobiles/

Contrairement au rapport Telephonie Mobile, les noms de fichiers SFM ne suivent pas un
gabarit unique (Observatoire-SFM-T3_2025_TAB.pdf, Tableau-de-Bord_T1_SFM_2025.pdf,
TB_SFM_Decembre-2024.pdf...) -- la detection se fait donc par ORDRE D'APPARITION sur la
page (l'ARCEP liste toujours du plus recent au plus ancien), pas par un regex de nom.

Extraction ciblee sur les deux tableaux les plus fiables :
  - Tableau 1 : comptes SFM (actifs/dormants), parts de marche par operateur,
    taux de penetration, taux d'activite
  - Tableau 3 (partiel) : Depots et Retraits d'argent -- volume + valeur (Mds FCFA)
Les autres types de transaction (paiements marchands, P2P, international...) ont une
structure de cellules fusionnees plus fragile -- non extraits dans cette premiere passe.
"""
import json
import os
import re
import time
import requests
import pdfplumber
from urllib.parse import unquote

INDEX_URL = "https://arcep.bj/services-financiers-mobiles/"
PDF_LINK_RE = re.compile(r'href="(https://arcep\.bj/wp-content/uploads/(\d{4})/\d{2}/[^"]+\.pdf)"')

OBS_DIR = r"D:\eraste\Products\Telecom Data Analysis\Benin\arcep\data\observatoire\sfm"
OUT_JSON = r"D:\eraste\Products\Telecom Data Analysis\Benin\vitrine\data\sfm_data.json"

MIN_YEAR = 2024  # ne remonte pas plus loin pour cette premiere passe

TYPE_LABELS = {
    "Transactions des\nDépôts d'argents": 'depots',
    "Transactions des\nRetraits d'argents": 'retraits',
}


def discover_reports():
    r = requests.get(INDEX_URL, timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; AntenneBeninBot/1.0)'})
    r.raise_for_status()
    seen = set()
    ordered = []
    for url, year in PDF_LINK_RE.findall(r.text):
        if url in seen:
            continue
        seen.add(url)
        if int(year) >= MIN_YEAR:
            ordered.append(url)
    return ordered  # deja du plus recent au plus ancien (ordre de la page)


def ensure_downloaded(url):
    fname = unquote(url.rsplit('/', 1)[-1])
    os.makedirs(OBS_DIR, exist_ok=True)
    path = os.path.join(OBS_DIR, fname)
    if os.path.exists(path):
        return path, False
    r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; AntenneBeninBot/1.0)'})
    r.raise_for_status()
    with open(path, 'wb') as f:
        f.write(r.content)
    return path, True


def parse_number(s):
    s = str(s).strip().replace('\xa0', '').replace(' ', '')
    s = s.replace(',', '.') if ',' in s and '.' not in s else s
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


def clean_quarter(q):
    return q.replace('-', '_')


COMPTES_LABELS = {
    'Nombre de comptes SFM\nactifs': 'comptes_actifs',
    'Nombre de comptes SFM\ndormants': 'comptes_dormants',
    'Part de marché MTN\nMobile Money': 'mtn',
    'Part de marché MOOV\nMoney': 'moov',
    'Part de marché CELTIIS\nCASH': 'celtiis',
    "Taux de pénétration SFM": 'taux_penetration',
    "Taux d'activité": 'taux_activite',
}


def extract_comptes(pdf_path):
    out = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table or not table[0] or table[0][0] != 'Désignations':
                    continue
                header = table[0]
                if 'T' not in str(header[1]):
                    continue
                quarters = [clean_quarter(q) for q in header[1:] if q and 'Variation' not in q]
                for row in table[1:]:
                    if not row or not row[0]:
                        continue
                    label = row[0].strip()
                    if label not in COMPTES_LABELS:
                        continue
                    key = COMPTES_LABELS[label]
                    for q, v in zip(quarters, row[1:]):
                        val = str(v).replace('%', '').strip() if v else None
                        num = parse_number(val) if val else None
                        if key in ('mtn', 'moov', 'celtiis'):
                            out.setdefault(q, {}).setdefault('parts_marche', {})[key] = num
                        else:
                            out.setdefault(q, {})[key] = num
    return out


def extract_depots_retraits(pdf_path, quarters_order):
    """Cible uniquement les lignes Depots/Retraits (les plus proprement formatees),
    en reconstituant le type de transaction porte par la premiere cellule non-vide."""
    out = {}
    current_type = None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cells = [c for c in row if c not in (None, '')]
                    if not cells:
                        continue
                    if cells[0] in TYPE_LABELS:
                        current_type = TYPE_LABELS[cells[0]]
                        cells = cells[1:]
                    if current_type not in ('depots', 'retraits') or not cells:
                        continue
                    sub = cells[0]
                    values = cells[1:]
                    if 'Volume' in sub:
                        metric = 'volume'
                    elif 'Valeur' in sub:
                        metric = 'valeur_mds_fcfa'
                    else:
                        continue
                    nums = [parse_number(v) for v in values]
                    nums = [n for n in nums if n is not None]
                    # les 5 premieres valeurs numeriques = les 5 trimestres (la variation, si
                    # presente, est la derniere -- on l'ignore ici, non critique)
                    for q, v in zip(quarters_order, nums[:len(quarters_order)]):
                        out.setdefault(q, {}).setdefault(current_type, {})[metric] = v
    return out


def main():
    print(f"Verification des rapports sur {INDEX_URL} ...")
    urls = discover_reports()
    print(f"{len(urls)} rapports (>= {MIN_YEAR}) detectes, du plus recent au plus ancien")

    if os.path.exists(OUT_JSON):
        with open(OUT_JSON, encoding='utf-8') as f:
            store = json.load(f)
    else:
        store = {'comptes': {}, 'transactions': {}, 'meta': {}}

    # Traite du plus ANCIEN au plus RECENT : quand deux rapports se chevauchent sur un
    # meme trimestre, la version du rapport le plus recent doit gagner (ecrase en dernier).
    for url in reversed(urls):
        path, is_new = ensure_downloaded(url)
        print(f"  {'telecharge' if is_new else 'deja present'} : {os.path.basename(path)}")
        comptes = extract_comptes(path)
        if not comptes:
            print(f"    ! aucune donnee 'comptes SFM' extraite de ce fichier -- structure differente, ignore")
            continue
        quarters_order = list(comptes.keys())
        transactions = extract_depots_retraits(path, quarters_order)
        for q, vals in comptes.items():
            store['comptes'][q] = vals
        for q, vals in transactions.items():
            store['transactions'].setdefault(q, {}).update(vals)
        time.sleep(1)

    store['meta']['derniere_verification'] = time.strftime('%Y-%m-%d')
    store['meta']['verifie'] = False

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"\nEcrit : {OUT_JSON}")
    print("STATUT : verifie=false -- revue humaine recommandee avant affichage public.")


if __name__ == '__main__':
    main()
