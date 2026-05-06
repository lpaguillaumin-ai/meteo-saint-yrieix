# Météo Saint-Yrieix

Tableau de bord météo automatique pour la station **87187003** (Saint-Yrieix-la-Perche).
Les données viennent de [meteo.data.gouv.fr](https://meteo.data.gouv.fr) (Météo-France).

La page est régénérée **chaque matin à 9h** (heure française) et publiée
automatiquement sur GitHub Pages — vous n'avez rien à faire au quotidien.

---

## 🔗 Adresse de la page publiée

Une fois la mise en service terminée (cf. ci-dessous), la page est visible à :

```
https://<votre-organisation>.github.io/<nom-du-repo>/
```

Le lien exact apparaît aussi dans l'onglet **Settings → Pages** du dépôt GitHub.

---

## 🧰 Mise en service (à faire une seule fois)

### 1. Créer le dépôt GitHub

1. Sur [github.com](https://github.com), cliquer sur **New repository**.
2. Nom suggéré : `meteo-saint-yrieix`. Le dépôt peut être public ou privé.
3. Cocher **Add a README** : non (on a déjà celui-ci).

### 2. Pousser le projet

Depuis le dossier du projet, dans un terminal :

```bash
git init
git add .
git commit -m "Première version"
git branch -M main
git remote add origin https://github.com/<votre-organisation>/meteo-saint-yrieix.git
git push -u origin main
```

### 3. Activer GitHub Pages

1. Dans GitHub, aller dans **Settings → Pages**.
2. À la ligne **Source**, choisir **GitHub Actions**.
3. (Facultatif) Dans **Settings → Actions → General**, vérifier que les workflows
   ont bien le droit d'écrire (`Read and write permissions`).

### 4. Lancer la première mise à jour

1. Aller dans l'onglet **Actions** du dépôt.
2. Cliquer sur le workflow **Mise à jour quotidienne**.
3. Bouton **Run workflow** → **Run workflow**.
4. Attendre ~2 minutes. La page apparaît ensuite à l'URL ci-dessus.

À partir de là, la mise à jour s'exécute automatiquement chaque jour à 7h UTC
(9h Paris en été, 8h en hiver).

---

## 📅 Au quotidien

**Vous n'avez rien à faire.** Tous les matins :

1. GitHub télécharge le dernier fichier Météo-France pour la Haute-Vienne.
2. Il extrait les mesures de la station St-Yrieix.
3. Il regénère la page HTML (graphiques + indicateurs).
4. Il publie la nouvelle version.

### Vérifier que tout va bien

- **Onglet Actions** du dépôt : vous devez voir une exécution verte ✅ chaque
  matin. Une croix rouge ❌ signale un problème.
- En cliquant sur une exécution, on voit les détails et les éventuels messages
  d'erreur.

### Forcer une mise à jour manuelle

Onglet **Actions** → **Mise à jour quotidienne** → **Run workflow**.

---

## 🛠️ Modifier le projet

| Je veux…                          | Fichier à modifier                          |
|-----------------------------------|---------------------------------------------|
| Changer la station                | `download.py` (constante `STATION`) + `download_historique.py` |
| Changer le département            | `download.py` (URLs `SOURCES`) + `download_historique.py` |
| Ajuster les normales              | `normales.py` (constantes `ANNEE_DEBUT` / `ANNEE_FIN`) puis `python normales.py` |
| Modifier l'apparence du tableau   | `dashboard.py` (bloc CSS dans `rendre_html`) |
| Décaler l'heure de mise à jour    | `.github/workflows/daily.yml` (ligne `cron`) |

Toute modification poussée sur `main` est automatiquement prise en compte à la
prochaine exécution.

---

## 🧪 Lancer les scripts en local (optionnel)

Si vous avez Python ≥ 3.10 installé :

```bash
python download.py             # crée data/quotidien.csv
python download_historique.py  # crée data/historique.csv (1 fois suffit)
python normales.py             # crée data/normales.csv  (à refaire si historique change)
python dashboard.py            # crée output/index.html
```

Aucune dépendance externe — uniquement la bibliothèque standard Python.

---

## ❓ En cas de souci

- **L'action échoue avec une erreur 404 / réseau** : Météo-France a peut-être
  changé l'URL d'une ressource. Vérifier sur
  <https://www.data.gouv.fr/datasets/donnees-climatologiques-de-base-quotidiennes>
  et mettre à jour les URLs dans `download.py`.
- **La page Pages affiche une 404** : vérifier dans **Settings → Pages** que
  la source est bien **GitHub Actions** et qu'au moins un workflow s'est terminé.
- **Pas de mise à jour ce matin** : GitHub désactive les workflows planifiés
  d'un dépôt sans activité depuis 60 jours. Faire un commit (même trivial) ou
  cliquer **Run workflow** une fois pour relancer la planification.

Pour toute question technique, voir aussi `claude.md` à la racine.
