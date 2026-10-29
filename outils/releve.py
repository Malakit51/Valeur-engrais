"""Le relevé des cours des engrais (GitHub Actions, chaque semaine) : sources ouvertes seulement.

- Banque mondiale, « Pink Sheet » mensuelle (CC BY 4.0) : urée, TSP, chlorure de potasse, DAP, gaz naturel Europe,
  en dollars, convertis en euros au taux mensuel de la BCE ;
- INSEE, IPAMPA (Licence Ouverte) : l'indice des prix des engrais payés par les agriculteurs français ;
- Web-agri (www.web-agri.fr/marches-agricoles/engrais), source citée : les cotations françaises du jour (ammonitrate,
  solution azotée, urée, TSP, chlorure, DAP), relevées une fois par semaine, à usage personnel. L'historique de ces
  cotations est réservé aux abonnés : il se construit ici semaine après semaine, à partir du 29/10/2026.

Écrit donnees/cours.json (lu par l'onglet Marché de l'appli) et, quand un cours passe dans le quart le plus bas de ses
trois dernières années ou baisse fortement en un mois, ouvre une « issue » GitHub : la notification arrive sur le
téléphone (appli GitHub) ou par courriel. donnees/alertes.json garde ce qui a déjà été signalé.
"""
import csv
import datetime
import html
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
BAISSE_FORTE = -8.0             # % en un mois (cours mensuels)
BAISSE_FORTE_HEBDO = -5.0       # % en 4 semaines (cotations françaises)
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
# cotations françaises de Web-agri : (nom sur la page, clé, nom, élément, teneur %)
WEB_AGRI = "https://www.web-agri.fr/marches-agricoles/engrais"
FRANCE = [
    ("Ammonitrate 33.5%", "fr_an33", "Ammonitrate 33,5", "N", 33.5),
    ("Ammonitrate 27%", "fr_an27", "Ammonitrate 27", "N", 27),
    ("Solution azotée", "fr_sol", "Solution azotée", "N", 30),
    ("Urée", "fr_uree", "Urée", "N", 46),
    ("Super phosphate triple", "fr_tsp", "Super triple (TSP)", "P2O5", 45),
    ("MOP", "fr_mop", "Chlorure de potasse (MOP)", "K2O", 60),
    ("DAP", "fr_dap", "DAP (18-46)", "P2O5", None),
]
SEMAINES = 156                  # trois ans de relevés hebdomadaires
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


def web_agri(anciennes):
    """Les cotations françaises du jour, ajoutées à leur historique (une valeur par date de cotation)."""
    h = html.unescape(lire(WEB_AGRI).decode("utf-8", "replace"))
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)
    t = re.sub(r"\s*(<[^>]+>\s*)+", "|", t)
    series = []
    for nom_page, cle, nom, el, teneur in FRANCE:
        m = re.search(r"\|" + re.escape(nom_page) + r"\|([^|]+?)\s*\|, €/t\|(\d\d)/(\d\d)/(\d{4})\|Prix\|Var\.\|([\d\s.,]+?)\s*\|", t)
        ancienne = anciennes.get(cle) or {}
        pts = [p for p in ancienne.get("points", [])]
        lieu = ancienne.get("lieu") or ""
        if m:
            lieu = m.group(1).strip()
            date = f"{m.group(4)}-{m.group(3)}-{m.group(2)}"
            prix = float(m.group(5).replace(" ", "").replace(",", "."))
            pts = [p for p in pts if p[0] != date] + [[date, prix]]
            pts.sort()
        else:
            print("Web-agri : cotation introuvable :", nom_page)
        series.append({"cle": cle, "nom": nom, "element": el, "teneur": teneur, "lieu": lieu, "unite": "€/t",
                       "frequence": "hebdomadaire", "source": "Web-agri, cotations du jour", "lien": WEB_AGRI,
                       "points": pts[-SEMAINES * 2:]})
    return series


def signal(s):
    """Le dernier cours jugé sur les trois dernières années : centile, état, variations (sur un mois et sur un an :
    1 et 12 relevés pour une série mensuelle, 4 et 52 pour une hebdomadaire). Une série hebdomadaire n'a d'état
    qu'après 26 relevés (six mois)."""
    pts = s["points"]
    hebdo = s.get("frequence") == "hebdomadaire"
    court, long_, fenetre, minimum = (4, 52, SEMAINES, 26) if hebdo else (1, 12, FENETRE, 13)
    if len(pts) < 2:
        return None
    vals = [v for _, v in pts[-fenetre:]]
    dernier = vals[-1]
    var = lambda n: round(100 * (dernier / pts[-1 - n][1] - 1), 1) if len(pts) > n else None
    g = {"mois": pts[-1][0], "dernier": dernier, "var1": var(min(court, len(pts) - 1)), "var12": var(long_),
         "releves": len(pts), "etat": None}
    if len(pts) >= minimum:
        trie = sorted(vals)
        q = lambda p: trie[min(len(trie) - 1, int(p / 100 * (len(trie) - 1) + 0.5))]
        centile = round(100 * sum(1 for v in vals if v < dernier) / max(1, len(vals) - 1))
        g.update({"centile": centile, "etat": "bas" if centile <= BAS else "haut" if centile >= HAUT else "moyen",
                  "q25": q(BAS), "q75": q(HAUT), "min": trie[0], "max": trie[-1]})
    return g


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
        hebdo = s.get("frequence") == "hebdomadaire"
        if g["etat"] == "bas":
            raisons.append(f"dans le quart le plus bas de ses 3 dernières années (centile {g['centile']})")
        if g["var1"] is not None and g["var1"] <= (BAISSE_FORTE_HEBDO if hebdo else BAISSE_FORTE):
            raisons.append(f"en baisse de {-g['var1']:.1f} % en " + ("4 semaines" if hebdo else "un mois"))
        if raisons:
            nouvelles.append((cle, s, g, raisons))
    for cle, s, g, raisons in nouvelles:
        titre = f"Engrais : {s['nom'].lower()} " + (" et ".join(raisons))[:120]
        var = lambda v, quand: f", {v:+.1f} % {quand}" if v is not None else ""
        corps = (f"**{s['nom']}** ({s['lieu']}), {g['mois']} : **{g['dernier']:.0f} {s['unite']}**"
                 f"{var(g['var1'], 'sur un mois')}{var(g['var12'], 'sur un an')}.\n\n"
                 + (f"Sur les 3 dernières années : de {g['min']:.0f} à {g['max']:.0f} {s['unite']}, "
                    f"le quart le plus bas sous {g['q25']:.0f}.\n\n" if g.get("etat") else "")
                 + f"Source : {s['source']} ({s['lien']}). C'est un prix de gros : il annonce la tendance, ton prix "
                 f"livré suit avec un décalage.\n\nLes courbes : {APPLI}\n")
        if os.environ.get("GITHUB_ACTIONS") and not silencieux:
            subprocess.run(["gh", "issue", "create", "--title", titre, "--body", corps, "--label", "alerte"], check=False)
        print("ALERTE" + (" (premier relevé : notée, pas envoyée)" if silencieux else ""), titre)
        deja.append(cle)


def main():
    taux = taux_bce()
    anciennes = {}
    if os.path.exists("donnees/cours.json"):
        anciennes = {s["cle"]: s for s in json.load(open("donnees/cours.json"))["series"]}
    series = web_agri(anciennes) + banque_mondiale(taux) + insee()
    for s in series:
        s["signal"] = signal(s)
        g = s["signal"]
        print(s["cle"], len(s["points"]), "points", s["points"][-1] if s["points"] else None, g and (g["etat"], g.get("centile"), g["var1"]))
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
