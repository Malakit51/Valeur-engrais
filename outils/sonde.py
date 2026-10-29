"""Reconnaissance (une fois) : l'historique des cotations françaises est-il lisible derrière les graphiques ?"""
import html, re, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Valeur-engrais; releve hebdomadaire des cours)"}

def lire(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
            d = r.read().decode("utf-8", "replace")
            print(f"--- {url} : {r.status}, {len(d)} car.")
            return d
    except Exception as e:
        print(f"--- {url} : ÉCHEC {e}")
        return ""

# les liens des produits sur la page engrais de Terre-net et de Web-agri
for page in ("https://www.terre-net.fr/marche-agricole/engrais", "https://www.web-agri.fr/marches-agricoles/engrais"):
    h = lire(page)
    liens = sorted(set(re.findall(r'href="([^"]*(?:ammonitrate|uree|solution|phosphate|mop|dap)[^"]*)"', h, re.I)))
    print("liens :", liens[:30])

# une page produit : ce qui ressemble à des séries de dates et de prix
for url in ("https://www.terre-net.fr/marche-agricole/ammonitrate-27/engrais",):
    h = lire(url)
    for m in re.finditer(r"(\d{2}/\d{2}/\d{4})", h):
        pass
    dates = re.findall(r"\d{2}/\d{2}/\d{4}", h)
    print("dates trouvées :", len(dates), dates[:5], dates[-5:])
    for m in re.finditer(r"<script[^>]*>(.*?)</script>", h, re.S):
        sc = m.group(1)
        if re.search(r"\d{3}[.,]\d", sc) and re.search(r"(data|series|chart|point)", sc, re.I):
            print("SCRIPT", len(sc), sc[:1500].replace("\n", " "))
    t = html.unescape(re.sub(r"<[^>]+>", "|", re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)))
    t = re.sub(r"(\s*\|\s*)+", "|", t)
    i = t.find("Ammonitrate 27")
    print("TEXTE", t[i:i + 3000])
    for u in sorted(set(re.findall(r'["\'](/[^"\']*(?:graph|chart|histor|cotation)[^"\']*)["\']', h, re.I)))[:20]:
        print("URL ?", u)

h = lire("https://www.agri-mutuel.com/cotations/engrais/")
for u in sorted(set(re.findall(r'["\']([^"\']*(?:ajax|graph|chart|histor|json)[^"\']*)["\']', h, re.I)))[:30]:
    print("AM ?", u)
