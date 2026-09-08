# Schema de donnees — Vitrine QoS Benin

Complement de `SCOPE.md`. **Correction du 2026-09-07** : la capacite `db` rendrait la page
reservee aux membres de l'organisation (pas de partage public possible) — voir `SCOPE.md`
section 5. Les "collections" ci-dessous ne sont donc **pas** une base Artifact live : ce sont
des **fichiers JSON locaux** (`vitrine/data/`), regeneres et integres dans le HTML statique a
chaque republication. La structure des documents reste la meme, seul le lieu de stockage
change (fichier local plutot que base `db`).

## Collection `qos_national` (section A1 — page hebdomadaire ARCEP)

Un document par indicateur x mois, meme granularite que nos CSV existants
(`arcep/data/qos/{mois}/{indicateur}_{mois}_2026.csv`) — le seed est une conversion directe,
pas de retraitement.

**doc_id** : `{indicateur}_{annee}_{mois}` (ex. `succes_voix_2026_09`)

```json
{
  "indicateur": "succes_voix",
  "label": "Succes voix 2G",
  "unite": "%",
  "seuil": 99,
  "conforme_si": "gte",
  "annee": 2026,
  "mois": 9,
  "jours": [
    {"date": "2026-09-01", "mtn": 99.37, "moov": 99.54, "celtiis": 99.39}
  ]
}
```

Indicateurs (6), avec `seuil` et `conforme_si` (`gte` = conforme si >= seuil, `lte` = conforme
si <= seuil) — repris tels quels de `arcep/scripts/generate_analyses.py` :

| indicateur | label | unite | seuil | conforme_si |
|---|---|---|---|---|
| succes_voix | Succes voix 2G | % | 99 | gte |
| blocage_voix | Blocage voix 2G | % | 1 | lte |
| dl_4g | Debit DL 4G | Mbps | 5 | gte |
| dl_3g | Debit DL 3G | kbps | 450 | gte |
| ul_4g | Debit UL 4G | Mbps | 2 | gte |
| ul_3g | Debit UL 3G | kbps | 70 | gte |

## Collection `qos_regional_latest` (section A2 — API Atlas, pas encore seedee a cette etape)

Un document par zone administrative. **doc_id** : `{type}_{id}` (ex. `department_1`,
`city_1`, `district_1`).

```json
{
  "type": "department",
  "id": 1,
  "name": "LITTORAL",
  "fetched_at": "2026-09-07",
  "operateurs": {
    "mtn":     {"2g_voice": 99.43, "3g_voice": 99.93, "4g_internet": 17.77, "qos_day": "2025-02-28"},
    "moov":    {"2g_voice": 99.60, "3g_voice": 99.63, "4g_internet": 14.68, "qos_day": "2025-11-30"},
    "celtiis": {"2g_voice": 99.56, "3g_voice": 99.91, "4g_internet": 19.97, "qos_day": "2026-09-04"}
  }
}
```

## Collection `qos_regional_history` (append seulement quand `qos_day` change)

**doc_id** : `{type}_{id}_{qos_day_operateur}` — on n'ecrit que lorsqu'on detecte un
changement par rapport a `qos_regional_latest`, pour eviter d'accumuler des doublons inutiles
a chaque poll mensuel.

## Collection `qos_meta`

Un seul document, `qos_meta/status` : derniere execution du scraper national, derniere
execution du poll regional, compteurs — pour affichage "derniere mise a jour" sur la page et
pour notre propre suivi.

---

## Etape actuelle (2026-09-07)

Seul `qos_national` est seede maintenant, a partir des CSV existants (mars, mai, juin, aout).
`qos_regional_latest`/`qos_regional_history` et les collections des sections C/D/F viendront
aux etapes suivantes du plan (`SCOPE.md`, section 6).
