"""Le relevé des cours des engrais (GitHub Actions, chaque semaine) : sources ouvertes seulement.

- Banque mondiale, « Pink Sheet » mensuelle (CC BY 4.0) : urée, TSP, chlorure de potasse, DAP, gaz naturel Europe,
  en dollars, convertis en euros au taux mensuel de la BCE ;
- INSEE, IPAMPA (Licence Ouverte) : l'indice des prix des engrais payés par les agriculteurs français.

Écrit donnees/cours.json (lu par l'onglet Marché de l'appli) et, quand un cours passe dans le quart le plus bas de ses
trois dernières années ou baisse fortement en un mois, ouvre une « issue » GitHub : la notification arrive sur le
téléphone (appli GitHub) ou par courriel. donnees/alertes.json garde ce qui a déjà été signalé.
"""
import csv
import datetime
import io
import json
import os
import re
import subprocess
import urllib.request

import openpyxl

UA = {"User-Agent": "Mozilla/5.0 (Valeur-engrais; releve hebdomadaire des cours)"}
DEPUIS = "2015-01"
FENETRE = 36                    # mois : « bas » et « haut » se jugent sur les trois dernières années
BAS, HAUT = 25, 75              # centiles
BAISSE_FORTE = -8.0             # % en un mois
APPLI = "https://malakit51.github.io/Valeur-engrais/#marche"
MWH_PAR_MMBTU = 0.293071

# (colonne de la Pink Sheet, clé, nom, élément, teneur % pour le prix de l'unité, lieu)
BANQUE_MONDIALE = [
    ("Urea", "uree", "Urée", "N", 46, "Moyen-Orient, FOB"),
    ("TSP", "tsp", "TSP (super triple)", "P2O5", 46, "golfe des États-Unis, import"),
    ("Potassium chloride", "kcl", "Chlorure de potasse", "K2O", 60, "Brésil, CFR"),
    ("DAP", "dap", "DAP (18-46)", "P2O5", None, "golfe des États-Unis, FOB"),
    ("Natural gas, Europe", "gaz", "Gaz naturel Europe", None, None, "TTF"),
]
# séries INSEE (IPAMPA mensuel, base 100 en 2020)
INSEE = [("010777321", "ipampa_n", "Engrais azotés simples, prix payés en France", "N")]


def lire(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def taux_bce():
    """{« AAAA-MM »: dollars pour un euro}, moyenne mensuelle de la BCE."""
    d = lire(f"https://data-api.ecb.europa.eu/service/data/EXR/M.USD.EUR.SP00.A?format=csvdata&startPeriod={DEPUIS}")
    return {r["TIME_PERIOD"]: float(r["OBS_VALUE"]) for r in csv.DictReader(io.StringIO(d.decode("utf-8"))) if r["OBS_VALUE"]}


def banque_mondiale(taux):
    page = lire("https://www.worldbank.org/en/research/commodity-markets").decode("utf-8", "replace")
    lien = re.search(r'https?://[^"\'\s]+?CMO-Historical-Data-Monthly\.xlsx', page).group(0)
    wb = openpyxl.load_workbook(io.BytesIO(lire(lien)), read_only=True, data_only=True)
    lignes = list(wb["Monthly Prices"].iter_rows(values_only=True))
    entete = next(r for r in lignes if r and r[1] and str(r[1]).startswith("Crude oil"))
    noms = [str(c or "").replace("*", "").strip() for c in entete]
    series = []
    for col, cle, nom, el, teneur, lieu in BANQUE_MONDIALE:
        i = noms.index(col)
        pts = []
        for r in lignes:
            m = re.fullmatch(r"(\d{4})M(\d{2})", str(r[0] or ""))
            if not m or not isinstance(r[i], (int, float)):
                continue
            mois = f"{m.group(1)}-{m.group(2)}"
            if mois < DEPUIS or mois not in taux:
                continue
            v = r[i] / taux[mois]                                    # € par t (gaz : € par mmbtu)
            pts.append([mois, round(v / MWH_PAR_MMBTU if cle == "gaz" else v, 2)])
        series.append({"cle": cle, "nom": nom, "element": el, "teneur": teneur, "lieu": lieu,
                       "unite": "€/MWh" if cle == "gaz" else "€/t", "frequence": "mensuel",
                       "source": "Banque mondiale (Pink Sheet), en euros au taux BCE",
                       "lien": "https://www.worldbank.org/en/research/commodity-markets", "points": pts})
    return series


def insee():
    series = []
    for idbank, cle, nom, el in INSEE:
        x = lire(f"https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/{idbank}?startPeriod={DEPUIS}").decode("utf-8")
        pts = sorted([m.group(1), float(m.group(2))] for m in re.finditer(r'TIME_PERIOD="(\d{4}-\d{2})" OBS_VALUE="([\d.]+)"', x))
        series.append({"cle": cle, "nom": nom, "element": el, "teneur": None, "lieu": "France",
                       "unite": "indice (100 en 2020)", "frequence": "mensuel", "source": "INSEE, IPAMPA",
                       "lien": f"https://www.insee.fr/fr/statistiques/serie/{idbank}", "points": pts})
    return series


def signal(s):
    """Le dernier cours jugé sur les trois dernières années : centile, état, variations."""
    pts = s["points"]
    if len(pts) < 13:
        return None
    vals = [v for _, v in pts[-FENETRE:]]
    dernier = vals[-1]
    centile = round(100 * sum(1 for v in vals if v < dernier) / max(1, len(vals) - 1))
    trie = sorted(vals)
    q = lambda p: trie[min(len(trie) - 1, int(p / 100 * (len(trie) - 1) + 0.5))]
    return {"mois": pts[-1][0], "dernier": dernier, "centile": centile,
            "etat": "bas" if centile <= BAS else "haut" if centile >= HAUT else "moyen",
            "var1": round(100 * (dernier / pts[-2][1] - 1), 1), "var12": round(100 * (dernier / pts[-13][1] - 1), 1),
            "q25": q(BAS), "q75": q(HAUT), "min": trie[0], "max": trie[-1]}


def alerter(series, deja, silencieux=False):
    """Une issue GitHub par nouveauté : un cours qui entre dans le quart bas, ou une forte baisse en un mois."""
    nouvelles = []
    for s in series:
        g = s.get("signal")
        if not g or s["cle"] == "gaz":
            continue
        cle = f"{s['cle']}:{g['mois']}"
        if cle in deja:
            continue
        raisons = []
        if g["etat"] == "bas":
            raisons.append(f"dans le quart le plus bas de ses 3 dernières années (centile {g['centile']})")
        if g["var1"] <= BAISSE_FORTE:
            raisons.append(f"en baisse de {-g['var1']:.1f} % en un mois")
        if raisons:
            nouvelles.append((cle, s, g, raisons))
    for cle, s, g, raisons in nouvelles:
        titre = f"Engrais : {s['nom'].lower()} " + (" et ".join(raisons))[:120]
        corps = (f"**{s['nom']}** ({s['lieu']}), {g['mois']} : **{g['dernier']:.0f} {s['unite']}**, "
                 f"{g['var1']:+.1f} % sur un mois, {g['var12']:+.1f} % sur un an.\n\n"
                 f"Sur les 3 dernières années : de {g['min']:.0f} à {g['max']:.0f} {s['unite']}, "
                 f"le quart le plus bas sous {g['q25']:.0f}.\n\n"
                 f"Source : {s['source']}. C'est un prix de marché mondial : il annonce la tendance, ton prix livré "
                 f"suit avec un décalage.\n\nLes courbes : {APPLI}\n")
        if os.environ.get("GITHUB_ACTIONS") and not silencieux:
            subprocess.run(["gh", "issue", "create", "--title", titre, "--body", corps, "--label", "alerte"], check=False)
        print("ALERTE" + (" (premier relevé : notée, pas envoyée)" if silencieux else ""), titre)
        deja.append(cle)


def main():
    taux = taux_bce()
    series = banque_mondiale(taux) + insee()
    for s in series:
        s["signal"] = signal(s)
        g = s["signal"]
        print(s["cle"], len(s["points"]), "points", s["points"][-1] if s["points"] else None, g and (g["etat"], g["centile"], g["var1"]))
    os.makedirs("donnees", exist_ok=True)
    chemin_alertes = "donnees/alertes.json"
    premier = not os.path.exists(chemin_alertes)          # le premier relevé note l'état du moment sans alerter
    deja = [] if premier else json.load(open(chemin_alertes))
    alerter(series, deja, silencieux=premier)
    json.dump(deja[-200:], open(chemin_alertes, "w"), ensure_ascii=False, indent=1)
    json.dump({"maj": datetime.date.today().isoformat(), "fenetre_mois": FENETRE, "series": series},
              open("donnees/cours.json", "w"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
