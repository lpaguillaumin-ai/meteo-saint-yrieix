"""Télécharge le dernier fichier quotidien Météo-France pour le dépt 87,
filtre la station 87187003 (St-Yrieix-la-Perche) et écrit data/quotidien.csv."""

from __future__ import annotations

import csv
import gzip
import sys
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STATION = "87187003"

SOURCES = {
    "rr_t_vent": "https://www.data.gouv.fr/api/1/datasets/r/e7c25f1a-e0bc-4c9b-ba3c-1dca6b6ad8a2",
    "autres":    "https://www.data.gouv.fr/api/1/datasets/r/0bce6ef5-dcba-4d40-803c-e943ed92c88e",
}

# Colonnes à exposer dans le CSV final (clé = nom source, valeur = nom de sortie).
COLONNES = {
    "RR":   "RR",    # précipitations 24h (mm)
    "TN":   "TN",    # T min sous abri (°C)
    "TX":   "TX",    # T max sous abri (°C)
    "FXI":  "FXI",   # rafale max instantanée à 10 m (m/s)
    "DXI":  "DXI",   # direction de FXI (°)
    "UN":   "UN",    # humidité relative min (%)
    "UX":   "UX",    # humidité relative max (%)
    "INST": "INST",  # durée d'insolation (mn)
}

RACINE = Path(__file__).parent
DOSSIER_RAW = RACINE / "data" / "raw"
SORTIE = RACINE / "data" / "quotidien.csv"


def telecharger(url: str, destination: Path) -> None:
    """Télécharge `url` vers `destination` (suit les redirections)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"  → {url}")
    with urllib.request.urlopen(url) as reponse:
        destination.write_bytes(reponse.read())
    print(f"    {destination.name} ({destination.stat().st_size // 1024} Ko)")


def lire_csv_gz(chemin: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Lit un CSV gzippé Météo-France (séparateur `;`, UTF-8)."""
    with gzip.open(chemin, "rt", encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        lignes = [ligne for ligne in lecteur if ligne["NUM_POSTE"] == STATION]
        return lecteur.fieldnames or [], lignes


def valeur_propre(brut: str) -> str:
    """Convertit une valeur brute en chaîne propre (vide si absente)."""
    if brut is None:
        return ""
    v = brut.strip()
    if v in ("", "NA", "nan"):
        return ""
    return v


def formater_date(aaaammjj: str) -> str:
    """20260504 → 2026-05-04."""
    return f"{aaaammjj[:4]}-{aaaammjj[4:6]}-{aaaammjj[6:8]}"


def main() -> int:
    print("Téléchargement des fichiers du département 87…")
    fichiers: dict[str, Path] = {}
    for nom, url in SOURCES.items():
        cible = DOSSIER_RAW / f"Q_87_latest_{nom}.csv.gz"
        telecharger(url, cible)
        fichiers[nom] = cible

    print(f"\nFiltrage de la station {STATION}…")
    _, lignes_rrtv = lire_csv_gz(fichiers["rr_t_vent"])
    _, lignes_autres = lire_csv_gz(fichiers["autres"])
    print(f"  RR-T-Vent : {len(lignes_rrtv)} jours")
    print(f"  autres    : {len(lignes_autres)} jours")

    # Indexation par date pour la fusion.
    par_date_autres = {l["AAAAMMJJ"]: l for l in lignes_autres}

    print(f"\nÉcriture de {SORTIE.relative_to(RACINE)}…")
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    en_tetes = ["date"] + list(COLONNES.values())
    nb_ecrites = 0
    with SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(en_tetes)
        for ligne in sorted(lignes_rrtv, key=lambda l: l["AAAAMMJJ"]):
            date = ligne["AAAAMMJJ"]
            autres = par_date_autres.get(date, {})
            sortie = [formater_date(date)]
            for src, _ in COLONNES.items():
                source = ligne if src in ligne else autres
                sortie.append(valeur_propre(source.get(src, "")))
            ecrivain.writerow(sortie)
            nb_ecrites += 1

    print(f"  {nb_ecrites} lignes écrites.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
