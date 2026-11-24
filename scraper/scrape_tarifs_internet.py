"""
Scraper Section D -- volet Tarifs Internet (Mobile + FTTH) -- arcep.bj/tarifs-internet/

Contrairement aux autres observatoires (series trimestrielles), ces rapports sont des
catalogues d'offres a un instant T -- pas un historique. On extrait donc uniquement le
DERNIER rapport disponible pour chaque type (Mobile, FTTH), en cliche instantane.

FTTH : tableau "Redevances mensuelles" mal structure par pdfplumber (colonnes operateur
qui se decalent d'une ligne a l'autre selon les cellules fusionnees) -- extraction par
position x/y des mots plutot que par index de colonne brut, plus fiable ici.
Mobile : catalogue complet des forfaits Internet, lu par colonne operateur. Depuis le
30 septembre 2026, l'ARCEP le publie dans l'"Observatoire des tarifs mobiles"
(page /telephonie-mobile/) et non plus dans un document a part : les deux pages sont
lues, et c'est la periode la plus recente qui est affichee. Les volumes sont repris tels
qu'ecrits par l'ARCEP (elle melange 8333 Mo et 8,13 Go selon l'operateur), sans conversion.
"""
import json
import os
import re
import time
import requests
import pdfplumber

import arcep_common as ac

INDEX_URL = "https://arcep.bj/tarifs-internet/"
MOBILE_INDEX_URL = "https://arcep.bj/telephonie-mobile/"

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


def clean_offer(s):
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'Go\s*Plus', 'Go Plus', s)
    s = re.sub(r'\s*/\s*(\d+)\s*Mbps', r' / \1 Mbps', s)
    s = re.sub(r'\s*\+\s*', ' + ', s)
    return s.replace('Whatsapp', 'WhatsApp')


def extract_mobile(pdf_path):
    """[{'prix': int, 'fup': bool, 'mtn'|'moov'|'sbin': {'volume': str, 'validite': str}}]"""
    for table in ac.iter_tables(pdf_path):
        heads = [' '.join(str(c) for c in row if c) for row in table]
        if not any('sans FUP' in h for h in heads):
            continue
        hrow = next(i for i, h in enumerate(heads) if 'Forfait (FCFA)' in h)
        vol = [i for i, c in enumerate(table[hrow]) if c == 'Volume']
        val = [i for i, c in enumerate(table[hrow]) if c and c.startswith('Valid')]
        ops = [c.lower() for row in table[:hrow] for c in row if c in ('MTN', 'MOOV', 'SBIN')]
        if len(vol) != 3 or len(val) != 3 or ops != ['mtn', 'moov', 'sbin']:
            raise ValueError(f"grille de forfaits inattendue : {os.path.basename(pdf_path)}")
        cols = sorted([(i, op, 'volume') for i, op in zip(vol, ops)] +
                      [(i, op, 'validite') for i, op in zip(val, ops)])
        offers, fup = [], False
        for row in table[hrow + 1:]:
            if any(c and 'avec FUP' in c for c in row):
                fup = True
                continue
            price = next((re.sub(r'\s', '', c) for c in row[:vol[0]]
                          if c and re.fullmatch(r'\d[\d\s]*', c.strip())), None)
            if price:
                offers.append({'prix': int(price), 'fup': fup})
            if not offers:
                continue
            for i, c in enumerate(row):
                if not c or i < vol[0]:
                    continue
                _, op, field = [x for x in cols if x[0] <= i][-1]
                d = offers[-1].setdefault(op, {})
                # cellule sur plusieurs lignes : la suite arrive sur une rangee sans prix
                d[field] = (d[field] + ' ' + c) if field in d else c
        for o in offers:
            for op in ops:
                if op in o:
                    o[op] = {k: clean_offer(v) for k, v in o[op].items()}
        return offers
    return []


def main():
    ftth = ac.load_reports(INDEX_URL, OBS_DIR, min_upload_year=2026, exclude=('mobile',))
    mobile = ac.load_reports(INDEX_URL, OBS_DIR, min_upload_year=2026, exclude=('ftth',))
    mobile += [r for r in ac.load_reports(MOBILE_INDEX_URL, OBS_DIR, min_upload_year=2026,
                                          exclude=('observatoire-telephonie',))
               if 'tarif' in ac.norm(os.path.basename(r[1]))]
    mobile.sort(key=lambda r: ac.qkey(r[0]), reverse=True)

    ftth_period, ftth_path = ftth[-1]
    store = {'ftth': extract_ftth(ftth_path), 'mobile': [], 'meta': ac.read_json(OUT_JSON).get('meta', {})}
    for period, path in mobile:  # du plus recent au plus ancien
        offers = extract_mobile(path)
        print(f"  Mobile {period} {os.path.basename(path)} : {len(offers)} forfaits")
        if offers:
            store['mobile'] = offers
            store['meta'].update(mobile_source=os.path.basename(path), mobile_periode=period)
            break
    print(f"  FTTH {ftth_period} {os.path.basename(ftth_path)}")
    store['meta'].update(
        ftth_source=os.path.basename(ftth_path), ftth_periode=ftth_period,
        dernier_rapport=max((ftth_period, mobile[0][0]), key=ac.qkey),
        derniere_verification=time.strftime('%Y-%m-%d'),
        note="Cliche instantane du dernier catalogue publie (pas une serie temporelle). Volumes "
             "repris tels qu'ecrits par l'ARCEP. SBIN = marque Celtiis.")
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"Ecrit : {OUT_JSON}")


if __name__ == '__main__':
    main()
