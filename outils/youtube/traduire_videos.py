"""Ajoute les titres/descriptions traduits (6 langues) aux vidéos du planning DÉJÀ publiées sur YouTube.
Lancé par outils/reseaux/planning.py avant chaque publication. Retrouve chaque vidéo par son titre dans les
50 derniers envois de la chaîne, met à jour snippet + localizations, et note « yt_trad » dans planning.json."""
import json, os, sys, datetime, zoneinfo, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reseaux"))
from publier import jeton
import traductions_videos as TV
P = "outils/reseaux/planning.json"
plan = json.load(open(P, encoding="utf-8"))
afaire = [(i + 1, x) for i, x in enumerate(plan) if x.get("fait", {}).get("youtube") and not x.get("yt_trad")]
if not afaire:
    print("Traductions YouTube : rien à faire."); sys.exit(0)
h = {"Authorization": "Bearer " + jeton()}
API = "https://www.googleapis.com/youtube/v3/"
up = requests.get(API + "channels?part=contentDetails&mine=true", headers=h, timeout=30).json()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
items = requests.get(API + f"playlistItems?part=snippet&maxResults=50&playlistId={up}", headers=h, timeout=30).json().get("items", [])
par_titre = {it["snippet"]["title"]: it["snippet"]["resourceId"]["videoId"] for it in items}
auj = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Paris")).date().isoformat()
for num, x in afaire:
    vid = par_titre.get((x["titre"] + " #Shorts")[:100])
    if not vid:
        print(f"Vidéo {num} introuvable sur la chaîne (titre changé ?)"); continue
    v = requests.get(API + f"videos?part=snippet&id={vid}", headers=h, timeout=30).json()["items"][0]["snippet"]
    sn = {k: v[k] for k in ("title", "description", "categoryId", "tags") if k in v}
    sn["defaultLanguage"] = v.get("defaultLanguage", "fr")
    r = requests.put(API + "videos?part=snippet,localizations", headers={**h, "Content-Type": "application/json"},
                     data=json.dumps({"id": vid, "snippet": sn, "localizations": TV.localisations(num)}), timeout=30)
    if r.status_code == 200:
        x["yt_trad"] = auj; print(f"Vidéo {num} : titres traduits ajoutés ({vid})")
    else:
        print(f"Vidéo {num} : refus {r.status_code} {r.text[:200]}")
json.dump(plan, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
