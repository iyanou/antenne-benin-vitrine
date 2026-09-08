"""
Scraper Section D -- volet Tarifs Internet (Mobile + FTTH) -- arcep.bj/tarifs-internet/

Contrairement aux autres observatoires (series trimestrielles), ces rapports sont des
catalogues d'offres a un instant T -- pas un historique. On extrait donc uniquement le
DERNIER rapport disponible pour chaque type (Mobile, FTTH), en cliche instantane.

FTTH : tableau "Redevances mensuelles" mal structure par pdfplumber (colonnes operateur
qui se decalent d'une ligne a l'autre selon les cellules fusionnees) -- extraction par
position x/y des mots plutot que par index de colonne brut, plus fiable ici.
Mobile : grille de forfaits tres eparse (beaucoup d'operateurs sans offre a un palier
donne) -- on extrait uniquement le palier "avec FUP" a 5000 FCFA, le seul ou les 3
operateurs ont systematiquement une offre, pour une comparaison honnete et fiable.
"""
import json
import os
import re
import time
import requests
import pdfplumber
from urllib.parse import unquote

INDEX_URL = "https://arcep.bj/tarifs-internet/"
PDF_LINK_RE = re.compile(r'href=\s*"(https://arcep\.bj/wp-content/uploads/(\d{4})/\d{2}/[^"]+\.pdf)"')

HERE = os.path.dirname(os.path.abspath(__file__))
OBS_DIR = os.path.normpath(os.path.join(HERE, "..", "cache", "tarifs-internet"))
OUT_JSON = os.path.normpath(os.path.join(HERE, "..", "data", "tarifs_data.json"))

OPERATOR_PATTERNS = [
    (re.compile(r'\bSBIN\b', re.I), 'sbin'),
    (re.compile(r'\bISOCEL\b', re.I), 'isocel'),
    (re.compile(r'\bGVA\b', re.I), 'gva_benin'),
    (re.compile(r'\bMTN\b', re.I), 'mtn'),
    (re.compile(r'\bMOOV\b', re.I), 'moov'),
]


def discover_reports():
    r = requests.get(INDEX_URL, timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; AntenneBeninBot/1.0)'})
    r.raise_for_status()
    seen, ordered = set(), []
    for url, year in PDF_LINK_RE.findall(r.text):
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


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


def normalize_operator(name):
    for pat, key in OPERATOR_PATTERNS:
        if pat.search(name):
            return key
    return None


def parse_fcfa(tokens):
    """Colle des tokens numeriques adjacents ('1','200','000' -> 1200000)."""
    return int(''.join(tokens).replace(' ', ''))


def group_rows(words, tol=2.0):
    rows = []
    for w in sorted(words, key=lambda w: (w['top'], w['x0'])):
        if rows and abs(w['top'] - rows[-1][0]['top']) <= tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    return rows


def extract_ftth(pdf_path):
    """{'installation': {op: fcfa}, 'redevances': {'partage'|'dedie': {mbps: {op: fcfa}}}}"""
    result = {'installation': {}, 'redevances': {'partage': {}, 'dedie': {}}}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            if 'FRAIS' not in text.upper() or 'INSTALLATION' not in text.upper():
                continue
            for line in text.split('\n'):
                m = re.match(r'^(SBIN|ISOCEL|GVA\s*BENIN)\s+([\d\s]+?)\s+\d+\s*semaine', line.strip(), re.I)
                if m:
                    op = normalize_operator(m.group(1))
                    fcfa = int(re.sub(r'\s+', '', m.group(2)))
                    if op:
                        result['installation'][op] = fcfa

            if 'REDEVANCES MENSUELLES' not in text.upper():
                continue

            words = page.extract_words()
            capacites_row = [w for w in words if w['text'] == 'Capacités']
            if not capacites_row:
                continue
            header_top = capacites_row[0]['top']
            header = [w for w in words if abs(w['top'] - header_top) < 3 and normalize_operator(w['text'])]
            if not header:
                continue
            # centre x par operateur (mots consecutifs de meme operateur, ex "GVA"+"BENIN")
            op_x = {}
            for w in header:
                op = normalize_operator(w['text'])
                op_x.setdefault(op, []).append(w['x0'])
            col_bounds = sorted((min(xs), op) for op, xs in op_x.items())

            def bucket(x0):
                best, best_dist = None, 1e9
                for cx, op in col_bounds:
                    if abs(x0 - cx) < best_dist:
                        best, best_dist = op, abs(x0 - cx)
                return best if best_dist < 40 else None

            data_words = [w for w in words if w['top'] > max(w2['top'] for w2 in header)]
            rows = group_rows(data_words)

            segment = 'partage'
            prev_mbps = -1
            for row in rows:
                row = sorted(row, key=lambda w: w['x0'])
                texts = [w['text'] for w in row]
                joined = ' '.join(texts)
                m = re.search(r'(\d+)\s*Mbps', joined)
                if not m:
                    continue
                mbps = int(m.group(1))
                if mbps < prev_mbps:
                    segment = 'dedie'
                prev_mbps = mbps

                # mots numeriques a droite de "Validité" (x0 > 300), regroupes par colonne operateur
                value_words = [w for w in row if w['x0'] > 300 and re.match(r'^[\d,]+$', w['text'])]
                by_op = {}
                for w in value_words:
                    op = bucket(w['x0'])
                    if op:
                        by_op.setdefault(op, []).append(w['text'])
                for op, toks in by_op.items():
                    result['redevances'][segment].setdefault(str(mbps), {})[op] = parse_fcfa(toks)
    return result


FUP_ROW_RE = re.compile(
    r'^5\s*000\s+([\d,]+)\s*Go(?:\s*Plus)?/(\d)Mbps\s*30\s*jours\s+'
    r'([\d,]+)\s*Go(?:\s*Plus)?/(\d)Mbps\s*30\s*jours\s+'
    r'([\d,]+)\s*Go(?:\s*Plus)?/(\d)Mbps\s*30\s*jours',
    re.I,
)


def extract_mobile_fup_5000(pdf_path):
    """Comparaison au palier 5000 FCFA 'avec FUP', seul palier ou MTN/MOOV/SBIN ont tous une offre."""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            if 'MTN' not in text.upper() or 'MOOV' not in text.upper():
                continue
            norm = re.sub(r'[ \t]+', ' ', text)
            for line in norm.split('\n'):
                m = FUP_ROW_RE.match(line.strip())
                if m:
                    go = lambda s: float(s.replace(',', '.'))
                    return {
                        'mtn': {'go': go(m.group(1)), 'mbps': int(m.group(2))},
                        'moov': {'go': go(m.group(3)), 'mbps': int(m.group(4))},
                        'sbin': {'go': go(m.group(5)), 'mbps': int(m.group(6))},
                    }
    return None


def main():
    print(f"Verification des rapports sur {INDEX_URL} ...")
    urls = discover_reports()
    ftth_urls = [u for u in urls if 'ftth' in u.lower()]
    mobile_urls = [u for u in urls if 'mobile' in u.lower()]
    print(f"{len(ftth_urls)} rapports FTTH, {len(mobile_urls)} rapports Mobile detectes")

    # dernier rapport de chaque type -- periode extraite du nom de fichier (pas fiable de se fier
    # a la seule date d'upload, plusieurs rapports de periodes differentes sont uploades le meme mois)
    MONTH_TO_Q = {'mars': 1, 'juin': 2, 'septembre': 3, 'decembre': 4, 'décembre': 4}

    def extract_period(u):
        fname = u.lower()
        m = re.search(r't(\d)[_-]?(\d{4})', fname)
        if m:
            return (int(m.group(2)), int(m.group(1)))
        m = re.search(r'(\d{4})_t(\d)', fname)
        if m:
            return (int(m.group(1)), int(m.group(2)))
        for name, q in MONTH_TO_Q.items():
            m = re.search(name + r'[-_]?(\d{4})', fname)
            if m:
                return (int(m.group(1)), q)
        m = re.search(r'/uploads/(\d{4})/(\d{2})/', u)
        return (int(m.group(1)), int(m.group(2)) // 3 + 1) if m else (0, 0)

    def latest(url_list):
        return sorted(url_list, key=extract_period)[-1] if url_list else None

    ftth_url = latest(ftth_urls)
    mobile_url = latest(mobile_urls)

    store = {'ftth': {}, 'mobile_fup_5000': {}, 'meta': {}}

    if ftth_url:
        path, is_new = ensure_downloaded(ftth_url)
        print(f"FTTH {'telecharge' if is_new else 'deja present'} : {os.path.basename(path)}")
        store['ftth'] = extract_ftth(path)
        store['meta']['ftth_source'] = os.path.basename(path)

    if mobile_url:
        path, is_new = ensure_downloaded(mobile_url)
        print(f"Mobile {'telecharge' if is_new else 'deja present'} : {os.path.basename(path)}")
        fup = extract_mobile_fup_5000(path)
        if fup:
            store['mobile_fup_5000'] = fup
        store['meta']['mobile_source'] = os.path.basename(path)

    store['meta']['derniere_verification'] = time.strftime('%Y-%m-%d')
    store['meta'].setdefault('verifie', False)
    store['meta']['note'] = (
        "Cliche instantane du dernier rapport disponible (pas une serie temporelle -- ce sont "
        "des catalogues d'offres, pas des mesures recurrentes). Mobile limite au palier 5000 FCFA "
        "'avec FUP', seul palier ou MTN/Moov/SBIN(marque Celtiis) ont tous une offre comparable."
    )

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"\nEcrit : {OUT_JSON}")


if __name__ == '__main__':
    main()
