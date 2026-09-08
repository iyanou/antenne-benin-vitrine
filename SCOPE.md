# Vitrine Telecom Data Intelligence — Benin
## Document de cadrage (scope) — a valider avant toute implementation

Cree le 2026-09-07. Complement de `../STRATEGIE_LINKEDIN_PILIERS.md` et
`../PLAN_CONTENU_LINKEDIN_SEPT-DEC2026.md`. Perimetre retenu avec l'utilisateur :
**uniquement le Benin** (le comparatif regional Benin/Togo, pilier B, est ecarte pour
l'instant).

---

## 1. Objectif

Une page web publique, permanente, a lien stable — pas une serie d'images qui disparaissent
dans un fil LinkedIn. Elle sert de preuve de capacite (pas seulement d'analyse) et de point
de reference que les decideurs beninois peuvent consulter n'importe quand. Referencee dans
la section "Featured" du profil LinkedIn et citee dans les posts.

## 2. Perimetre retenu

| Section | Retenue ? | Nature des donnees |
|---|---|---|
| A. QoS Benin — vivant (national + regional) | **Oui** | Donnees ARCEP (page nationale + API Atlas) |
| B. Comparaison regionale (Benin/Togo) | **Non, pour l'instant** | Ecarte a la demande de l'utilisateur |
| C. Bibliotheque "comprendre la fraude" | **Retiree le 2026-09-07** | Etait en ligne (3 cartes), retiree a la demande de l'utilisateur -- la vitrine se concentre sur QoS + Marche |
| D. Marche & Regulation | **Oui** | Rapports trimestriels ARCEP (Observatoire, parts de marche, revenus) |
| E. Qui es-tu | **Oui** | Contenu statique, redige une fois |
| F. Analyses & Articles | **Retire** | Ajoutee le 2026-09-07, retiree le meme jour a la demande de l'utilisateur |

---

## 3. Contrainte de donnees decouverte (critique — a lire avant de dimensionner la section A)

Verification faite directement sur `arcep.bj` le 2026-09-07 (WebFetch) :

- La page `arcep.bj/performances-mtn-et-moov/` affiche des **tableaux HTML reels**, mais
  **uniquement la derniere semaine publiee**. Verifie : elle montre actuellement le 22-28
  aout 2026 (la meme semaine que celle deja traitee localement).
- Chaque semaine a son **propre article d'annonce** (ex. "...periode-du-15-au-21-aout-2026/"),
  mais ces articles **ne contiennent pas les chiffres** — juste un texte de synthese qui
  renvoie vers la meme page "Qualite de service" ci-dessus. Verifie sur l'article de la
  semaine du 15-21 aout 2026 : aucun tableau, uniquement une phrase invitant a cliquer vers
  la page qui, elle, ne montre que la semaine courante.
- Consequence : **il n'existe aucun moyen de recuperer par scraping les chiffres exacts
  d'une semaine passee une fois qu'elle a ete remplacee par la semaine suivante sur cette
  page.** L'archive PDF (`qos-archives/`) existe mais couvre un format plus ancien
  (2023-2024), pas le format hebdomadaire 2026 actuel.
- Confirme l'hypothese de l'utilisateur : le scraping ne donnera jamais qu'"une semaine a la
  fois", celle qui est active au moment ou le scraper tourne.

### Implication directe sur le plan

- **Historique (mars, mai, juin, aout 2026)** : deja traite localement dans
  `arcep/data/qos/{mois}/` — sert de **seed** (donnees de depart) pour la section A. Pas
  besoin de scraper, cette donnee existe deja.
- **Trous connus, irrecuperables par scraping** : janvier, fevrier, juillet 2026 (deja
  documentes comme perdus dans `arcep/data/qos/README.txt`), et **01-07, 08-14, 15-21 aout
  2026** — trois semaines dont l'annonce existe sur le site mais dont les chiffres exacts ne
  sont plus accessibles (la page a deja avance sur la semaine suivante). **Question ouverte
  pour l'utilisateur** : as-tu par hasard sauvegarde ces 3 semaines d'aout quelque part au
  moment de leur publication (capture d'ecran, export) ? Si non, ces semaines resteront des
  trous dans l'historique de la vitrine, comme janvier/fevrier/juillet.
- **A partir de maintenant** : le scraper doit tourner **au moins une fois par semaine**,
  idealement deux fois (ex. mardi et vendredi) pour reduire le risque de manquer une semaine
  si l'ARCEP change son jour de publication habituel. Chaque semaine manquee est
  definitivement perdue, pas de rattrapage possible.

### 3bis. API Atlas de couverture (`atlas.arcep.bj`) — verifiee le 2026-09-07

Decouverte en cours de route : un second outil ARCEP, recemment mis en ligne (confirme par
l'utilisateur), avec une **vraie API REST JSON publique, sans authentification**
(documentation Swagger a `atlas.arcep.bj/api/documentation`). Teste directement (PowerShell,
requetes GET) :

- **Couverture administrative complete** : `/api/departments` (12), `/api/cities` (77
  communes), `/api/districts` (546 arrondissements) — toute la hierarchie du Benin, avec
  contours geographiques (GeoJSON).
- **Donnees QoS par zone** : `/api/qos-data/{department|city|district}/{id}` — teste sur
  plusieurs departements (1, 5, 10, 12), deux communes et un arrondissement : donnees reelles
  et coherentes a chaque niveau, avec une vraie variance locale (ex. arrondissement 1 :
  succes voix 2G Celtiis a 89,9%, tres en dessous de la moyenne nationale — invisible dans
  l'agregat national).
- **Nuance importante — ce n'est PAS la meme famille de donnees que la page nationale
  hebdomadaire** : chaque enregistrement porte son propre `qos_day`, et ce champ varie
  enormement :
  - **Celtiis** : `qos_day` proche de la date du jour a chaque appel, sur toutes les zones
    testees — refraichissement quasi continu.
  - **MTN et Moov** : `qos_day` tres irregulier selon la zone (observe entre fevrier 2025 et
    mai 2026 selon le departement) — probablement la date de la **derniere campagne d'audit
    terrain** de l'ARCEP pour cette zone/cet operateur, pas un cycle hebdomadaire.
  - **`coverage_day`** (couverture geographique/population) : fige a **octobre 2023** sur
    tous les departements testes — carte de couverture d'une campagne ponctuelle, non
    reactualisee depuis.
- **Consequence** : cette source vient probablement de l'audit de couverture/QoS/conformite
  lance par l'ARCEP (distinct du suivi hebdomadaire continu). On l'affichera avec **la date
  de derniere mesure toujours visible**, jamais comme un chiffre "a jour cette semaine". Nos
  propres snapshots reguliers (meme mensuels suffiraient ici, vu la cadence d'actualisation
  observee) deviennent la seule facon de detecter *quand* une zone est reauditee et de
  construire une historique que l'ARCEP elle-meme ne conserve pas.
- **Prudence d'usage** : documentation Swagger etiquetee "pre-prod", decouverte par recherche
  web (pas liee depuis le site officiel), aucune limite de debit visible. L'utilisateur a
  confirme qu'il s'agit d'un outil recemment mis en ligne intentionnellement par le
  regulateur — donc pas une fuite, mais on continue d'interroger poliment (appels espaces,
  pas de martelage) puisque c'est une surface non documentee officiellement qui pourrait
  changer sans preavis.

---

## 4. Detail par section

### A. QoS Benin — vivant (national + regional)

**Deux sous-sources, a ne pas confondre dans l'affichage** :

**A1 — National, hebdomadaire** (page `performances-mtn-et-moov`)
- Indicateurs : succes voix (seuil 99%), blocage voix (seuil 1%), debit DL/UL 3G, DL/UL 4G
- Operateurs : MTN, Moov Africa, Celtiis — granularite quotidienne, agregee par semaine ARCEP

**A2 — Regional, par campagne d'audit** (API Atlas, voir section 3bis)
- Memes 3 operateurs, indicateurs proches (voix/SMS 2G/3G, debit 3G/4G) + couverture
  geographique/population
- Granularite geographique : departement (12) / commune (77) / arrondissement (546)
- Fraicheur variable par operateur et par zone — **toujours afficher la date de la mesure**

**Fonctionnalites** :
1. Vue "derniere semaine disponible" (A1) — tableau/graphique des 3 operateurs, tous
   indicateurs, avec badge de conformite (vert/rouge) par rapport au seuil
2. Historique interactif (A1) — selecteur indicateur + periode (mois/trimestre/annee),
   graphique qui se met a jour en direct (zoom, survol pour voir la valeur exacte par jour)
3. Heatmap de conformite globale (A1) — portage interactif de ce qui existe deja en statique
   dans `arcep/graphs/qos/analyses/30_heatmap_conformite.png`
4. Frise chronologique des incidents (A1) — detection automatique des jours ou un operateur
   passe sous le seuil (ex. le 26/08 deja identifie), affiches comme des marqueurs sur la
   frise, avec le chiffre exact au survol
5. **Carte interactive de la QoS par commune (A2)** — carte du Benin coloree par indicateur
   choisi (succes voix, debit, etc.), filtrable par operateur/technologie, avec la date de
   derniere mesure visible au survol de chaque commune
6. **Recherche "ma commune" (A2)** — barre de recherche, l'utilisateur tape sa ville/commune
   et voit directement la derniere QoS connue pour sa zone, tous operateurs
7. **Carte de "fraicheur des donnees" (A2)** — visualisation des zones auditees recemment vs
   depuis longtemps ; contenu unique que personne d'autre n'assemble puisqu'il faut suivre le
   `qos_day` de chaque zone dans le temps

**Cadence de mise a jour** : A1 scrapee 2x/semaine (voir section 3) ; A2 interrogee a une
cadence plus espacee (mensuelle suffit largement vu la vitesse d'actualisation observee),
plus le seed initial a partir des CSV existants (mars, mai, juin, aout) pour A1.

**Prive/expose** : aucune donnee client ou confidentielle ici — tout est deja public (ARCEP).

### C. Bibliotheque "Comprendre la fraude telecom"

**Contenu** : une carte par typologie deja traitee en post LinkedIn (SIMBox pour commencer,
puis CLI spoofing, Wangiri, fraude Mobile Money au fil du calendrier de contenu).

**Par carte** :
- Titre de la typologie
- Le schema explicatif produit pour le post (image)
- Un resume court (2-3 phrases, meme registre "grand public" que les posts)
- Date + lien vers le post LinkedIn original

**Mise a jour** : manuelle, a chaque nouveau post de ce pilier — pas de scraping, le contenu
est produit par nous, pas recupere depuis une source externe.

### D. Marche & Regulation

**Donnees couvertes** : parts de marche par operateur, revenus sectoriels, indicateurs "en
chiffres" publies par l'ARCEP dans son Observatoire trimestriel.

**Source confirmee** (verification precedente) : pages d'index stables
(`/rapports/`, `/le-marche-des-communications-electroniques-et-de-la-poste-en-chiffres/`)
qui listent des PDF a des URLs stables (`arcep.bj/wp-content/uploads/[annee]/[mois]/...pdf`).
Pas de tableau HTML directement exploitable — **il faut extraire le texte/les tableaux du
PDF** (bibliotheque type pdfplumber).

**Consequence technique** : moins fiable a 100% automatiquement que la section A. Prevoir une
etape de verification humaine (rapide) apres chaque extraction, avant que le chiffre
n'apparaisse sur la page. Cadence trimestrielle (rythme de publication de l'Observatoire),
donc peu de volume a verifier a chaque fois.

**Fonctionnalites** :
1. Tableau des parts de marche par operateur, mis a jour a chaque nouvel Observatoire detecte
2. Chiffres cles du marche (CA sectoriel, redevances recouvrees par l'ARCEP, nombre
   d'abonnes/SIM) — repris des memes rapports
3. Detection automatique de nouveaux rapports publies (scan periodique de la page d'index),
   avec alerte a l'utilisateur (pas de publication automatique) pour verification avant mise
   en ligne du nouveau chiffre

### E. Qui es-tu

**Contenu statique** : bio courte (Telecom Data Engineer, Revenue Assurance, fraude,
formateur Elastic certifie), lien LinkedIn, lien vers les formations Udemy, mention du fait
que cette page est maintenue et mise a jour activement (renforce l'effet "preuve de
capacite"). Pas de proposition commerciale explicite (ca reste reserve a l'outreach prive,
voir `../PLAN_ACTION_NETWORKING.md`).

**Mise a jour** : ponctuelle, pas de cadence recurrente.

### F. Analyses & Articles (nouveau, ajoute le 2026-09-07)

**Principe** : chaque post LinkedIn a une limite de longueur et de nuance. La vitrine peut
heberger la **version longue** — plus de donnees, plus de contexte, plus de graphiques — et
le post LinkedIn devient l'accroche qui renvoie vers "l'analyse complete" sur la vitrine.

**Benefices** :
- Contenu indexable/retrouvable (LinkedIn est mauvais pour retrouver un vieux post ; une
  page web est cherchable, partageable, citable)
- Construit une bibliotheque de reference qui grossit avec le temps — chaque nouvel article
  renforce les precedents plutot que de les remplacer
- Permet d'aller plus loin que le format LinkedIn sur les sujets qui le meritent (ex. le
  post capstone du 19/11 post-forum, voir `PLAN_CONTENU_LINKEDIN_SEPT-DEC2026.md`)

**Contenu** : un article par analyse significative (pas systematiquement a chaque post) —
typiquement les posts QoS mensuels/trimestriels, les posts "capstone", et toute analyse
transversale (ex. comparaison heatmap conformite). Format : titre, date, texte, graphiques
integres (ceux deja produits pour LinkedIn), lien vers le post LinkedIn d'origine.

**Mise a jour** : manuelle, au rythme du calendrier de contenu — pas de scraping.

---

## 5. Architecture technique (revisee le 2026-09-07 — voir correction ci-dessous)

**Correction critique** : la capacite `db` (base de donnees live attachee a un Artifact)
rend la page **reservee aux membres signes de l'organisation du proprietaire** — elle ne peut
pas etre partagee publiquement (confirme par la documentation technique du contrat 0.2.41).
Ca contredit frontalement l'objectif n°1 de la vitrine (section 1) : un lien que n'importe
quel decideur beninois peut consulter sans compte. **`db` est donc ecarte pour la page
publique.**

Architecture retenue :
- **La page** : un Artifact HTML **statique**, sans capacite `db` — donc pleinement public,
  partageable a n'importe qui, sans connexion requise. Les donnees (QoS national, regional,
  marche) sont **integrees directement dans le HTML au moment de la publication**, pas lues
  en direct depuis une base.
- **L'entrepot de donnees reel** : les fichiers locaux du projet (`vitrine/data/`,
  `arcep/data/qos/`) — deja notre pratique actuelle. Le scraper (national, regional, PDF)
  ecrit/complete ces fichiers locaux a chaque execution ; rien de plus.
- **Cadence de republication** : a chaque fois que les fichiers locaux ont de la donnee
  nouvelle et verifiee, on regenere le HTML (donnees fraiches integrees) et on republie sur
  la meme URL (le lien ne change jamais). Ce n'est pas automatique de bout en bout — la
  republication reste une action explicite (moi qui la declenche), ce qui laisse aussi la
  porte a une verification rapide avant que quoi que ce soit d'aille en public.
- **assets** (capacite separee, pas de restriction organisationnelle connue) : reste une
  option pour heberger les images des schemas de fraude (section C) si utile, a confirmer a
  l'implementation de cette section.
- **Pas de publication automatique de post LinkedIn** : inchange, le contenu editorial reste
  pilote par le calendrier de contenu.

---

## 6. Plan de mise en oeuvre (ordre propose)

1. ~~Creer le dossier de travail~~ — fait (`vitrine/`)
2. ~~Rediger ce document de cadrage~~ — fait, valide
3. ~~Construire le schema de donnees et seeder l'historique national~~ — fait
   (`vitrine/DATA_SCHEMA.md`, `vitrine/data/qos_national.json`, 24 documents, mars/mai/
   juin/aout). Correction en cours de route : pas de base `db` live (rendrait la page
   privee-organisation) — donnees integrees statiquement dans le HTML a la publication.
4. ~~Construire et publier une premiere version de la page (section A national + roadmap)~~
   — fait : https://claude.ai/code/artifact/84d4a12b-674e-4d25-85d4-8f9b17a7988f
   (`vitrine/site/index.html`). A partager depuis le menu de partage de la page pour la
   rendre visible au-dela de nous deux.
5. ~~Construire et tester une fois manuellement le scraper QoS national~~ — fait
   (`vitrine/scraper/scrape_qos_national.py`). Teste en conditions reelles le 2026-09-07 :
   recupere les 6 tables HTML (`performances-mtn-et-moov/`), fusion idempotente dans
   `qos_national.json` (ignore les semaines deja connues, ajoute uniquement les jours
   reellement nouveaux au bon document mensuel, cree un nouveau document si le mois
   n'existe pas encore). Reste manuel pour l'instant : re-integrer le JSON mis a jour dans
   `site/index.html` et republier — automatisable plus tard (etape 8).
6. ~~Ajouter le detail regional (section A2, API Atlas) a la page~~ — fait, et pousse plus
   loin que prevu : carte SVG interactive du Benin (contours reels, pas de tuiles externes),
   couleur = conformite agregee (rouge/orange/jaune/vert), vue "tous operateurs" par defaut,
   clic sur un departement = zoom anime sur ses communes (appartenance commune->departement
   deduite geometriquement, l'API ne l'expose pas), filtre de fraicheur des mesures, recherche
   "ma commune" en complement.
7. ~~Ajouter la section C (bibliotheque fraude)~~ — fait : 3 cartes (SIMBox, Wangiri/SIM
   swap, CLI spoofing), images integrees en base64. Section F (Analyses & articles) faite
   en meme temps : article complet du post capstone du 19/11.
8. Mettre en place la tache planifiee recurrente pour le scraper QoS (2x/semaine) — **reporte
   a la demande de l'utilisateur le 2026-09-07** : "rien pour l'instant", tout reste manuel
   (scraper relance a la main, republication manuelle) jusqu'a ce que le reste de la vitrine
   soit termine. A reevaluer plus tard, ne pas le faire sans redemander.
9. ~~Construire le scraper/parseur PDF pour la section D~~ — fait
   (`vitrine/scraper/scrape_market_reports.py`, `vitrine/scraper/build_map_geometry.py`
   n'est pas concerne). Detecte les rapports "Observatoire Telephonie Mobile" sur
   `arcep.bj/telephonie-mobile/`, telecharge les nouveaux PDF, extrait via pdfplumber :
   abonnements actifs par operateur + parts de marche calculees (7 trimestres, T3_2024 a
   T1_2026), trafic reseau (voix/SMS/data). Extraction verifiee manuellement (recoupee
   avec une lecture directe du PDF) -- fiable pour ce type de rapport. Section D en ligne
   sur le site : graphique parts de marche + stats trafic dernier trimestre.
   Reste a faire eventuellement : revenus sectoriels / redevances ARCEP (pas dans ce
   rapport, source differente a identifier si voulu).
10. Ajouter la section E (deja un brouillon sur la page)
11. Revue finale

**Note 2026-09-07** : la section C (bibliotheque fraude) a ete retiree du perimetre a la
demande de l'utilisateur -- la vitrine se concentre desormais sur A (QoS) + D (marche) + E.

## 9. Cartographie des rapports ARCEP (exploration du 2026-09-07)

Categories "Observatoire" trouvees sur arcep.bj, au-dela de QoS et Telephonie Mobile deja
exploitees :

| Categorie | URL | Statut | Pertinence |
|---|---|---|---|
| Services Financiers Mobiles (SFM) | `/services-financiers-mobiles/` | **Fait** (`scrape_sfm_reports.py`) | Forte -- Mobile Money, pilier existant |
| Internet | `/internet/` | **Fait** (`scrape_internet_reports.py`) | Moyenne |
| Tarifs Internet | (rapports melanges sur `/internet/`) | Ecarte (structure differente, tables de prix) | Faible-moyenne |
| Telephonie Fixe | `/telephonie-fixe/` | **Fait** (`scrape_fixe_reports.py`) | Faible (segment en declin) mais anomalie interessante (voir plus bas) |
| Postes | `/observatoire-postal/` | **Fait, extraction minimale** (`scrape_postal_reports.py`) | Faible -- seul le total des recettes postales extrait, pas le detail par operateur |
| Gestion des plaintes | `/observatoire-des-plaintes/` | **Fait** (`scrape_complaints_reports.py`) | Angle confiance consommateur |
| Rapports annuels | `/rapports/` | Non explore | Gros PDF peu structures, rendement incertain |

**Scraper SFM** (`vitrine/scraper/scrape_sfm_reports.py`) : noms de fichiers non uniformes
(pas de gabarit regex unique comme pour Telephonie Mobile) -- detection par ordre
d'apparition sur la page (l'ARCEP liste toujours du plus recent au plus ancien), pas par
nom de fichier. Extraction ciblee sur 2 tableaux fiables : comptes SFM (actifs/dormants,
parts de marche par produit, taux penetration/activite) et dnepots/retraits
(volume+valeur). Les autres types de transaction (paiements marchands, P2P, P2C,
transferts internationaux) ont une structure de cellules fusionnees plus fragile,
non extraits dans cette premiere passe -- extensible si besoin.
**Bug corrige en cours de route** : merge initial traitait les rapports du plus recent au
plus ancien, ce qui faisait ecraser les donnees les plus recentes/completes par des
versions plus anciennes sur les trimestres qui se chevauchent. Corrige (traite desormais
du plus ancien au plus recent, le rapport le plus recent gagne toujours en dernier).

**Donnee marquante extraite** : part de marche Mobile Money Celtiis Cash passee de 13,4%
(T3 2024) a 24,93% (T3 2025), MTN Mobile Money reculant de 63,97% a 51,98% -- bascule
encore plus rapide que sur le marche mobile classique. Piste de post LinkedIn potentiel.

**Scraper Internet** (`scrape_internet_reports.py`) : page `/internet/` melange en fait 3
observatoires (abonnements Internet fixe/mobile + tarifs FTTH + tarifs mobile) -- seuls les
rapports d'abonnements sont extraits, les rapports tarifaires sont correctement ignores
(structure de tableau differente). Deux bugs trouves et corriges : (1) le libelle
"Penetration Internet fixe" varie selon les rapports (avec/sans suffixe "(%)"), corrige par
detection par sous-chaine ; (2) un en-tete de tableau avec cellule fusionnee dupliquait un
trimestre (ex. "T4_2024" apparaissant deux fois), decalant l'association valeur/trimestre --
corrige par deduplication de l'en-tete. Un garde-fou automatique detecte desormais toute
paire de trimestres consecutifs avec des valeurs identiques (signal d'un decalage similaire)
et l'affiche pour verification manuelle. 15 trimestres obtenus (T2_2022 a T1_2026) pour
Internet fixe (liste d'operateurs dynamique, casse normalisee) et mobile (3 gros operateurs).

**Scraper Telephonie Fixe** (`scrape_fixe_reports.py`) : le plus simple de tous, un seul
petit tableau (parc d'abonnes + tele densite). Anomalie interessante et **confirmee
authentique** (pas un bug d'extraction, verifie sur plusieurs rapports sources) : le parc
d'abonnes bondit de 1214 (T3 2025) a 78 938 (T4 2025) puis 89 575 (T1 2026) -- x65,
probablement une reclassification methodologique (ex. integration de lignes fixes-sans-fil)
plutot qu'une vraie explosion d'usage. A creuser si on veut en tirer un post.

**Scraper Postes** (`scrape_postal_reports.py`) : categorie la plus complexe (9 pages,
nombreuses sous-tables SPU/SPNR par segment et par operateur postal) et la moins pertinente
pour le positionnement telecom/data -- extraction volontairement limitee au tableau des
recettes totales (5 trimestres, T2 2024 a T2 2025). Le detail par operateur postal (La Poste
SA, DHL, Top Chrono, Baobab Express...) n'est pas extrait dans cette premiere passe.

**Scraper Gestion des plaintes** (`vitrine/scraper/scrape_complaints_reports.py`) : meme
strategie de detection par ordre d'apparition (noms de fichiers non uniformes). Piege
rencontre et corrige : le HTML de cette page melange `href="..."` et `href= "..."`
(espace variable) -- la regex tolere desormais les deux. Deuxieme piege : une premiere
version de l'extraction produisait des valeurs incoherentes pour les trimestres 2023
(ex. "fondees"=1824 pour un total de 24) a cause de cellules fusionnees mal reconstruites
par pdfplumber sur les anciens gabarits de rapport -- **garde-fou ajoute** : rejet
automatique de tout trimestre ou fondees+infondees+classees != total. 14 trimestres
propres obtenus (T4 2022 a T1 2026) apres filtrage.

## 7. Risques et limites acceptes

- **Semaines deja perdues** : janvier, fevrier, juillet 2026 et 01-07/08-14/15-21 aout 2026 —
  aucun rattrapage possible par scraping (voir section 3). Question ouverte a l'utilisateur
  sur d'eventuelles sauvegardes manuelles de ces 3 semaines d'aout.
- **Fiabilite du parsing PDF (section D)** : necessitera une verification humaine
  occasionnelle, jamais garanti fiable a 100% automatiquement.
- **Dependance a la structure du site ARCEP** : si l'ARCEP change son gabarit de page, le
  scraper QoS cassera et devra etre corrige — a surveiller, pas un risque une fois pour
  toutes.
- **Aucune donnee client/confidentielle** : tout le contenu de la vitrine repose sur des
  donnees deja publiques (ARCEP) ou produites par nous (schemas pedagogiques) — pas de
  question de confidentialite Synaptique a gerer ici.

---

## 8. Idees de fonctionnalites par rubrique (brainstorm, a prioriser)

Reflexion libre demandee par l'utilisateur le 2026-09-07 : tout ce qu'on pourrait construire
et presenter, au-dela du perimetre deja acte plus haut. Marque par priorite : **★★★** = fort
impact, faisable des maintenant avec ce qu'on a deja ; **★★** = bon, vient une fois le socle
en place ; **★** = idee interessante, a re-visiter plus tard (demande plus de donnees ou plus
de temps).

### QoS (section A)
- ★★★ Recherche "ma commune" — barre de recherche, resultat instantane pour n'importe quelle
  ville du Benin (deja dans le detail de la section A ci-dessus)
- ★★★ Carte de "fraicheur des donnees" — quelles zones l'ARCEP a/n'a pas reauditees
  recemment ; personne d'autre n'a ca, car ca demande de suivre `qos_day` dans le temps
- ★★★ Frise des incidents nationaux (deja dans le perimetre)
- ★★ Mode comparaison — choisir 2-3 communes et les voir cote a cote sur le meme graphique
- ★★ Export CSV des donnees affichees — geste de transparence, utile pour un journaliste ou
  un chercheur qui voudrait verifier ou reutiliser
- ★★ Page "methodologie" — explique clairement ce qui est hebdomadaire (A1) vs base sur audit
  (A2), les seuils ARCEP, les sources — condition de credibilite aupres d'un public exigeant
- ★ Alertes par e-mail/notification quand un operateur repasse sous le seuil dans une zone
  suivie — demande une brique d'abonnement, pas prioritaire pour une v1

### Fraude (section C)
- ★★★ Cartes par typologie (deja dans le perimetre) : SIMBox, puis CLI spoofing, Wangiri,
  SIM swap, fraude Mobile Money, IRSF (International Revenue Share Fraud)
- ★★★ Glossaire public (CDR, IPDR, HLR/HSS, SS7, Cell-ID, TAP files...) — deja redige dans
  `../BENIN_TELECOM_DATA_INTELLIGENCE.md` annexe A, reutilisable tel quel. Bon aussi pour le
  referencement (quelqu'un qui cherche "qu'est-ce qu'un CDR" peut tomber dessus)
- ★★ Checklist interactive "avez-vous deja vecu ca ?" — reprend les signes d'alerte de chaque
  post (ex. les 3 signes du post SIMBox) sous forme de petite liste a cocher, plus engageant
  qu'un texte passif
- ★ Fil d'actualite regional — recap occasionnel des cas de fraude demanteles en Afrique de
  l'Ouest (Ghana, Cameroun, etc., memes references deja utilisees) — a curer manuellement,
  pas de source unique a scraper

### Marche, Revenus & Trafic (section D)
- ★★★ Chiffres cles du marche — CA sectoriel, redevances ARCEP recouvrees pour l'Etat (le
  66,1 Mds FCFA 2024 deja cite), nombre d'abonnes/SIM, comptes Mobile Money actifs — deja
  compiles dans `../BENIN_TELECOM_DATA_INTELLIGENCE.md`, sert de socle initial avant meme le
  premier scraping PDF
- ★★★ Parts de marche par operateur (evolution une fois plusieurs trimestres accumules)
- ★★ Frise des evenements reglementaires — passage a 10 chiffres (nov. 2024), nouvelle taxe
  Mobile Money (janv. 2025), etc. — contextualise les chiffres, alimentee manuellement
- ★★ Indicateurs Mobile Money dans le temps — depots, revenus SFM, comptes actifs
- ★ Trafic agrege voix/data (minutes, Go consommes) — seulement si l'Observatoire le publie
  sous une forme exploitable ; a confirmer au moment du parsing PDF

### Analyses & Articles (section F)
- ★★★ Version longue des posts marquants (capstone du 19/11, bilan annuel du 29/12 — voir
  `PLAN_CONTENU_LINKEDIN_SEPT-DEC2026.md`)
- ★★ Bibliotheque chronologique de toutes les analyses, cherchable/filtrable par pilier
- ★ Une "note technique" occasionnelle plus poussee (ex. comment fonctionne un scraper QoS,
  pourquoi telle donnee est fiable ou non) — demontre la capacite d'ingenierie elle-meme,
  pas seulement le resultat

### Transversal (toutes sections)
- ★★★ Bandeau clair "source : ARCEP Benin, donnees publiques" partout — credibilite et
  transparence, jamais presenter une donnee sans sa source et sa date
- ★★ Mode sombre/clair (deja une reflexion menee sur les graphes QoS eux-memes)
- ★ Compteur de visites / statistiques de frequentation — utile pour toi seul (savoir si la
  vitrine est vue), pas expose publiquement

---

## Question ouverte — resolue le 2026-09-07

Confirme par l'utilisateur : pas de sauvegarde des semaines du 01-07, 08-14, 15-21 aout 2026.
Ces 3 semaines sont donc des trous definitifs dans l'historique, au meme titre que janvier,
fevrier et juillet 2026 (voir section 3).

---

## Refonte de la presentation — terminee le 2026-09-08

Les 6 categories de la section D (Marche & regulation) sont maintenant toutes scrapees ET
affichees sur le site (avant : seulement Mobile/SFM/Plaintes affiches, Internet/Fixe/Postes
extraits mais non integres).

Changements :
- Section Marche restructuree en onglets (Telephonie Mobile, Internet, Mobile Money,
  Telephonie Fixe, Plaintes, Postes) au lieu d'un empilement vertical des 3 anciens blocs
- 3 nouvelles fonctions de rendu : renderInternet (mobile 3 operateurs + fixe total/FAI),
  renderFixe (parc abonnes, avec detection automatique de la rupture de serie T3->T4 2025,
  x65 sur le parc — signalee sur le site sans en inventer la cause, l'ARCEP ne la precise pas),
  renderPostal (recettes totales + repartition par segment, extraction minimale volontaire —
  voir note dans postal_data.json)
- Hero refait : 6 tuiles KPI calculees dynamiquement en JS a partir des donnees reelles
  (avant : uniquement 3 tuiles, dont 2 en texte statique jamais mises a jour) — periode du
  dernier releve QoS, conformite voix, couverture regionale, plus forte variation de parts
  de marche, comptes Mobile Money actifs, plaintes traitees
- Section "Qui suis-je" reconstruite en bio-card (avatar, titre, tags de competences, lien
  LinkedIn reel) au lieu d'un paragraphe brut
- Feuille de route mise a jour : QoS et Marche passent tous les deux au statut "En ligne"

Site republie sur la meme URL : https://claude.ai/code/artifact/84d4a12b-674e-4d25-85d4-8f9b17a7988f
(toujours prive — a partager par l'utilisateur via le menu de partage de la page).

Reste hors perimetre (voir listes d'idees ci-dessus) : revenus sectoriels/redevances,
detail postal par operateur, tarifs Internet/FTTH, section F "Analyses & articles" (retiree
sur demande explicite de l'utilisateur).

---

## Titres/coherence — 2026-09-08

- Nameplate "Antenne Bénin" unifie en un seul bloc de texte (au lieu de "A"/"Antenne"/"Bénin"
  visuellement disjoints, "Bénin" traite comme un tag separe)
- QoS national + QoS regional fusionnes en une seule section/nav "QoS" (Regions n'est qu'un
  detail de la QoS, pas un sujet a part) — nav passe de 5 a 4 items
- Nav "Marche" -> "Marche & regulation" (aligne sur le h2, la section couvre aussi les
  Plaintes qui ne sont pas du "marche" a proprement parler)
- Bascule clair/sombre ajoutee (bouton icone soleil/lune dans le header, localStorage,
  pas de flash au chargement)
- Site rendu responsive mobile : nav horizontale scrollable au lieu de disparaitre <720px,
  champ recherche commune corrige (min-width fixe -> overflow possible sur petits ecrans)

## Trois derniers trous de donnees combles — 2026-09-08

Les 3 points identifies comme "reste a faire" ont ete traites :

1. **Detail postal par operateur** (`scrape_postal_reports.py` etendu) : parts de marche
   La Poste/DHL/Top Chrono/Baobab Express/Cars ATT/Africa Global Logistics sur les segments
   Courrier Express et Colis, en volume ET en valeur, T1 2023 -> T2 2025. Extraction par
   position texte (pas index de colonne brut, peu fiable sur ce PDF) avec guard de coherence
   (somme des parts par trimestre). Affiche en graphe sous l'onglet Postes.

2. **Tarifs Internet/FTTH** (nouveau `scrape_tarifs_internet.py`) : cliche instantane (pas une
   serie temporelle, ce sont des catalogues d'offres) du dernier rapport ARCEP disponible.
   FTTH : frais d'installation + redevances mensuelles par palier de debit (SBIN/Isocel/GVA
   Benin), extraction par position x/y des mots (le tableau brut pdfplumber melangeait les
   colonnes operateur d'une ligne a l'autre). Mobile : comparaison au palier 5000 FCFA "avec
   FUP", seul palier ou MTN/Moov/SBIN ont tous une offre. Affiche sous l'onglet Internet.

3. **Revenus sectoriels/redevances** (nouveau `scrape_revenus_arcep.py`) : rapports annuels
   d'activites ARCEP 2022-2025, section "Ressources financieres". Deux chiffres distincts —
   ressources propres de l'ARCEP (budget de fonctionnement du regulateur) et redevances
   recouvrees pour le compte de l'Etat (absent avant 2023, pas encore publie pour 2025).
   Confirme au passage la source exacte du chiffre "66,1 Mds FCFA" deja cite dans
   `BENIN_TELECOM_DATA_INTELLIGENCE.md` (66 129 397 493 FCFA exactement, rapport 2024).
   Nouvel onglet "Regulateur" dans la section Marche.

Site passe de 6 a 7 onglets dans la section Marche & regulation. Republie sur le meme lien.

---

## Trois idees de la liste ★★ traitees + refonte Qui suis-je — 2026-09-08

- **Export CSV** : bouton "Exporter en CSV" sur les 9 blocs de donnees principaux (QoS
  national, QoS regional, Marche mobile, Internet+tarifs, Mobile Money, Fixe, Plaintes,
  Postes, Regulateur). Implemente via la capacite `downloads` de l'artefact (declaree au
  publish) -- PAS via un lien `<a download>`/blob, qui est neutralise dans le sandbox du
  visualiseur d'artefacts. Les boutons restent caches tant que la capacite n'a pas resolu
  (evite un bouton visible qui ne ferait rien).
- **Mode comparaison communes** : nouveau bloc sous la recherche "Votre commune" --
  ajoute jusqu'a 3 communes via chips, choix d'un indicateur (succes voix 2G/3G, debit 4G),
  graphe en barres groupees par operateur. Reutilise les memes donnees QOS_REGIONAL que la
  recherche simple, aucune nouvelle extraction necessaire.
- **Page methodologie** : nouvelle section (+ lien nav) qui explique la difference de
  fraicheur entre le tableau de bord national (hebdomadaire, mesures automatisees) et le
  detail regional (audits terrain irreguliers, d'ou le filtre de fraicheur sur la carte).
- **Qui suis-je refondue** : l'ancienne bio-card (avatar "IA" en monogramme + tags) avait
  l'air d'un gabarit generique en attente d'une vraie photo -- remplacee par des tuiles
  `.stat-tile` (meme langage visuel que le reste du site : Role, Formation, Certification,
  Domaines, Contact). Pas de photo -- a ajouter plus tard si l'utilisateur en fournit une.
- **Noms sur la carte** (demande separee) : les departements affichent maintenant leur nom
  directement sur la carte (pas seulement au survol), pareil pour les communes une fois
  zoome sur un departement. Position calculee via `path.getBBox()`, pas de nouvelle donnee.

Question ouverte non traitee (l'utilisateur reflechissait a haute voix, pas de decision
prise) : faire remonter les 7 rubriques de "Marche & regulation" directement dans le menu
principal plutot que dans des onglets internes. Avis donne : je recommande de NE PAS le
faire -- un menu a 11 items (4 actuels + 7 rubriques) serait plus dur a scanner qu'un menu
a 5 items ou "Marche & regulation" est un point d'entree clair vers un sous-menu d'onglets
deja bien nomme. A revisiter si l'utilisateur insiste.

---

## Passe de verification "verifie: false" -- 2026-09-08 (bugs reels trouves et corriges)

Demande initiale : lever le flag `verifie: false` sur Postes/Internet/Fixe. En verifiant
reellement (pas juste en repassant le flag a true), 3 bugs d'extraction reels ont ete
trouves et corriges -- pas juste des artefacts cosmetiques :

1. **`scrape_internet_reports.py`** (fixe ET mobile) : un operateur recemment ajoute au
   tableau (colonnes vides, pas des tirets, sur les trimestres ou il n'existait pas
   encore) se retrouvait systematiquement aligne sur le PREMIER trimestre au lieu du
   dernier -- `zip()` sur une liste compactee ne sait pas ou sont les vrais trous.
   Corrige avec une strategie hybride : zip simple si le compte de valeurs correspond
   au nombre de trimestres (cas normal, marche quel que soit le decalage de colonne
   brut d'un rapport a l'autre), fallback sur un alignement par position d'en-tete
   sinon. Egalement corrige : un en-tete de trimestre duplique sur 2 colonnes
   consecutives (cellule fusionnee mal eclatee par pdfplumber) faisait perdre 1
   trimestre entier par decalage de longueur de liste. Et "JENY" / "JENY SAS" (meme
   FAI, renomme a partir de T1_2025) fusionnes en une seule cle.
   Resultat concret : le "FAI leader" et les stats Internet affichaient parfois le
   mauvais operateur/la mauvaise valeur pour certains trimestres (T2_2022-T3_2022,
   T4_2023-T4_2024 notamment). Toutes les incoherences (somme operateurs vs total
   publie) sont a 0 maintenant, sur 16 trimestres fixe et 15 trimestres mobile.
2. **`scrape_fixe_reports.py`** (telephonie fixe voix) : le regex de detection des
   trimestres n'acceptait pas la variante `T4 _2023` (espace avant le tiret bas) que
   certains rapports utilisent -- consequence : ces trimestres n'etaient simplement
   pas comptes, et TOUS les trimestres suivants du meme tableau se decalaient d'un cran.
   T3_2024 et T4_2024 etaient carrement absents du jeu de donnees. Corrige, serie
   complete T3_2022 -> T1_2026 sans trou. Le saut x65 T3_2025->T4_2025 est confirme
   present tel quel dans le rapport source (attribue a SBIN par l'ARCEP elle-meme).
3. **`postal_data.json`** : pas de bug trouve. Verification manuelle (recettes par
   segment = total publie, parts de marche par operateur ~100% par trimestre) +
   confirmation que les rapports anterieurs a T2_2024 ne publient simplement pas la
   section "Recettes" (pas un echec d'extraction).

Les 3 fichiers portent maintenant `verifie: true` avec une note honnete sur ce qui a
ete verifie et comment. Site republie avec les donnees corrigees sur le meme lien.

**Lecon a retenir** (deja notee mais reconfirmee ici) : le compress-puis-zip sur des
cellules de tableau pdfplumber est fragile des qu'une ligne peut avoir MOINS de valeurs
que de colonnes attendues (nouvel entrant, trimestre manquant) -- toujours prevoir soit
un garde-fou de coherence (somme vs total publie) qui aurait signale ces 2 bugs plus tot,
soit une strategie d'alignement par position en fallback des le depart plutot qu'apres coup.

---

## Deux corrections QoS regional/carte -- 2026-09-08

1. **Champs manquants dans l'Atlas de couverture** : SMS 2G/3G, debit 3G etaient deja
   scrapes mais pas affiches (CARD_FIELDS n'en montrait que 3 sur 4 deja presents).
   La couverture (%) n'existait pas du tout -- nouveau champ dans l'API Atlas
   (`2g_coverage`/`3g_coverage`/`4g_coverage`, structure `{geo:{seuil_dBm: pct}}`,
   on garde le seuil le plus permissif `"0"`). La couverture "population" par
   operateur est vide dans l'API (seulement renseignee sur les vues multi-operateurs
   combinees) -- on utilise donc la couverture geographique. `scrape_qos_regional.py`
   etendu, fiche commune/departement passe de 3 a 9 indicateurs par operateur.
2. **Etiquettes de commune illisibles une fois zoome sur un departement** : taille de
   police fixe (6.5) beaucoup trop grande pour les petites communes serrees les unes
   contre les autres -- texte deborde et se chevauche. Corrige : taille calculee a
   partir de la forme elle-meme (`path.getBBox()`), avec une deuxieme passe qui mesure
   le texte reellement rendu (`getComputedTextLength()`) et retrecit encore si ca
   deborde toujours ; en dessous d'un seuil de lisibilite, l'etiquette est simplement
   masquee plutot que de produire un fouillis illisible.

Site republie sur le meme lien.
