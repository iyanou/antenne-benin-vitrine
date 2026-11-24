"""
Outils communs aux scrapers de rapports PDF ARCEP (observatoires trimestriels).

Principe (2026-11-24) : chaque tableau d'observatoire porte exactement 5 trimestres
consecutifs, le dernier etant celui de la page de couverture ("Tableau de bord au 30
septembre 2026" -> T3_2026). On deduit donc les trimestres de la COUVERTURE, pas de
l'en-tete du tableau : l'ARCEP y laisse regulierement des coquilles (trimestre en
double, colonne oubliee, "T3-2023" au lieu de "T3-2024"...).
Une ligne qui n'a pas exactement 5 valeurs est rejetee, jamais devinee.
"""
import json
import os
import re
import time
import unicodedata
from urllib.parse import unquote

import pdfplumber
import requests

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; AntenneBeninBot/1.0)'}
PDF_LINK_RE = re.compile(r'href\s*=\s*["\'](https?://arcep\.bj/[^"\']+?\.pdf)["\']', re.I)
MONTHS = {'mars': 1, 'juin': 2, 'septembre': 3, 'decembre': 4}
COVER_RE = re.compile(r'\b(mars|juin|septembre|decembre)\s*(20\d\d)')
VALUE_RE = re.compile(r'^-?\d[\d\s.,]*%?$')
N_QUARTERS = 5


def norm(s):
    """minuscules, sans accents, espaces (et sauts de ligne) reduits a un seul."""
    s = unicodedata.normalize('NFD', str(s or ''))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s.replace('’', "'")).strip().lower()


def qkey(q):
    t, y = q.split('_')
    return int(y) * 10 + int(t[1:])


def prev_quarter(q):
    t, y = int(q[1]), int(q[3:])
    return f"T{t - 1}_{y}" if t > 1 else f"T4_{y - 1}"


def quarters_ending(q, n=N_QUARTERS):
    out = [q]
    while len(out) < n:
        out.insert(0, prev_quarter(out[0]))
    return out


def discover(index_url, min_upload_year=2024, exclude=()):
    """URLs des PDF de la page, dedoublonnees, sans les communiques."""
    r = requests.get(index_url, timeout=30, headers=HEADERS)
    r.raise_for_status()
    out = []
    for url in PDF_LINK_RE.findall(r.text):
        # l'ARCEP ecrit parfois "wpcontent" (lien mort) au lieu de "wp-content"
        url = url.replace('/wpcontent/', '/wp-content/')
        m = re.search(r'/uploads/(\d{4})/', url)
        name = norm(unquote(url.rsplit('/', 1)[-1]))
        if not m or int(m.group(1)) < min_upload_year or url in out:
            continue
        if name.startswith('commu') or any(x in name for x in exclude):
            continue
        out.append(url)
    return out


def download(url, folder):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, unquote(url.rsplit('/', 1)[-1]))
    if not os.path.exists(path):
        r = requests.get(url, timeout=90, headers=HEADERS)
        r.raise_for_status()
        if r.content[:4] != b'%PDF':
            raise ValueError(f"pas un PDF : {url}")
        with open(path, 'wb') as f:
            f.write(r.content)
        time.sleep(1)  # poli -- pas de martelage
    return path


def report_period(path):
    """'T3_2026' d'apres la page de couverture, None si introuvable."""
    with pdfplumber.open(path) as pdf:
        m = COVER_RE.search(norm(pdf.pages[0].extract_text()))
    return f"T{MONTHS[m.group(1)]}_{m.group(2)}" if m else None


def load_reports(index_url, folder, **kw):
    """[(periode, chemin)] du plus ancien au plus recent : en cas de chevauchement,
    le rapport le plus recent doit toujours ecraser les precedents."""
    out = []
    for url in discover(index_url, **kw):
        path = download(url, folder)
        period = report_period(path)
        if not period:
            raise ValueError(f"periode introuvable en couverture : {os.path.basename(path)}")
        out.append((period, path))
    if not out:
        raise ValueError(f"aucun rapport trouve sur {index_url}")
    return sorted(out, key=lambda x: qkey(x[0]))


def parse_number(s):
    s = re.sub(r'[\s%]', '', str(s))
    if s in ('-', ''):
        return None
    s = s.replace(',', '.')
    return float(s) if '.' in s else int(s)


def is_value(cell):
    c = str(cell).strip()
    return c == '-' or bool(VALUE_RE.match(c))


def iter_tables(path):
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            yield from (t for t in page.extract_tables() if t)


def split_row(row):
    """(libelle normalise, [cellules de valeur])"""
    cells = [str(c).strip() for c in row if c not in (None, '') and str(c).strip()]
    i = next((k for k, c in enumerate(cells) if is_value(c)), len(cells))
    return norm(' '.join(cells[:i])), cells[i:]


def five_values(values, variation=False):
    """Les 5 valeurs de la ligne, ou None. variation=True : une 6e colonne
    'Variation' (en %) est toleree et ignoree."""
    if variation and len(values) == N_QUARTERS + 1:
        values = values[:N_QUARTERS]
    if len(values) != N_QUARTERS or not all(is_value(v) for v in values):
        return None
    return [parse_number(v) for v in values]


def read_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def keep_missing_quarters(new, old):
    """Conserve les trimestres connus qui ne figurent plus dans les rapports en ligne."""
    for q, v in (old or {}).items():
        new.setdefault(q, v)
    return {q: new[q] for q in sorted(new, key=qkey)}
