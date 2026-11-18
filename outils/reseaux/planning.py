"""Publication automatique des vidéos (lancé chaque jour par .github/workflows/planning-reseaux.yml).
Lit outils/reseaux/planning.json : [{fichier, date (AAAA-MM-JJ), titre, legende, fait:{youtube, facebook, instagram}}].
Publie AU PLUS UNE vidéo par passage (4 passages par jour : 12 h 30, 15 h 30, 17 h 30, 20 h 30) : la plus ancienne dont la date est passée et qui n'est pas encore faite partout.
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
# créneaux (17 nov. : GitHub a lancé le robot de 17 h 30 à 1 h du matin) : une vidéo neuve seulement entre 12 h et 22 h (Paris),
# et une seule avant 17 h, deux au plus par jour ; une vidéo déjà commencée (un réseau a échoué) peut être finie à toute heure.
# 18 nov. : lancé par Supabase à 12 h 30 / 17 h 30 pile (workflow_dispatch) ; les crons GitHub restent en secours. Numéro forcé : pas de limite.
if not force:
    h = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Paris")).hour
    deja_auj = sum(1 for v in plan if auj in v.get("fait", {}).values())
    neuve = lambda v: not v.get("fait")
    # 18 nov. : 4 vidéos par jour (12 h 30, 15 h 30, 17 h 30, 20 h 30) : au plus 1 avant 15 h, 2 avant 17 h, 3 avant 20 h, 4 dans la journée
    # 18 nov. (propriétaire) : 4 vidéos par jour, à 8 h, 12 h 30, 17 h 30 et 20 h 30 (Paris) ; lancé par Supabase (robot_poster)
    permis = 0 if h < 8 else 1 if h < 12 else 2 if h < 17 else 3 if h < 20 else 4
    if deja_auj >= permis: dues = [v for v in dues if not neuve(v)]
if not dues:
    print("Rien à publier maintenant (" + auj + ")."); sys.exit(0)
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
