"""Calcule les normales mensuelles 1995-2024 à partir d'un CSV historique
(même schéma que data/quotidien.csv : date, RR, TN, TX, FXI, DXI, UN, UX, INST)
et écrit data/normales.csv."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from statistics import mean

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ANNEE_DEBUT, ANNEE_FIN = 1995, 2024

# Variables à cumuler sur le mois (somme mensuelle, puis moyenne des sommes).
CUMULS = ("RR", "INST")
# Variables à moyenner directement sur les jours du mois.
MOYENNES = ("TN", "TX", "FXI", "DXI", "UN", "UX")

VARIABLES = CUMULS + MOYENNES

RACINE = Path(__file__).parent
ENTREE_DEFAUT = RACINE / "data" / "historique.csv"
SORTIE = RACINE / "data" / "normales.csv"


def parser_float(brut: str) -> float | None:
    if brut is None or brut.strip() == "":
        return None
    try:
        return float(brut)
    except ValueError:
        return None


def charger(chemin: Path) -> list[dict]:
    """Lit le CSV historique, garde les années dans la fenêtre de référence."""
    lignes: list[dict] = []
    with chemin.open("r", encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f):
            date = ligne["date"]  # AAAA-MM-JJ
            annee = int(date[:4])
            if not (ANNEE_DEBUT <= annee <= ANNEE_FIN):
                continue
            mois = int(date[5:7])
            valeurs = {v: parser_float(ligne.get(v, "")) for v in VARIABLES}
            lignes.append({"annee": annee, "mois": mois, **valeurs})
    return lignes


def calculer_normales(lignes: list[dict]) -> list[dict]:
    """Pour chaque mois 1..12, calcule la normale de chaque variable."""
    # Pour les cumuls : somme par (année, mois), puis moyenne des sommes.
    sommes_annuelles: dict[tuple[int, int], dict[str, float]] = {}
    # Pour les moyennes : on accumule toutes les valeurs journalières du mois.
    valeurs_journalieres: dict[int, dict[str, list[float]]] = {
        m: {v: [] for v in MOYENNES} for m in range(1, 13)
    }

    for l in lignes:
        cle = (l["annee"], l["mois"])
        cumul_mois = sommes_annuelles.setdefault(cle, {v: 0.0 for v in CUMULS})
        for v in CUMULS:
            x = l[v]
            if x is not None:
                cumul_mois[v] += x
        for v in MOYENNES:
            x = l[v]
            if x is not None:
                valeurs_journalieres[l["mois"]][v].append(x)

    # Regroupement des cumuls par mois (toutes années confondues).
    cumuls_par_mois: dict[int, dict[str, list[float]]] = {
        m: {v: [] for v in CUMULS} for m in range(1, 13)
    }
    for (_annee, mois), cumul in sommes_annuelles.items():
        for v in CUMULS:
            cumuls_par_mois[mois][v].append(cumul[v])

    resultats = []
    for mois in range(1, 13):
        ligne = {"mois": mois}
        for v in CUMULS:
            valeurs = cumuls_par_mois[mois][v]
            ligne[v] = round(mean(valeurs), 1) if valeurs else ""
        for v in MOYENNES:
            valeurs = valeurs_journalieres[mois][v]
            ligne[v] = round(mean(valeurs), 1) if valeurs else ""
        resultats.append(ligne)
    return resultats


def main() -> int:
    entree = Path(sys.argv[1]) if len(sys.argv) > 1 else ENTREE_DEFAUT
    if not entree.exists():
        print(f"Fichier introuvable : {entree}", file=sys.stderr)
        print("Usage : py normales.py [chemin/historique.csv]", file=sys.stderr)
        return 1

    print(f"Lecture {entree.relative_to(RACINE)} (période {ANNEE_DEBUT}-{ANNEE_FIN})…")
    lignes = charger(entree)
    print(f"  {len(lignes)} jours retenus")

    if not lignes:
        print("Aucune donnée dans la fenêtre de référence.", file=sys.stderr)
        return 1

    annees = sorted({l["annee"] for l in lignes})
    print(f"  années couvertes : {annees[0]}-{annees[-1]} ({len(annees)} ans)")

    normales = calculer_normales(lignes)

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    en_tetes = ["mois", *VARIABLES]
    with SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=en_tetes)
        ecrivain.writeheader()
        ecrivain.writerows(normales)

    print(f"Écrit {SORTIE.relative_to(RACINE)} ({len(normales)} mois).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
