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
HISTORY_FROM = 2025  # annee de mise en ligne des plus anciens rapports conserves en historique

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


MONTH_Q = {'janvier': 1, 'fevrier': 1, 'mars': 1, 'avril': 2, 'mai': 2, 'juin': 2, 'juillet': 3,
           'aout': 3, 'septembre': 3, 'octobre': 4, 'novembre': 4, 'decembre': 4}
SOURCE_RE = re.compile(r'donnees operateurs,?\s*(' + '|'.join(MONTH_Q) + r')\s*(20\d\d)')
VOLUME_RE = re.compile(r'(\d[\d\s]*(?:,\d+)?)\s*(Go|Mo|MB)?', re.I)


def data_period(pdf_path, cover_period):
    """Periode reelle des offres : la ligne "Source : (Donnees Operateurs, mars 2026)".
    L'ARCEP republie parfois le catalogue d'un trimestre precedent sous une nouvelle
    couverture (ex. tableau de bord "au 30 juin 2026" contenant les offres de mars)."""
    with pdfplumber.open(pdf_path) as pdf:
        text = ac.norm(' '.join(page.extract_text() or '' for page in pdf.pages))
    found = SOURCE_RE.findall(text)
    if not found:
        return cover_period, None
    month, year = found[-1]
    return f"T{MONTH_Q[month]}_{year}", f"{month} {year}"


def volume_mo(volume):
    """Volume en Mo (1 Go = 1024 Mo, convention ARCEP : 4 Go = 4096 Mo)."""
    m = VOLUME_RE.match(volume)
    if not m:
        return None
    n = float(re.sub(r'\s', '', m.group(1)).replace(',', '.'))
    return round(n * 1024 if (m.group(2) or '').lower() == 'go' else n, 2)


def table_rows(table):
    """Lignes d'un tableau pdfplumber : [(centre x, x gauche, texte)] par cellule non vide."""
    for row, texts in zip(table.rows, table.extract()):
        yield [((c[0] + c[2]) / 2, c[0], s.strip()) for c, s in zip(row.cells, texts) if c and s and s.strip()]


def extract_mobile(pdf_path):
    """[{'prix': int, 'fup': bool, 'mtn'|'moov'|'sbin': {'volume', 'validite', 'mo'}}]
    Deux formats : 2026 (volumes avec unite, sections "sans FUP" / "avec FUP") et 2025
    (en-tete "Volume (MB)", chiffres seuls, section "Forfaits Internet Illimites", et suite
    du tableau sur la page suivante, sans en-tete). Colonnes reperees par leur abscisse."""
    ops = ('mtn', 'moov', 'sbin')
    cols, price_max, head_page, in_mb, offers, fup = None, None, None, False, [], False
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.find_tables():
                rows = list(table_rows(table))
                h = next((k for k, r in enumerate(rows) if any(s == 'Forfait (FCFA)' for _, _, s in r)), None)
                if h is not None:
                    if cols:
                        continue  # un seul catalogue Internet par rapport
                    vol = [x for _, x, s in rows[h] if s.startswith('Volume')]
                    val = [x for _, x, s in rows[h] if s.startswith('Valid')]
                    names = [s.lower() for r in rows[:h] for _, _, s in r if s in ('MTN', 'MOOV', 'SBIN')]
                    if len(vol) != 3 or len(val) != 3 or names != list(ops):
                        continue
                    in_mb = any('MB' in s for _, _, s in rows[h])
                    cols = sorted([(x, op, 'volume') for x, op in zip(vol, ops)] +
                                  [(x, op, 'validite') for x, op in zip(val, ops)])
                    price_max, rows, head_page = vol[0], rows[h + 1:], page.page_number
                elif not cols or page.page_number == head_page:
                    continue  # la suite du catalogue est sur une page suivante ; le reste est parasite
                for r in rows:
                    line = ac.norm(' '.join(s for _, _, s in r))
                    if 'arcep.bj' in line or line.startswith(('source', 'tel :')):
                        continue  # pied de page
                    if 'avec fup' in line or 'internet illimites' in line:
                        fup = True
                        continue
                    price = next((re.sub(r'\s', '', s) for c, _, s in r
                                  if c < price_max and re.fullmatch(r'\d[\d\s]*', s)), None)
                    if price:
                        offers.append({'prix': int(price), 'fup': fup})
                    if not offers:
                        continue
                    for c, _, s in r:
                        if c < price_max:
                            continue
                        _, op, field = [k for k in cols if k[0] <= c][-1]
                        d = offers[-1].setdefault(op, {})
                        # cellule sur plusieurs lignes : la suite arrive sur une rangee sans prix
                        d[field] = (d[field] + ' ' + s) if field in d else s
    for o in offers:
        for op in ops:
            if op in o:
                d = {k: clean_offer(v.replace('**', '')) for k, v in o[op].items()}
                if in_mb and re.fullmatch(r'[\d\s]+', d.get('volume', '')):
                    d['volume'] = re.sub(r'\s', '', d['volume']) + ' Mo'
                d['mo'] = volume_mo(d.get('volume', ''))
                if d['mo']:
                    o[op] = d
                else:
                    del o[op]  # case sans volume (ex. "30 jours" seul, offre portee par la ligne suivante)
    return [o for o in offers if any(op in o for op in ops)]


def same_catalog(new, known):
    """Vrai si le catalogue n'apporte rien : identique, ou simple extrait d'un catalogue deja vu
    (table coupee sur deux pages dans un rapport qui republie le meme trimestre)."""
    return all(o in known for o in new)


def main():
    ftth = ac.load_reports(INDEX_URL, OBS_DIR, min_upload_year=HISTORY_FROM, exclude=('mobile',))
    mobile = ac.load_reports(INDEX_URL, OBS_DIR, min_upload_year=HISTORY_FROM, exclude=('ftth', 'fixe'))
    mobile += [r for r in ac.load_reports(MOBILE_INDEX_URL, OBS_DIR, min_upload_year=HISTORY_FROM,
                                          exclude=('telephonie', 'annuel'))
               if 'tarif' in ac.norm(os.path.basename(r[1]))]
    old = ac.read_json(OUT_JSON)

    # historique mobile : un catalogue par periode reelle des donnees, doublons ecartes
    hist_mobile, labels, confirmed = {}, {}, {}
    for period, path in sorted(mobile, key=lambda r: ac.qkey(r[0])):
        offers = extract_mobile(path)
        if not offers:
            continue
        dp, label = data_period(path, period)
        print(f"  Mobile {period} (donnees {label or dp}) {os.path.basename(path)} : {len(offers)} forfaits")
        # meme catalogue deja vu, ou republication partielle de la meme periode : on garde le plus complet
        known = next((k for k, o in hist_mobile.items() if same_catalog(offers, o)), None)
        if known or len(hist_mobile.get(dp, [])) >= len(offers):
            if known and ac.qkey(dp) > ac.qkey(known):
                confirmed[known] = label or dp  # catalogue inchange, revu a cette date
            continue
        hist_mobile[dp] = offers
        labels[dp] = label
    hist_ftth = {}
    for period, path in sorted(ftth, key=lambda r: ac.qkey(r[0])):
        # redevances seules : les frais d'installation en promotion ("20 000 / 10 000*") des
        # anciens rapports ne sont pas lus de facon fiable
        r = extract_ftth(path)['redevances']
        if r['partage'] and (not hist_ftth or r != hist_ftth[max(hist_ftth, key=ac.qkey)]):
            hist_ftth[period] = r
    hist_mobile = ac.keep_missing_quarters(hist_mobile, old.get('historique_mobile'))
    hist_ftth = ac.keep_missing_quarters(hist_ftth, old.get('historique_ftth'))

    m_period = max(hist_mobile, key=ac.qkey)
    f_period, f_path = ftth[-1]
    store = {
        'ftth': extract_ftth(f_path),
        'mobile': hist_mobile[m_period],
        'historique_mobile': hist_mobile,
        'historique_ftth': hist_ftth,
        'meta': old.get('meta', {}),
    }
    print(f"  FTTH {f_period} {os.path.basename(f_path)} ; historique mobile {list(hist_mobile)}, "
          f"fibre {list(hist_ftth)}")
    store['meta'].update(
        ftth_source=os.path.basename(f_path), ftth_periode=f_period, mobile_periode=m_period,
        mobile_source=next(os.path.basename(p) for q, p in mobile
                           if data_period(p, q)[0] == m_period and extract_mobile(p)),
        inchange_jusqu_a={**old.get('meta', {}).get('inchange_jusqu_a', {}), **confirmed},
        libelles_periodes={k: v for k, v in {**old.get('meta', {}).get('libelles_periodes', {}), **labels}.items() if v},
        dernier_rapport=max((f_period, m_period), key=ac.qkey),
        derniere_verification=time.strftime('%Y-%m-%d'))
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    print(f"Ecrit : {OUT_JSON}")


if __name__ == '__main__':
    main()
