"""Publication automatique des vidéos (lancé chaque jour par .github/workflows/planning-reseaux.yml).
Lit outils/reseaux/planning.json : [{fichier, date (AAAA-MM-JJ), titre, legende, fait:{youtube, facebook, instagram}}].
Publie AU PLUS UNE vidéo par passage (2 passages par jour : 12 h 30 et 17 h 30) : la plus ancienne dont la date est passée et qui n'est pas encore faite partout.
Chaque réseau est noté dans « fait » dès qu'il a réussi (un réseau en panne est retenté le lendemain, sans republier les autres).
Le fichier mis à jour est renvoyé dans le dépôt par le workflow."""
import json, os, subprocess, sys, datetime, zoneinfo

P = "outils/reseaux/planning.json"
RESEAUX = ["youtube", "facebook", "instagram"]
plan = json.load(open(P, encoding="utf-8"))
auj = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Paris")).date().isoformat()
force = os.environ.get("FORCER", "").strip()   # numéro de fichier à publier tout de suite (ex. 05), lancement à la main
# titres traduits pour les vidéos YouTube déjà publiées (sans bloquer la suite si ça échoue)
if not force and os.environ.get("YT_REFRESH_TOKEN"):
    subprocess.run([sys.executable, "outils/youtube/traduire_videos.py"])
    subprocess.run([sys.executable, "outils/reseaux/commenter.py"])
    plan = json.load(open(P, encoding="utf-8"))
dues = [x for x in plan if (x["fichier"].endswith(force + ".mp4") if force else x["date"] <= auj) and any(r not in x.get("fait", {}) for r in RESEAUX)]
# jamais une vidéo refusée par la vérification Gemini (verifier_videos.py), sauf publication forcée
if not force: dues = [x for x in dues if (x.get("verif") or {}).get("ok", True) is not False]
if not dues:
    print("Rien à publier aujourd'hui (" + auj + ")."); sys.exit(0)
x = sorted(dues, key=lambda v: v["date"])[0]
x.setdefault("fait", {})
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import traductions_videos as TV
num = plan.index(x) + 1
print("Vidéo du jour :", x["fichier"], "|", x["titre"])
if not os.path.exists(x["fichier"]):   # dépôt solfito-robot : la vidéo est prise sur solfito.com
    import urllib.request; os.makedirs(os.path.dirname(x["fichier"]), exist_ok=True)
    urllib.request.urlretrieve("https://solfito.com/" + x["fichier"][5:], x["fichier"])
ok = True
if "youtube" not in x["fait"]:
    env = {**os.environ, "FICHIER": x["fichier"], "TITRE": (x["titre"] + " #Shorts")[:100],
           "DESCRIPTION": x["legende"] + "\n\nApprends le solfège et le piano en jouant : https://solfito.com", "STATUT": "public", "PUBLIER_LE": "",
           "LOCALISATIONS": json.dumps(TV.localisations(num), ensure_ascii=False)}
    r = subprocess.run([sys.executable, "outils/youtube/publier.py"], env=env)
    if r.returncode == 0: x["fait"]["youtube"] = auj; x["yt_trad"] = auj
    else: ok = False
for res in ("facebook", "instagram"):
    if res in x["fait"]: continue
    env = {**os.environ, "FICHIER": x["fichier"], "LEGENDE": x["legende"], "CIBLES": res}
    r = subprocess.run([sys.executable, "outils/reseaux/publier_meta.py"], env=env)
    if r.returncode == 0: x["fait"][res] = auj
    else: ok = False
json.dump(plan, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("Fait :", x["fait"])
subprocess.run([sys.executable, "outils/reseaux/commenter.py"])   # commentaire automatique sous la vidéo
if not ok: sys.exit("Un réseau a échoué : il sera retenté demain (voir le journal ci-dessus).")
