"""
Regenerateur du site -- relit les 10 fichiers JSON de vitrine/data/ et resplice le
bloc `const NOM = {...};` correspondant dans vitrine/site/index.html.

Chaque bloc est une unique ligne JS ("const NOM = <json compact>;"). On preserve
l'indentation/espacement exacts deja presents autour du "=" et du ";" de fin de
ligne, on ne remplace que le JSON au milieu -- pour ne produire aucun diff quand
les donnees n'ont pas change.

Note volontairement absente de cette liste : `map_geometry.json` -> MAP_GEOMETRY
(geometrie SVG figee, generee une seule fois par build_map_geometry.py, jamais
regeneree par ce script).

Usage : python build_site.py [--check]
  --check : n'ecrit rien, sort avec un code non-nul si index.html devrait changer
            (utile en CI pour decider s'il faut committer + deployer ou non).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))
SITE_HTML = os.path.normpath(os.path.join(HERE, "..", "site", "index.html"))

# fichier JSON -> nom de la const JS correspondante dans index.html
JSON_TO_CONST = {
    'qos_national.json': 'QOS_DATA',
    'qos_regional.json': 'QOS_REGIONAL',
    'market_data.json': 'MARKET_DATA',
    'sfm_data.json': 'SFM_DATA',
    'complaints_data.json': 'COMPLAINTS_DATA',
    'postal_data.json': 'POSTAL_DATA',
    'internet_data.json': 'INTERNET_DATA',
    'fixe_data.json': 'FIXE_DATA',
    'tarifs_data.json': 'TARIFS_DATA',
    'revenus_arcep_data.json': 'REVENUS_ARCEP_DATA',
}


def splice_const(html_text, const_name, data):
    """Remplace le JSON de `const NAME = <json>;` en preservant le prefixe/suffixe
    exacts de la ligne existante. Leve ValueError si la const est introuvable."""
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    pattern = re.compile(
        r'^([ \t]*const[ \t]+' + re.escape(const_name) + r'[ \t]*=[ \t]*).+?(;[ \t]*)$',
        re.MULTILINE,
    )
    new_text, n = pattern.subn(lambda m: m.group(1) + payload + m.group(2), html_text, count=1)
    if n == 0:
        raise ValueError(f"const {const_name} introuvable dans {SITE_HTML}")
    return new_text


def main():
    check_only = '--check' in sys.argv

    with open(SITE_HTML, encoding='utf-8') as f:
        html = f.read()
    original_html = html

    changed_consts = []
    for fname, const_name in JSON_TO_CONST.items():
        path = os.path.join(DATA_DIR, fname)
        if not os.path.exists(path):
            print(f"  ! {fname} absent, {const_name} inchange")
            continue
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        new_html = splice_const(html, const_name, data)
        if new_html != html:
            changed_consts.append(const_name)
        html = new_html

    if html == original_html:
        print("Aucun changement -- index.html deja a jour.")
        sys.exit(0)

    print(f"Consts modifiees : {', '.join(changed_consts)}")
    if check_only:
        print("(--check : rien ecrit, index.html devrait changer)")
        sys.exit(1)

    with open(SITE_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Ecrit : {SITE_HTML}")


if __name__ == '__main__':
    main()
