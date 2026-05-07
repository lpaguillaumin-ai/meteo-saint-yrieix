# Documentation — Tableau de bord météo Saint-Yrieix-la-Perche

Station Météo-France **87187003** · Haute-Vienne · altitude 404 m  
Source des données : [meteo.data.gouv.fr](https://meteo.data.gouv.fr), jeu de données
*Données climatologiques de base — quotidiennes*  
Période de référence (normales) : **1995–2024**

---

## Sommaire

1. [Données brutes et pipeline](#1-données-brutes-et-pipeline)
2. [Onglet — Mois en cours](#2-onglet--mois-en-cours)
3. [Onglet — Bilan hydrique](#3-onglet--bilan-hydrique)
4. [Onglet — Phénologie](#4-onglet--phénologie)
5. [Onglet — Gel et chaleur](#5-onglet--gel-et-chaleur)
6. [Onglet — Heatmap T° max](#6-onglet--heatmap-t-max)
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

### Ce qui est affiché

**Graphique à 9 séries** : degrés-jours de croissance cumulés depuis le 1er janvier pour trois bases de température (0 °C, 6 °C, 10 °C), chacune en trait plein (année en cours) et pointillés (médiane historique 1995–2024). Trois lignes horizontales marquent les seuils phénologiques.

**Tableau des seuils** : pour chaque seuil, le DJC actuel avec une barre de progression, la date de franchissement cette année (ou "en cours"), et la date médiane historique 1995–2024.

### Formules

#### Degrés-Jours de Croissance (DJC / GDD)

```
DJC_jour(base) = max(0,  (TN + TX) / 2  −  Tbase)
DJC_cumulé(J)  = Σ DJC_jour(base)  pour tous les jours du 1er janvier au jour J
```

> **Référence** : McMaster G.S. & Wilhelm W.W., *Agricultural and Forest Meteorology*, 87(4), 1997.

#### Trois bases de calcul

| Base | Culture visée |
|---|---|
| 0 °C | Développement végétatif général, pousse de l'herbe |
| 6 °C | Céréales à paille (blé, orge) |
| 10 °C | Maïs grain |

#### Seuils phénologiques

| Seuil | Base | Valeur | Signification | Source |
|---|---|---|---|---|
| Démarrage pousse de l'herbe | 0 °C | 200 DJC | Reprise de croissance herbacée | INRAE / ARVALIS |
| Épiaison blé tendre | 6 °C | 1 000 DJC | Sortie des épis | ARVALIS, *Guide Grandes Cultures* 2022 |
| Floraison maïs grain | 10 °C | 1 700 DJC | Pollinisation du maïs | ARVALIS / INRAE |

#### Médiane historique (P50)

Pour chaque seuil et chaque année de référence (1995–2024), le script calcule le jour de l'année (DOY) où le cumul DJC franchit le seuil. La médiane de ces 30 DOY donne la date de référence affichée.

---

## 5. Onglet — Gel et chaleur

### Ce qui est affiché

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

## 6. Onglet — Heatmap T° max

### Ce qui est affiché

Grille calendrier sur les **365 derniers jours glissants** (de J−364 à aujourd'hui). Chaque cellule correspond à un jour et est colorée selon la TX observée, sur une échelle continue allant du bleu froid au rouge chaud.

L'échelle de couleur est normalisée entre le minimum et le maximum de TX observés sur la période affichée (5 paliers : bleu foncé, bleu, gris, orange, rouge).

Les colonnes sont des semaines (lundi → dimanche, de gauche à droite). Les étiquettes de mois indiquent la semaine où débute chaque mois.

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
| DJC maïs | La station est à 404 m d'altitude. Le seuil de 1 700 DJC base 10 °C (floraison maïs) n'est pas atteint certaines années, ce qui est cohérent avec le contexte altitudinal. |
| Année de référence | Les calculs de références utilisent toujours la période 1995–2024. Une mise à jour de cette fenêtre nécessite de relancer `normales.py` et de recalculer les médianes dans `dashboard.py`. |
