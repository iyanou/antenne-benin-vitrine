"""
Recupere les contours geographiques (GeoJSON) des 12 departements et 77 communes
du Benin depuis l'API Atlas ARCEP, les projette en coordonnees SVG (projection
equirectangulaire simple), genere les chemins <path>, et deduit geometriquement
l'appartenance commune -> departement (l'API ne l'expose pas directement) via un
test point-dans-polygone sur le centroide de chaque commune. Calcule aussi la
boite englobante de chaque departement (pour le zoom sur ses communes).
"""
import json
import requests

BASE = "https://atlas.arcep.bj/api"
OUT  = r"D:\eraste\Products\Telecom Data Analysis\Benin\vitrine\data\map_geometry.json"

VIEWBOX_W = 640
VIEWBOX_H = 760
PAD = 12


def get(path):
    r = requests.get(f"{BASE}/{path}", timeout=20, headers={'Accept': 'application/json'})
    r.raise_for_status()
    return r.json()['data']


def all_coords(zones):
    for z in zones:
        for poly in z['area_feature']['coordinates']:
            for ring in poly:
                for lon, lat in ring:
                    yield lon, lat


def make_projector(bbox):
    lon_min, lon_max, lat_min, lat_max = bbox
    inner_w, inner_h = VIEWBOX_W - 2 * PAD, VIEWBOX_H - 2 * PAD
    scale = min(inner_w / (lon_max - lon_min), inner_h / (lat_max - lat_min))
    off_x = PAD + (inner_w - (lon_max - lon_min) * scale) / 2
    off_y = PAD + (inner_h - (lat_max - lat_min) * scale) / 2

    def project(lon, lat):
        x = off_x + (lon - lon_min) * scale
        y = off_y + (lat_max - lat) * scale
        return round(x, 2), round(y, 2)
    return project


def projected_rings(area_feature, project):
    """Renvoie la liste des polygones, chacun = liste d'anneaux, chaque anneau = liste de (x,y)."""
    polys = []
    for poly in area_feature['coordinates']:
        rings = [[project(lon, lat) for lon, lat in ring] for ring in poly]
        polys.append(rings)
    return polys


def rings_to_path(polys):
    parts = []
    for rings in polys:
        for pts in rings:
            d = 'M' + 'L'.join(f'{x},{y}' for x, y in pts) + 'Z'
            parts.append(d)
    return ' '.join(parts)


def bbox_of(polys):
    xs = [x for rings in polys for ring in rings for x, y in ring]
    ys = [y for rings in polys for ring in rings for x, y in ring]
    return min(xs), min(ys), max(xs), max(ys)


def centroid_of(polys):
    xs = [x for x, y in polys[0][0]]
    ys = [y for x, y in polys[0][0]]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def point_in_polys(x, y, polys):
    for rings in polys:
        if point_in_ring(x, y, rings[0]):
            return True
    return False


def pad_bbox(bbox, pad_ratio=0.15):
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    px, py = w * pad_ratio, h * pad_ratio
    return [round(x0 - px, 1), round(y0 - py, 1), round(w + 2 * px, 1), round(h + 2 * py, 1)]


def build():
    departments = get('departments')
    cities = get('cities')
    print(f"{len(departments)} departements, {len(cities)} communes")

    lons = [lon for lon, lat in all_coords(departments)]
    lats = [lat for lon, lat in all_coords(departments)]
    bbox = (min(lons), max(lons), min(lats), max(lats))
    project = make_projector(bbox)

    out = {'viewBox': [0, 0, VIEWBOX_W, VIEWBOX_H], 'departments': {}, 'cities': {}}

    dept_polys = {}
    for d in departments:
        polys = projected_rings(d['area_feature'], project)
        dept_polys[str(d['id'])] = polys
        out['departments'][str(d['id'])] = {
            'name': d['name'], 'path': rings_to_path(polys),
            'bbox': list(bbox_of(polys)), 'commune_ids': [],
        }

    unmatched = 0
    city_polys = {}
    for c in cities:
        polys = projected_rings(c['area_feature'], project)
        city_polys[str(c['id'])] = polys
        cx, cy = centroid_of(polys)
        dept_id = None
        for did, dpolys in dept_polys.items():
            if point_in_polys(cx, cy, dpolys):
                dept_id = did
                break
        if dept_id is None:
            unmatched += 1
        else:
            out['departments'][dept_id]['commune_ids'].append(str(c['id']))
        out['cities'][str(c['id'])] = {
            'name': c['name'], 'path': rings_to_path(polys),
            'department_id': dept_id,
        }
    print(f"Communes non rattachees a un departement (centroide hors polygone) : {unmatched}")

    # boite englobante zoomee = departement + ses communes, avec marge
    for did, dept in out['departments'].items():
        x0, y0, x1, y1 = bbox_of(dept_polys[did])
        for cid in dept['commune_ids']:
            cx0, cy0, cx1, cy1 = bbox_of(city_polys[cid])
            x0, y0, x1, y1 = min(x0, cx0), min(y0, cy0), max(x1, cx1), max(y1, cy1)
        dept['zoom_bbox'] = pad_bbox((x0, y0, x1, y1))
        del dept['bbox']

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    import os
    print(f"Ecrit : {OUT} ({os.path.getsize(OUT)} octets)")


if __name__ == '__main__':
    build()
