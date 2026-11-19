"""Commentaire automatique de Solfito sous chaque vidéo du planning déjà publiée (YouTube, Facebook, Instagram).
Lancé par planning.py. Retrouve la vidéo par son titre / sa légende, poste COMMENTAIRE une seule fois par réseau
et le note dans planning.json (x["com"][réseau] = date). Un réseau qui refuse (droits manquants) est simplement sauté.
YouTube : le jeton doit avoir le droit youtube.force-ssl ; Meta : pages_manage_engagement / instagram_manage_comments."""
import json, os, sys, datetime, zoneinfo, requests
COMMENTAIRE_IG = "Ta réponse ici 👇 Tu l'avais trouvée ? 🎹"   # Instagram : sans lien (les liens dans les commentaires passent pour du spam)
COMMENTAIRE = "Ta réponse ici 👇 Et pour t'entraîner à lire les notes en jouant : solfito.com 🎹"
P = "outils/reseaux/planning.json"
plan = json.load(open(P, encoding="utf-8"))
auj = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Paris")).date().isoformat()
def afaire(res): return [x for x in plan if x.get("fait", {}).get(res) and res not in x.get("com", {})]
def noter(x, res): x.setdefault("com", {})[res] = auj

# ---- YouTube ----
if afaire("youtube") and os.environ.get("YT_REFRESH_TOKEN"):
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "youtube"))
        from publier import jeton
        h = {"Authorization": "Bearer " + jeton()}; API = "https://www.googleapis.com/youtube/v3/"
        up = requests.get(API + "channels?part=contentDetails&mine=true", headers=h, timeout=30).json()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        items = requests.get(API + f"playlistItems?part=snippet&maxResults=50&playlistId={up}", headers=h, timeout=30).json().get("items", [])
        ids = {it["snippet"]["title"]: it["snippet"]["resourceId"]["videoId"] for it in items}
        for x in afaire("youtube"):
            vid = ids.get((x["titre"] + " #Shorts")[:100])
            if not vid: continue
            r = requests.post(API + "commentThreads?part=snippet", headers={**h, "Content-Type": "application/json"},
                              data=json.dumps({"snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": COMMENTAIRE}}}}), timeout=30)
            print("YouTube", x["fichier"], r.status_code, "" if r.ok else r.text[:200])
            if r.ok: noter(x, "youtube")
            elif r.status_code == 403: break
    except (Exception, SystemExit) as e: print("YouTube : commentaire impossible", e)

# ---- Facebook + Instagram ----
tok = os.environ.get("META_PAGE_TOKEN", "").strip()
if tok and (afaire("facebook") or afaire("instagram")):
    G = "https://graph.facebook.com/v21.0"
    try:
        me = requests.get(f"{G}/me", params={"fields": "id,instagram_business_account{id}", "access_token": tok}, timeout=30)
        if me.status_code != 200:
            print("Meta /me :", me.status_code, me.text[:300])
            pages = requests.get(f"{G}/me/accounts", params={"fields": "id,name,access_token", "access_token": tok}, timeout=30).json().get("data") or []
            pg = next((p for p in pages if "solfito" in (p.get("name") or "").lower()), pages[0] if pages else None)
            if not pg: raise RuntimeError("aucune page trouvée avec ce jeton")
            tok = pg["access_token"]; me = requests.get(f"{G}/me", params={"fields": "id,instagram_business_account{id}", "access_token": tok}, timeout=30)
        me = me.json(); page = me["id"]; ig = (me.get("instagram_business_account") or {}).get("id")
        debut = lambda s: (s or "")[:40]
        if afaire("facebook"):
            vids = requests.get(f"{G}/{page}/video_reels", params={"fields": "id,description", "limit": 50, "access_token": tok}, timeout=30).json().get("data", [])
            for x in afaire("facebook"):
                v = next((v for v in vids if debut(v.get("description")) == debut(x["legende"])), None)
                if not v: continue
                r = requests.post(f"{G}/{v['id']}/comments", data={"message": COMMENTAIRE, "access_token": tok}, timeout=30)
                print("Facebook", x["fichier"], r.status_code, "" if r.ok else r.text[:200])
                if r.ok: noter(x, "facebook")
                else: break
        # 19 nov. : commentaires Instagram COUPÉS (Instagram a masqué nos commentaires comme spam après le bug de répétition).
        # Les remettre (IG_COMMENTER = True) dans 1 à 2 semaines si on veut.
        IG_COMMENTER = False
        if IG_COMMENTER and ig and afaire("instagram"):
            med = requests.get(f"{G}/{ig}/media", params={"fields": "id,caption", "limit": 50, "access_token": tok}, timeout=30).json().get("data", [])
            for x in afaire("instagram"):
                m = next((m for m in med if debut(m.get("caption")) == debut(x["legende"])), None)
                if not m: continue
                # 19 nov. : anti-doublon. Instagram publiait le commentaire mais il n'était jamais noté (il revenait à chaque passage) :
                # on regarde d'abord les commentaires déjà présents, on supprime les doublons, et on note « fait » s'il y en a un.
                def les_notres():
                    c = requests.get(f"{G}/{m['id']}/comments", params={"fields": "id,text,timestamp", "limit": 100, "access_token": tok}, timeout=30).json().get("data", [])
                    return sorted([k for k in c if (k.get("text") or "").strip() in (COMMENTAIRE, COMMENTAIRE_IG)], key=lambda k: k.get("timestamp", ""))
                notres = les_notres()
                for k in notres[1:]:
                    d = requests.delete(f"{G}/{k['id']}", params={"access_token": tok}, timeout=30)
                    print("Instagram : doublon supprimé", x["fichier"], d.status_code)
                if notres: noter(x, "instagram"); continue
                r = requests.post(f"{G}/{m['id']}/comments", data={"message": COMMENTAIRE_IG, "access_token": tok}, timeout=30)
                print("Instagram", x["fichier"], r.status_code, "" if r.ok else r.text[:200])
                # 19 nov. : Instagram bloque un commentaire répété avec un lien (anti-spam) : on n'insiste JAMAIS, on note la vidéo
                # comme traitée (sinon le robot recommencerait toutes les 30 min).
                noter(x, "instagram")
    except Exception as e:
        import traceback; traceback.print_exc(); print("Meta : commentaire impossible", e)
json.dump(plan, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
