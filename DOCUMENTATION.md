# Documentation — Tableau de bord météo Saint-Yrieix-la-Perche

Station Météo-France **87187003** · Haute-Vienne · altitude 404 m  
Source des données : [meteo.data.gouv.fr](https://meteo.data.gouv.fr), jeu de données
*Données climatologiques de base — quotidiennes*  
Période de référence (normales) : **1995–2024**

L'interface se compose de six onglets : **📅 Mois en cours**, **💧 Bilan hydrique**,
**🌱 Phénologie**, **🌡️ Gel et chaleur**, **🐄 Stress thermique** et **🏆 Records**.

---

## Sommaire

1. [Données brutes et pipeline](#1-données-brutes-et-pipeline)
2. [Onglet — Mois en cours](#2-onglet--mois-en-cours)
3. [Onglet — Bilan hydrique](#3-onglet--bilan-hydrique)
4. [Onglet — Phénologie](#4-onglet--phénologie)
5. [Onglet — Gel et chaleur](#5-onglet--gel-et-chaleur)
6. [Onglet — Stress thermique](#6-onglet--stress-thermique)
7. [Onglet — Records](#7-onglet--records)
8. [Normales de référence](#8-normales-de-référence)
9. [Limites et précautions](#9-limites-et-précautions)

---

## 1. Données brutes et pipeline

### Fichiers sources

| Fichier | Contenu | Période |
|---|---|---|
| `data/quotidien.csv` | Données de l'année en cours, téléchargées chaque matin | Janvier de l'année courante → avant-hier |
| `data/historique.csv` | Archive complète téléchargée une fois | 1994–fin de l'année précédente |
| `data/normales.csv` | Moyennes mensuelles calculées sur 1995–2024 | 12 lignes (une par mois) |

### Variables utilisées

| Colonne CSV | Signification | Unité |
|---|---|---|
| `TN` | Température minimale journalière | °C |
| `TX` | Température maximale journalière | °C |
| `RR` | Cumul de précipitations des 24 h | mm |
| `FXI` | Rafale maximale instantanée | m/s |
| `DXI` | Direction de la rafale maximale | degrés (0–360) |
| `UN` | Humidité relative minimale | % |
| `UX` | Humidité relative maximale | % |
| `INST` | Durée d'insolation | minutes |

### Enchaînement des scripts

```
download.py          → data/quotidien.csv
download_historique.py → data/historique.csv  (exécuté une seule fois)
normales.py          → data/normales.csv      (recalcul si historique change)
dashboard.py         → docs/index.html        (exécuté chaque matin par le workflow)
```

---

## 2. Onglet — Mois en cours

### Ce qui est affiché

**Quatre tuiles KPI** résument le mois jusqu'à la dernière mesure disponible :

| Tuile | Calcul | Comparaison |
|---|---|---|
| Cumul pluie | Σ RR sur les jours du mois | Écart en % à la normale mensuelle |
| T° moyenne | Moyenne de (TN + TX) / 2 sur les jours du mois | Écart absolu à la normale (°C) |
| Vent max | max(FXI) × 3,6 → km/h | Date + direction (rose des vents 16 secteurs) |
| Insolation | Σ INST / 60 → heures | Comparaison à la normale mensuelle |

**Graphique "Détail jour par jour"** : barres de précipitations (axe gauche, mm) et courbes TX/TN (axe droit, °C), une colonne par jour du mois.

**Climogramme annuel** : barres mensuelles de pluie observée vs normale 1995–2024 (axe gauche), courbe de température moyenne mensuelle vs normale (axe droit). Couvre les 12 mois de l'année en cours.

**Bouton "Exporter les données du mois en CSV"** : télécharge un fichier `meteo-st-yrieix-AAAA-MM.csv` (UTF-8 avec BOM) contenant les colonnes Date / Précipitations / T° max / T° min pour chaque jour du mois.

### Formules

**Température moyenne journalière**
```
Tmoy = (TN + TX) / 2
```

**Température moyenne mensuelle**
```
Tmoy_mois = moyenne de Tmoy sur tous les jours du mois avec TN et TX disponibles
```

**Écart à la normale**
```
ΔT = Tmoy_mois − Normale_T_mois
ΔRR (%) = (RR_mois − Normale_RR_mois) / Normale_RR_mois × 100
```

**Conversion direction vent (degrés → rose)**  
16 secteurs de 22,5° chacun, libellés N / NNE / NE / ENE / E / ESE / SE / SSE / S / SSO / SO / OSO / O / ONO / NO / NNO.

---

## 3. Onglet — Bilan hydrique

### Ce qui est affiché

**Tuile KPI** : bilan P − ETP cumulé depuis le 1er janvier de l'année en cours, comparé à la moyenne de référence 1995–2024. Affiché en vert (excédent) ou orange (déficit).

**Graphique à 4 séries** (deux axes Y) :
- Barres bleues (axe gauche) : pluie cumulée P (mm) depuis le 1er janvier
- Ligne orange (axe gauche) : ETP cumulée (mm) depuis le 1er janvier
- Ligne verte avec zone colorée (axe droit) : bilan P − ETP de l'année en cours — zone verte au-dessus de zéro (excédent), zone orange en dessous (déficit)
- Ligne grise pointillée (axe droit) : bilan P − ETP moyen 1995–2024 au même jour de l'année

### Formules

#### ETP — méthode Hargreaves-Samani (1985)

```
ETP (mm/j) = 0,0023 × (Tmoy + 17,8) × √(TX − TN) × Ra
```

avec :
- `Tmoy = (TN + TX) / 2`
- `TX − TN` = amplitude thermique journalière (°C) — proxy de l'ensoleillement
- `Ra` = rayonnement extra-terrestre (mm/j équivalent évaporation), calculé par la méthode FAO-56

#### Rayonnement extra-terrestre Ra (FAO-56, Allen et al. 1998)

La station est à la latitude φ = 45,513667 °N.

```
dr  = 1 + 0,033 × cos(2π × J / 365)          # correction distance Terre-Soleil
δ   = 0,409 × sin(2π × J / 365 − 1,39)        # déclinaison solaire (rad)
ωs  = arccos(−tan(φ) × tan(δ))                # angle horaire au coucher du soleil
Ra  = (24 × 60 / π) × Gsc × dr × [ωs × sin(φ) × sin(δ) + cos(φ) × cos(δ) × sin(ωs)]
Ra_mm = Ra_MJ / 2,45                           # conversion MJ·m⁻² → mm
```

avec J = jour de l'année (1–365) et Gsc = 0,0820 MJ·m⁻²·min⁻¹ (constante solaire).

> **Référence** : Hargreaves G.H. & Samani Z.A., *Applied Engineering in Agriculture*, 1(2), 1985.  
> FAO : Allen R.G. et al., *Crop evapotranspiration — FAO Irrigation and Drainage Paper 56*, Rome, 1998.

#### Bilan cumulé

```
P_ETP_cumul(j) = Σ [RR(i) − ETP(i)]  pour i = 1er janvier → j
```

La courbe de référence est la **moyenne** de ce cumul, calculée sur 1995–2024, au même jour de l'année.

---

## 4. Onglet — Phénologie

L'onglet se compose de **trois blocs** : un suivi annuel de l'herbe (somme des
températures de gestion du pâturage), puis deux sections **maïs** et **blé** pilotées
par une **date de semis saisie par l'utilisateur** et recalculées en direct dans le
navigateur.

### 4.1 Herbe — somme des températures de gestion du pâturage

Méthode du **Guide du pâturage** (Programme Structurel Herbe & Fourrages en Limousin,
2013). La somme est calculée en **base 0 °C à partir du 1er février**, avec une moyenne
journalière **bornée entre 0 °C et 18 °C** (au-delà de 18 °C de moyenne, on ne compte
que 18). C'est cette somme qui calibre les seuils de gestion ci-dessous.

**Graphique** : somme cumulée depuis le 1er février, en trait plein (année en cours) et
pointillés (médiane historique 1995–2024), avec les **lignes-seuils de gestion** du
Guide (tracées via le plugin `chartjs-plugin-annotation`).

**Tableau** : cumul actuel avec barre de progression, date de franchissement cette année
(ou « en cours »), et date médiane historique 1995–2024.

```
DJC_jour = min(18, max(0, (TN + TX) / 2))      # plancher 0 °C, plafond 18 °C
DJC_cumulé(J) = Σ DJC_jour  du 1er février au jour J
```

| Seuil | Valeur | Signification |
|---|---|---|
| Début de la mise à l'herbe | 300–350 °C·j | Démarrage du pâturage (surface de base ou complémentaire) |
| Fin du déprimage | 550 °C·j | Fin du premier passage rapide |
| Calcul des jours d'avance | 650 °C·j | Prévision de fauche des excédents |
| Fin du 1ᵉʳ cycle de pâturage | 750 °C·j | Sur la surface de base |
| Fauche précoce | 900 °C·j | — |
| Fin du 2ᵉ cycle de pâturage | 1 150 °C·j | — |
| Limite de fauche (parcelles non étêtées) | 1 400 °C·j | Au-delà : valeur fourragère médiocre |

> **Source des seuils** : *Guide du pâturage*, Programme Structurel Herbe & Fourrages en
> Limousin (juillet 2013), p. 21. Seuils et méthode ajustables dans `dashboard.py`
> (`SEUILS_PHENO`, `HERBE_DEPART`, `HERBE_PLAFOND`).

### 4.2 Maïs — suivi depuis la date de semis (modèle farmi)

L'utilisateur saisit une **date de semis** et choisit une **précocité variétale**.
Le cumul de degrés-jours est calculé en **base 6 °C** avec des **plafonds** (modèle
[farmi.com](https://www.farmi.com/article/somme-chaleur-germination-mais)) :

```
TX_eff = min(TX, 30 °C)        # plafond : au-delà de 30 °C, pas de gain supplémentaire
TN_eff = max(TN, 6 °C)         # plancher : en deçà de 6 °C, ramené à la base
DJC_jour(maïs) = max(0, (TN_eff + TX_eff) / 2 − 6)
```

| Stade | Seuil (°C·j base 6) | Source |
|---|---|---|
| Levée | 80 | farmi.com |
| Floraison (sortie des soies) | 850 | ARVALIS |
| Maturité physiologique | 1 550 → 1 850 selon précocité | indice de précocité variétale |

Le seuil de maturité dépend du **sélecteur de précocité** : très précoce 1 550 ·
précoce 1 650 · ½ précoce 1 750 · ½ tardif 1 850 °C·j.

### 4.3 Blé tendre d'hiver — suivi depuis la date de semis (base 0 °C)

Saisie d'une **date de semis d'automne** ; le cumul est calculé en **base 0 °C**
(convention ARVALIS) et **traverse le changement d'année civile** (semis d'octobre
N-1 → récolte de l'été N).

```
DJC_jour(blé) = max(0, (TN + TX) / 2)    # base 0 °C, sans plafond
```

| Stade | Seuil (°C·j base 0) |
|---|---|
| Levée | 150 |
| Début tallage | 450 |
| Épi 1 cm (début montaison) | 1 000 |
| Épiaison | 1 700 |
| Floraison | 1 900 |
| Maturité | 2 300 |

> Seuils blé indicatifs (ordre de grandeur ARVALIS pour le Limousin), ajustables dans
> `dashboard.py` (`BLE_STADES`).

### Calcul interactif et projection

Pour les deux cultures, le calcul est réalisé **côté navigateur** à partir de la série
journalière TN/TX embarquée dans la page (année courante + précédente). Chaque graphique
affiche :

- la courbe **observée** (trait plein) jusqu'à la dernière mesure disponible ;
- une **projection** (pointillés) au-delà de cette date, et une courbe **« normale »**,
  toutes deux construites à partir des **incréments journaliers médians par jour-de-l'année**
  calculés sur 1995–2024 (mêmes formules et plafonds que ci-dessus) ;
- des lignes horizontales pour chaque seuil de stade.

Le tableau de chaque culture donne, par stade : le seuil, la date **atteinte** (✓) ou
**prévue** (projection), et la date **normale** 1995–2024. Les saisies (dates de semis,
précocité) sont **mémorisées** d'une visite à l'autre via `localStorage`.

#### Configuration (constantes en tête de `dashboard.py`)

| Constante | Rôle |
|---|---|
| `HERBE_DEPART`, `HERBE_PLAFOND` | date de départ (1ᵉʳ fév.) et plafond (18 °C) de la somme herbe |
| `SEUILS_PHENO` | seuils de gestion du pâturage (Guide Limousin, p. 21) |
| `MAIS_BASE`, `MAIS_TX_PLAFOND`, `MAIS_TN_PLANCHER` | base et plafonds farmi du maïs |
| `MAIS_PRECOCITES` | seuils de maturité par groupe de précocité |
| `MAIS_STADES` | stades maïs (levée, floraison, maturité) |
| `BLE_BASE`, `BLE_STADES` | base 0 et stades du blé |

---

## 5. Onglet — Gel et chaleur

### Ce qui est affiché

**Heatmap T° max — 12 mois glissants** (en tête de l'onglet) : grille calendrier sur les **365 derniers jours glissants** (de J−364 à aujourd'hui). Chaque cellule correspond à un jour et est colorée selon la TX observée, sur une échelle continue allant du bleu froid au rouge chaud.

L'échelle de couleur est normalisée entre le minimum et le maximum de TX observés sur la période affichée (5 paliers : bleu foncé, bleu, gris, orange, rouge). Les colonnes sont des semaines (lundi → dimanche, de gauche à droite) ; les étiquettes de mois indiquent la semaine où débute chaque mois.

**Calendrier annuel des gelées** : grille semaines × jours (style heatmap) pour l'année en cours. Chaque cellule représente un jour, colorié selon la catégorie de gel.

| Couleur | Catégorie | Condition |
|---|---|---|
| Gris foncé | Hors gel | TN ≥ 0 °C |
| Bleu clair | Gel léger | −2 °C ≤ TN < 0 °C |
| Bleu moyen | Gel modéré | −5 °C ≤ TN < −2 °C |
| Bleu foncé | Gel sévère | TN < −5 °C |

**Tableau récapitulatif** (1995–année en cours) : pour chaque année, nombre de jours de gel, date de la dernière gelée de printemps, date de la première gelée d'automne, et durée de la saison sans gel.

```
Saison sans gel (j) = date 1ère gelée d'automne − date dernière gelée de printemps − 1
```

---

## 6. Onglet — Stress thermique

> Libellé d'onglet : **🐄 Stress thermique**. Le titre interne du panneau précise
> *Stress thermique bovin (ITH)*.

### Ce qui est affiché

**Graphique ITH** : barres empilées (jours par classe de stress thermique, par mois) pour l'année en cours, plus une ligne pointillée indiquant le nombre moyen de jours de stress (toutes classes ≥ Alerte) sur 1995–2024.

Une **alerte rouge** s'affiche si le mois le plus récent (ou le mois précédent s'il est incomplet) dépasse 5 jours de stress sévère ou danger.

### Formules

#### Indice de Température-Humidité bovin (ITH)

```
ITH = (1,8 × TX + 32) − (0,55 − 0,0055 × HRmoy) × (1,8 × TX − 26)

avec HRmoy = (UN + UX) / 2
```

> **Référence** : INRAE, *Recommandations stress thermique bovin* (formule NRC adaptée).

#### Classes de confort/stress ITH

| Classe | Seuil ITH | Couleur |
|---|---|---|
| Confort | < 68 | Bleu |
| Alerte | 68 – 72 | Jaune |
| Stress modéré | 72 – 78 | Orange |
| Stress sévère | 78 – 84 | Rouge |
| Danger | ≥ 84 | Rouge foncé |

---

## 7. Onglet — Records

### Ce qui est affiché

**Quatre tuiles** mettent en avant les records absolus toutes années confondues (TX max, TN min, RR 24 h max, rafale FXI max) avec la date du record et la valeur atteinte dans l'année en cours. Une étoile ★ signale si l'année en cours a égalé ou battu le record.

**Tableau complet** sur 11 variables :

| Catégorie | Variable |
|---|---|
| 🌡️ Température | T° maximale absolue (TX) |
| 🌡️ Température | T° minimale absolue (TN) |
| 🌡️ Température | Mois le plus chaud (Tmoy mensuelle) |
| 🌡️ Température | Mois le plus froid (Tmoy mensuelle) |
| 🌧️ Pluie | Pluie max en 24 h |
| 🌧️ Pluie | Pluie mensuelle maximale |
| 🌧️ Pluie | Pluie mensuelle minimale |
| 🌧️ Pluie | Plus longue série sans pluie (< 0,2 mm) |
| 💨 Vent | Vent maximal (rafale FXI) |
| ❄️ Gel | Plus longue série de gels consécutifs (TN ≤ 0 °C) |
| ☀️ Insolation | Journée la plus ensoleillée ⚠️ |

Pour chaque variable, le tableau indique le record historique, sa date, la valeur de l'année en cours et sa date.

> ⚠️ **Insolation** : environ 30 % des valeurs INST sont manquantes avant 2000 sur cette station. Le record d'ensoleillement journalier est affiché à titre indicatif uniquement.

### Critères de qualification

- **Pluie mensuelle** : seuls les mois avec ≥ 25 jours de données valides sont pris en compte.
- **Température mensuelle** : idem (≥ 25 jours avec TN et TX disponibles).
- **Série sèche** : jours consécutifs avec RR < 0,2 mm.
- **Série de gels** : jours consécutifs avec TN ≤ 0 °C.

---

## 8. Normales de référence

Les normales sont calculées par `normales.py` sur la fenêtre **1995–2024** (30 ans, conforme à la méthode OMM) à partir de `data/historique.csv`.

Pour chaque mois (1 à 12) :

| Variable | Calcul |
|---|---|
| RR normal | Moyenne des cumuls mensuels sur 1995–2024 |
| TN normale | Moyenne des TN journalières sur 1995–2024 |
| TX normale | Moyenne des TX journalières sur 1995–2024 |
| INST normale | Moyenne des cumuls mensuels d'insolation (minutes) |

La température normale mensuelle affichée dans le climogramme est `(TN_normale + TX_normale) / 2`.

---

## 9. Limites et précautions

| Sujet | Détail |
|---|---|
| ETP Hargreaves-Samani | Méthode empirique basée sur la seule amplitude thermique. Sous-estime l'ETP en conditions très venteuses, sèches ou nuageuses. Choisie faute de rayonnement mesuré disponible. |
| Insolation avant 2000 | ~30 % de valeurs manquantes. Records et normales d'insolation à interpréter avec précaution. |
| Données de la veille | Météo-France publie les données avec un délai de 1 à 2 jours. Le tableau affiche les données disponibles au moment de la dernière mise à jour. |
| ITH bovin | Formule conçue pour des bovins en bâtiment. Les seuils sont des repères agronomiques, non des prévisions individuelles. |
| DJC cultures | La station est à 404 m d'altitude : les cumuls maïs (base 6, plafonds farmi) et blé (base 0) restent modestes, et la maturité du maïs n'est atteinte que les années chaudes, ce qui est cohérent avec le contexte altitudinal. Les seuils de stades sont des repères agronomiques indicatifs, non des prévisions parcellaires. |
| Projection cultures | Au-delà de la dernière mesure, les courbes maïs/blé sont prolongées par la **normale** 1995–2024 (incréments médians par jour-de-l'année). Les dates de stades « prévues » sont donc des estimations en année normale, pas des prévisions météo. |
| Année de référence | Les calculs de références utilisent toujours la période 1995–2024. Une mise à jour de cette fenêtre nécessite de relancer `normales.py` et de recalculer les médianes dans `dashboard.py`. |
