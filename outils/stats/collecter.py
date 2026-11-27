"""v763 : robot des stats (onglet Admin « Tout »). Lancé chaque jour par .github/workflows/stats-quotidiennes.yml.
Collecte YouTube, Facebook, Instagram, Google Search Console et les range dans Supabase (table stats_jour, fonction
stats_ecrire, SQL supabase/solfito-stats-tout-v763.sql). Les clés restent dans les secrets GitHub, jamais dans le site.
Un réseau qui refuse (secret absent, droit manquant) est simplement sauté : le reste continue.
Lignes : jour, source (youtube/facebook/instagram/google), cle, valeur, detail (JSON facultatif)."""
import json, os, sys, datetime, zoneinfo, requests
SB_URL = "https://lskljjzijrtmakbinecr.supabase.co"
SB_KEY = "sb_publishable_pI0-BJ8Db2bnpqWsYiXcjw_igz1LAsu"   # clé PUBLIQUE du site (déjà dans 00-config.js)
CLE = os.environ.get("STATS_CLE", "").strip()
auj = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Paris")).date()
J = auj.isoformat()
L = []
def ligne(source, cle, valeur, detail=None, jour=J):
    if valeur is None: return
    L.append({"jour": jour, "source": source, "cle": cle[:120], "valeur": float(valeur), "detail": detail})
num = lambda x: int(x) if str(x or "").isdigit() else 0

# ---- YouTube ----
if os.environ.get("YT_REFRESH_TOKEN"):
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "youtube"))
        from publier import jeton
        h = {"Authorization": "Bearer " + jeton()}; API = "https://www.googleapis.com/youtube/v3/"
        ch = requests.get(API + "channels?part=statistics,contentDetails&mine=true", headers=h, timeout=30).json()["items"][0]
        st = ch["statistics"]
        ligne("youtube", "abonnes", num(st.get("subscriberCount")))
        ligne("youtube", "vues_total", num(st.get("viewCount")))
        up = ch["contentDetails"]["relatedPlaylists"]["uploads"]; ids, page = [], ""
        while len(ids) < 200:
            r = requests.get(API + f"playlistItems?part=contentDetails&maxResults=50&playlistId={up}&pageToken={page}", headers=h, timeout=30).json()
            ids += [it["contentDetails"]["videoId"] for it in r.get("items", [])]; page = r.get("nextPageToken")
            if not page: break
        for i in range(0, len(ids), 50):
            for v in requests.get(API + "videos?part=statistics,snippet&id=" + ",".join(ids[i:i+50]), headers=h, timeout=30).json().get("items", []):
                s = v["statistics"]
                ligne("youtube", "video:" + v["id"], num(s.get("viewCount")), {"t": v["snippet"]["title"][:90], "pub": v["snippet"]["publishedAt"][:10],
                      "likes": num(s.get("likeCount")), "com": num(s.get("commentCount"))})
        print("YouTube :", len(ids), "vidéos")
    except (Exception, SystemExit) as e: print("YouTube : impossible", e)

# ---- Facebook + Instagram ----
tok = os.environ.get("META_PAGE_TOKEN", "").strip()
if tok:
    G = "https://graph.facebook.com/v21.0"
    get = lambda chemin, **p: requests.get(f"{G}/{chemin}", params={**p, "access_token": tok}, timeout=30)
    try:
        me = get("me", fields="id,name,followers_count,fan_count,instagram_business_account{id,followers_count,media_count}")
        if me.status_code != 200:   # jeton d'utilisateur : on prend le jeton de la page Solfito
            pages = get("me/accounts", fields="id,name,access_token").json().get("data") or []
            pg = next((p for p in pages if "solfito" in (p.get("name") or "").lower()), pages[0] if pages else None)
            if not pg: raise RuntimeError("aucune page trouvée avec ce jeton")
            tok = pg["access_token"]; me = get("me", fields="id,name,followers_count,fan_count,instagram_business_account{id,followers_count,media_count}")
        me = me.json(); page = me["id"]; ig = me.get("instagram_business_account") or {}
        ligne("facebook", "abonnes", me.get("followers_count") or me.get("fan_count"))
        n = 0
        for v in get(f"{page}/video_reels", fields="id,description,created_time,likes.summary(true).limit(0),comments.summary(true).limit(0)", limit=100).json().get("data", []):
            vues = None
            r = get(f"{v['id']}/video_insights", metric="blue_reels_play_count")   # demande read_insights
            if r.ok:
                d = r.json().get("data") or []
                if d and d[0].get("values"): vues = d[0]["values"][0].get("value")
            ligne("facebook", "reel:" + v["id"], vues if vues is not None else 0, {"t": (v.get("description") or "")[:90], "pub": (v.get("created_time") or "")[:10],
                  "likes": (v.get("likes") or {}).get("summary", {}).get("total_count", 0), "com": (v.get("comments") or {}).get("summary", {}).get("total_count", 0),
                  "sans_vues": vues is None}); n += 1
        print("Facebook :", n, "reels")
        if ig.get("id"):
            ligne("instagram", "abonnes", ig.get("followers_count"))
            n = 0
            for m in get(f"{ig['id']}/media", fields="id,caption,timestamp,like_count,comments_count,media_product_type", limit=100).json().get("data", []):
                vues = None
                r = get(f"{m['id']}/insights", metric="views")   # demande instagram_manage_insights
                if r.ok:
                    d = r.json().get("data") or []
                    if d and d[0].get("values"): vues = d[0]["values"][0].get("value")
                ligne("instagram", "media:" + m["id"], vues if vues is not None else 0, {"t": (m.get("caption") or "")[:90], "pub": (m.get("timestamp") or "")[:10],
                      "likes": m.get("like_count", 0), "com": m.get("comments_count", 0), "sans_vues": vues is None}); n += 1
            print("Instagram :", n, "publications")
    except Exception as e: print("Meta : impossible", e)

# ---- Google Search Console ----
gsc = os.environ.get("GSC_SERVICE_ACCOUNT", "").strip() or os.environ.get("GOOGLE_PLAY_JSON", "").strip()   # solfito-robot : le compte de service de Google Play (à ajouter dans Search Console)
if gsc:
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
        s = AuthorizedSession(service_account.Credentials.from_service_account_info(json.loads(gsc), scopes=["https://www.googleapis.com/auth/webmasters.readonly"]))
        import urllib.parse   # 27 nov. : le site est une propriété « https://solfito.com/ » (pas sc-domain) : on prend celle que Google donne
        sites = [x["siteUrl"] for x in s.get("https://www.googleapis.com/webmasters/v3/sites").json().get("siteEntry", []) if "solfito.com" in x["siteUrl"]] or ["sc-domain:solfito.com"]
        Q = "https://www.googleapis.com/webmasters/v3/sites/" + urllib.parse.quote(sites[0], safe="") + "/searchAnalytics/query"
        d0 = (auj - datetime.timedelta(days=10)).isoformat()
        for r in s.post(Q, json={"startDate": d0, "endDate": J, "dimensions": ["date"]}).json().get("rows", []):   # Google a 2-3 jours de retard
            ligne("google", "clics", r["clicks"], {"imp": r["impressions"], "pos": round(r["position"], 1)}, jour=r["keys"][0])
        d28 = (auj - datetime.timedelta(days=28)).isoformat()
        for dim, cle in (("query", "requetes"), ("country", "pays"), ("page", "pages")):
            rows = s.post(Q, json={"startDate": d28, "endDate": J, "dimensions": [dim], "rowLimit": 25}).json().get("rows", [])
            ligne("google", cle, len(rows), [{"k": r["keys"][0].replace("https://solfito.com", "")[:80], "c": r["clicks"], "i": r["impressions"]} for r in rows])
        print("Google : OK")
    except Exception as e: print("Google : impossible", e)

# ---- Envoi dans Supabase ----
print(len(L), "lignes")
if not CLE:   # solfito-robot : pas de clé, on prouve qui on est avec le jeton OIDC signé par GitHub (fonction Supabase stats-robot)
    o = requests.get(os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=solfito-stats",
                     headers={"Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]}, timeout=30).json()["value"]
    r = requests.post(SB_URL + "/functions/v1/stats-robot", headers={"Authorization": "Bearer " + o, "Content-Type": "application/json"}, json=L, timeout=60)
else:
    r = requests.post(SB_URL + "/rest/v1/rpc/stats_ecrire", headers={"apikey": SB_KEY, "Authorization": "Bearer " + SB_KEY, "Content-Type": "application/json"},
                      json={"p_cle": CLE, "p_lignes": L}, timeout=60)
print("Supabase :", r.status_code, r.text[:200])
if not r.ok or not r.json().get("ok"): sys.exit(1)
