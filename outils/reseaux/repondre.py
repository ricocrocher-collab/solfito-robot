"""Réponses AUTOMATIQUES (sans validation, demande du propriétaire le 17 nov.) aux commentaires YouTube, Facebook, Instagram
et aux avis Google Play. Réponses : quiz vérifié sans IA ; sinon IA locale gratuite Qwen 2.5 3B (Ollama, sans clé) ; Gemini seulement si GEMINI_API_KEY existe.
Chaque commentaire / avis n'est traité qu'une fois (outils/reseaux/repondus.json). Au plus MAX réponses par passage.
Secrets : GEMINI_API_KEY ; YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN ; META_PAGE_TOKEN ; GOOGLE_PLAY_JSON (compte de service, facultatif)."""
import json, os, sys, time, datetime, requests
ICI = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(ICI, "repondus.json"); P = os.path.join(ICI, "planning.json")
fait = json.load(open(F, encoding="utf-8")) if os.path.exists(F) else {}
plan = json.load(open(P, encoding="utf-8")) if os.path.exists(P) else []
MAX = 25; n = 0
G = "https://graph.facebook.com/v21.0"
MODELES = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]

CONSIGNE = """Tu es la personne qui gère Solfito (appli et site solfito.com pour apprendre le solfège et le piano en jouant, avec Mélo, la petite note violette).
Tu réponds à un {quoi}. Règles :
- réponds dans la langue du message, tutoiement, 1 ou 2 phrases courtes, chaleureux et naturel, 1 émoji au plus ;
- si c'est une réponse au quiz de la vidéo, dis si c'est juste en t'appuyant sur les bonnes réponses données ci-dessous (ne les invente jamais) ;
- si c'est une critique, reste calme, poli, factuel, remercie ; ne te dispute jamais ; en solfège sois rigoureux (clé de sol par défaut) ;
- n'invente aucune fonction, prix, promotion ou date ; ne parle jamais d'essai gratuit ; pas de lien sauf « solfito.com » si c'est utile ;
- avis Google Play : remercie ; si un problème est décrit, excuse-toi et propose d'écrire à contact@solfito.com ;
- si le message est du spam, une arnaque, haineux, sexuel, ou n'appelle aucune réponse, réponds exactement : SKIP
Contexte : {contexte}
Message de {auteur} : « {texte} »
Écris seulement la réponse."""

NOTES = ["DO", "RE", "MI", "FA", "SOL", "LA", "SI"]
def notes_de(t):   # noms de notes écrits dans un commentaire (« mi ré la », « Mi-Ré-La »…)
    import re, unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", t.upper()) if unicodedata.category(c) != "Mn")
    return [m for m in re.findall(r"\b(DO|RE|MI|FA|SOL|LA|SI)\b", t)]

def quiz(texte, contexte):   # réponse sûre (sans IA) quand quelqu'un donne des notes à un quiz « lis ces notes »
    if "bonnes réponses dans l'ordre : " not in (contexte or ""): return None
    att = [notes_de(a)[0] if notes_de(a) else None for a in contexte.split("bonnes réponses dans l'ordre : ")[1].split(", ")]
    if None in att: return None
    dit = notes_de(texte)
    if len(dit) < 2: return None
    bon = sum(1 for a, b in zip(att, dit) if a == b)
    sol = ", ".join(a.replace("RE", "RÉ") for a in att)
    if bon == len(att): return "Bravo, 3 sur 3 ! 🎉 Tu lis super bien les notes."
    if bon: return f"Presque ! {bon} sur {len(att)} 👏 Les bonnes réponses : {sol}."
    return f"Bien essayé ! Les bonnes réponses : {sol} 🎹 Tu feras mieux à la prochaine !"

def local(invite):   # IA gratuite sans clé : Qwen 2.5 (3B) avec Ollama, sur la machine GitHub (dépôt public = gratuit)
    try:
        r = requests.post("http://localhost:11434/api/generate", json={"model": "qwen2.5:3b", "prompt": invite, "stream": False,
                          "options": {"temperature": 0.5, "num_predict": 120}}, timeout=300)
        return r.json().get("response", "").strip() if r.status_code == 200 else None
    except Exception as e:
        print("IA locale indisponible :", e); return None

def ia(quoi, texte, auteur, contexte):
    q = quiz(texte, contexte)
    if q: return q
    cle = os.environ.get("GEMINI_API_KEY", "")
    if not cle:
        t = local(CONSIGNE.format(quoi=quoi, texte=texte[:1500], auteur=auteur or "quelqu'un", contexte=contexte or "aucun"))
        if t is None: return False
        t = t.strip().strip('"«» ')
        return None if (not t or "SKIP" in t[:8].upper()) else t[:600]
    corps = {"contents": [{"parts": [{"text": CONSIGNE.format(quoi=quoi, texte=texte[:1500], auteur=auteur or "quelqu'un", contexte=contexte or "aucun")}]}],
             "generationConfig": {"temperature": 0.6, "maxOutputTokens": 300}}
    for m in MODELES:
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={cle}", json=corps, timeout=60)
        if r.status_code == 200:
            try: t = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip().strip('"«» ')
            except Exception: continue
            return None if (not t or "SKIP" in t[:8]) else t[:900]
        print("Gemini", m, r.status_code, r.text[:120], flush=True); time.sleep(2)
    return False

def contexte_video(titre):
    titre = (titre or "").replace(" #Shorts", "").strip().lower()
    for x in plan:
        if x.get("titre", "").strip().lower() == titre or titre and titre in x.get("legende", "").lower():
            return f"vidéo « {x['titre']} »" + (f", bonnes réponses dans l'ordre : {', '.join(x['attendu'])}" if x.get("attendu") else "")
    return f"vidéo « {titre} »" if titre else ""

def noter(k):
    fait[k] = datetime.date.today().isoformat()

def traiter(k, quoi, texte, auteur, ctx, envoyer):
    global n
    if k in fait or n >= MAX or not (texte or "").strip(): return
    rep = ia(quoi, texte, auteur, ctx)
    if rep is False: return
    if rep is None: noter(k); print("ignoré :", texte[:80]); return
    if os.environ.get("ESSAI"): print(f"[ESSAI {k.split(':')[0]}] {texte[:90]!r} -> {rep!r}", flush=True); return
    try:
        ok = envoyer(rep)
    except Exception as e:
        ok = False; print("erreur", e)
    if ok: noter(k); n += 1; print(f"[{k.split(':')[0]}] {texte[:70]!r} -> {rep[:120]!r}", flush=True)

# ---- YouTube ----
def youtube():
    if not os.environ.get("YT_REFRESH_TOKEN"): return
    sys.path.insert(0, os.path.join(ICI, "..", "youtube")); from publier import jeton
    h = {"Authorization": "Bearer " + jeton()}; API = "https://www.googleapis.com/youtube/v3/"
    moi = requests.get(API + "channels?part=id&mine=true", headers=h, timeout=30).json()["items"][0]["id"]
    th = requests.get(API + "commentThreads", headers=h, timeout=30, params={"part": "snippet,replies", "allThreadsRelatedToChannelId": moi,
                      "maxResults": 50, "order": "time", "textFormat": "plainText"}).json().get("items", [])
    titres = {}
    for t in th:
        top = t["snippet"]["topLevelComment"]; s = top["snippet"]
        if (s.get("authorChannelId") or {}).get("value") == moi: continue
        if any((r["snippet"].get("authorChannelId") or {}).get("value") == moi for r in (t.get("replies") or {}).get("comments", [])): noter("yt:" + top["id"]); continue
        vid = s.get("videoId") or t["snippet"].get("videoId")
        if vid not in titres:
            v = requests.get(API + "videos", headers=h, params={"part": "snippet", "id": vid}, timeout=30).json().get("items", [])
            titres[vid] = v[0]["snippet"]["title"] if v else ""
        def env(rep, pid=top["id"]):
            r = requests.post(API + "comments?part=snippet", headers={**h, "Content-Type": "application/json"},
                              json={"snippet": {"parentId": pid, "textOriginal": rep}}, timeout=30)
            if r.status_code != 200: print("YouTube refuse", r.status_code, r.text[:200])
            return r.status_code == 200
        traiter("yt:" + top["id"], "commentaire YouTube", s.get("textDisplay", ""), s.get("authorDisplayName"), contexte_video(titres[vid]), env)

# ---- Facebook + Instagram ----
def meta():
    tok = os.environ.get("META_PAGE_TOKEN", "").strip()
    if not tok: return
    me = requests.get(f"{G}/me", params={"fields": "id,instagram_business_account{id,username}", "access_token": tok}, timeout=30).json()
    pid = me.get("id"); ig = me.get("instagram_business_account") or {}
    if not pid: print("Meta :", str(me)[:200]); return
    r = requests.get(f"{G}/{pid}/video_reels", params={"fields": "id,description,comments.limit(50){id,message,from,comments.limit(20){from}}", "limit": 25, "access_token": tok}, timeout=60).json()
    for v in r.get("data", []):
        ctx = contexte_video((v.get("description") or "").split(" 🎼")[0])
        for c in (v.get("comments") or {}).get("data", []):
            if (c.get("from") or {}).get("id") == pid: continue
            if any((x.get("from") or {}).get("id") == pid for x in (c.get("comments") or {}).get("data", [])): noter("fb:" + c["id"]); continue
            env = lambda rep, cid=c["id"]: requests.post(f"{G}/{cid}/comments", data={"message": rep, "access_token": tok}, timeout=30).status_code == 200
            traiter("fb:" + c["id"], "commentaire Facebook", c.get("message", ""), (c.get("from") or {}).get("name"), ctx, env)
    if not ig.get("id"): return
    r = requests.get(f"{G}/{ig['id']}/media", params={"fields": "id,caption,comments.limit(50){id,text,username,replies{username}}", "limit": 25, "access_token": tok}, timeout=60).json()
    if "error" in r: print("Instagram :", str(r)[:200])
    for m in r.get("data", []):
        ctx = contexte_video((m.get("caption") or "").split(" 🎼")[0])
        for c in (m.get("comments") or {}).get("data", []):
            if c.get("username") == ig.get("username"): continue
            if any(x.get("username") == ig.get("username") for x in (c.get("replies") or {}).get("data", [])): noter("ig:" + c["id"]); continue
            env = lambda rep, cid=c["id"]: requests.post(f"{G}/{cid}/replies", data={"message": rep, "access_token": tok}, timeout=30).status_code == 200
            traiter("ig:" + c["id"], "commentaire Instagram", c.get("text", ""), c.get("username"), ctx, env)

# ---- Google Play ----
def play():
    js = os.environ.get("GOOGLE_PLAY_JSON", "").strip()
    if not js: return
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    cr = service_account.Credentials.from_service_account_info(json.loads(js), scopes=["https://www.googleapis.com/auth/androidpublisher"]); cr.refresh(Request())
    h = {"Authorization": "Bearer " + cr.token}; A = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/com.solfito.app/reviews"
    r = requests.get(A, headers=h, params={"maxResults": 50}, timeout=30)
    if r.status_code != 200: print("Google Play :", r.status_code, r.text[:200]); return
    for rv in r.json().get("reviews", []):
        cs = rv.get("comments", [])
        u = next((c["userComment"] for c in cs if "userComment" in c), None)
        if not u or any("developerComment" in c for c in cs): continue
        env = lambda rep, rid=rv["reviewId"]: requests.post(f"{A}/{rid}:reply", headers=h, json={"replyText": rep[:350]}, timeout=30).status_code == 200
        traiter("play:" + rv["reviewId"], f"avis Google Play ({u.get('starRating')} étoiles sur 5)", u.get("text", ""), rv.get("authorName"), "", env)

for f in (youtube, meta, play):
    try: f()
    except Exception as e: print(f.__name__, "erreur :", e)
json.dump(fait, open(F, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("Réponses envoyées :", n)
