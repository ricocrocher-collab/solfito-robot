"""Publication automatique des vidéos (lancé chaque jour par .github/workflows/planning-reseaux.yml).
Lit outils/reseaux/planning.json : [{fichier, date (AAAA-MM-JJ), titre, legende, fait:{youtube, facebook, instagram}}].
Rythme par réseau (18 nov.) : YouTube 2/jour (12 h 30, 20 h 30), Facebook et Instagram 1/jour (20 h 30) ; voir RYTHME plus bas.
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
# 18 nov. (propriétaire) : un rythme PAR RÉSEAU. Créneaux (Paris) : 8 h, 12 h 30, 17 h 30, 20 h 30 (lancés par Supabase).
#   YouTube : 2 par jour (12 h 30 et 20 h 30) ; Facebook et Instagram : 1 par jour (20 h 30).
#   Chaque réseau prend la plus ancienne vidéo prête qu'il n'a pas encore. Un numéro forcé (FORCER) part partout tout de suite.
RYTHME = {"youtube": {12: 1, 20: 2}, "facebook": {20: 1}, "instagram": {20: 1}}   # heure de début du créneau -> total permis ce jour-là
h = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Paris")).hour
def permis(res):
    if force: return 99
    ok = [n for hh, n in RYTHME[res].items() if h >= hh and h < hh + 2]   # le créneau en cours (2 h de marge pour les secours)
    return ok[0] if ok else 0
def prete(v):
    if force: return v["fichier"].endswith(force + ".mp4")
    return v["date"] <= auj and (v.get("verif") or {}).get("ok", True) is not False
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import traductions_videos as TV
def fichier_local(x):
    if not os.path.exists(x["fichier"]):   # dépôt solfito-robot : la vidéo est prise sur solfito.com
        import urllib.request; os.makedirs(os.path.dirname(x["fichier"]), exist_ok=True)
        urllib.request.urlretrieve("https://solfito.com/" + x["fichier"][5:], x["fichier"])
ok, rien = True, True
for res in RESEAUX:
    deja = sum(1 for v in plan if v.get("fait", {}).get(res) == auj)
    if deja >= permis(res): continue
    cand = sorted([v for v in plan if prete(v) and res not in v.get("fait", {})], key=lambda v: (not v.get("prio"), v["date"]))   # 21 nov. : « prio » = passe devant le retard dès sa date (vidéos d'événement, ex. Noël)
    if not cand: continue
    x = cand[0]; x.setdefault("fait", {}); rien = False
    print(res, ":", x["fichier"], "|", x["titre"]); fichier_local(x)
    if res == "youtube":
        env = {**os.environ, "FICHIER": x["fichier"], "TITRE": (x["titre"] + " #Shorts")[:100],
               "DESCRIPTION": x["legende"] + "\n\nApprends le solfège et le piano en jouant : https://solfito.com", "STATUT": "public", "PUBLIER_LE": "",
               "LOCALISATIONS": json.dumps(TV.localisations(plan.index(x) + 1), ensure_ascii=False)}
        r = subprocess.run([sys.executable, "outils/youtube/publier.py"], env=env)
        if r.returncode == 0: x["fait"]["youtube"] = auj; x["yt_trad"] = auj
        else: ok = False
    else:
        env = {**os.environ, "FICHIER": x["fichier"], "LEGENDE": x["legende"], "CIBLES": res}
        r = subprocess.run([sys.executable, "outils/reseaux/publier_meta.py"], env=env)
        if r.returncode == 0: x["fait"][res] = auj
        else: ok = False
    json.dump(plan, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if rien:
    print("Rien à publier maintenant (" + auj + ", " + str(h) + " h)."); sys.exit(0)
subprocess.run([sys.executable, "outils/reseaux/commenter.py"])   # commentaire automatique sous la vidéo
if not ok: sys.exit("Un réseau a échoué : il sera retenté au prochain créneau (voir le journal ci-dessus).")
