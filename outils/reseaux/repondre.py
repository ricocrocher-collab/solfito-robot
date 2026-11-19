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
MODELES = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite"]
MODELE_LOCAL = "qwen2.5:7b"   # 19 nov. : 3B écrivait trop mal ; 7B (gratuit, sans clé) seulement si GEMINI_API_KEY est absent

# ---------- 19 nov. : réponses refaites (le propriétaire les trouvait « très nulles ») ----------
# 1) langue du commentaire détectée → réponses toutes faites dans la bonne langue (avant : toujours en français) ;
# 2) consigne beaucoup plus précise + exemples : répondre à CE QUE la personne a dit, jamais « Merci pour ton commentaire ! » ;
# 3) contrôle de qualité : une réponse plate, trop longue, dans une autre langue ou avec un lien est refusée, on réessaie une fois,
#    sinon on NE répond PAS (mieux vaut pas de réponse qu'une réponse nulle).
MOTS_LANGUE = {
    "fr": " je tu il le la les un une des et est pas trop super merci bravo trop c'est j'ai ça avec pour sur dans vidéo ",
    "en": " the you i is it and this that what my so love thanks thank great nice cool wow can how video got out of all ",
    "es": " el la los que es y muy gracias hola me mi una por qué como bien jaja ",
    "pt": " o a os que é e muito obrigado obrigada oi eu meu uma não por que como bem kkk ",
    "de": " der die das und ist ich du nicht sehr danke ein eine wie gut toll super ",
    "it": " il la che e è non molto grazie ciao io mi un una per come bene bravo ",
}
def langue(t, defaut="fr"):
    import re
    if re.search(r"[¡¿ñ]", t or ""): return "es"
    if re.search(r"[ãõ]", t or ""): return "pt"
    if re.search(r"[ßäöü]", (t or "").lower()): return "de"
    t = re.sub(r"\b(do|ré|re|mi|fa|sol|la|si|[a-g])\b", " ", (t or "").lower())   # les noms de notes ne comptent pas
    t = " " + "".join(c if c.isalpha() or c in "'" else " " for c in t) + " "
    sc = {l: sum(1 for w in set(t.split()) if f" {w} " in m) for l, m in MOTS_LANGUE.items()}
    l = max(sc, key=sc.get)
    return l if sc[l] >= 1 else defaut

import random
TOUT_FAIT = {   # réponses toutes faites, plusieurs variantes par langue
    "3/3": {"fr": ["3 sur 3, trop fort ! 🎉 Tu lis les notes comme un pro.", "Sans faute ! 🎉 La prochaine sera plus dure, prépare-toi 😏", "3/3 👏 Rien ne t'échappe !"],
            "en": ["3 out of 3, amazing! 🎉 You read notes like a pro.", "Perfect score! 🎉 The next one will be harder 😏"],
            "es": ["¡3 de 3, increíble! 🎉 Lees las notas como un pro."], "pt": ["3 de 3, incrível! 🎉 Você lê as notas como um profissional."],
            "de": ["3 von 3, super! 🎉 Du liest Noten wie ein Profi."], "it": ["3 su 3, fortissimo! 🎉 Leggi le note come un professionista."]},
    "2/3": {"fr": ["2 sur 3, tout près ! 👏 Laquelle t'a piégé ?", "Presque parfait 👏 La 3e était sournoise, hein ?"],
            "en": ["2 out of 3, so close! 👏 Which one tricked you?"], "es": ["¡2 de 3, casi! 👏 ¿Cuál te engañó?"],
            "pt": ["2 de 3, quase! 👏 Qual te enganou?"], "de": ["2 von 3, fast! 👏 Welche hat dich reingelegt?"], "it": ["2 su 3, quasi! 👏 Quale ti ha ingannato?"]},
    "1/3": {"fr": ["1 sur 3, c'est un début 💪 Astuce : repère d'abord la note sur la 2e ligne, c'est le Sol !", "On progresse 💪 Retente la prochaine, tu vas voir !"],
            "en": ["1 out of 3, that's a start 💪 Tip: find the 2nd line first, it's G!"], "es": ["1 de 3, ¡es un comienzo! 💪"],
            "pt": ["1 de 3, é um começo! 💪"], "de": ["1 von 3, ein Anfang! 💪"], "it": ["1 su 3, è un inizio! 💪"]},
    "0/3": {"fr": ["Pas facile du tout celle-là 😄 Avec un peu d'entraînement, ça viendra vite !"], "en": ["That one was tough 😄 A little practice and you'll get it!"],
            "es": ["¡Esa era difícil! 😄 Con práctica lo lograrás."], "pt": ["Essa era difícil! 😄 Com prática você consegue."],
            "de": ["Die war echt schwer 😄 Mit etwas Übung klappt's!"], "it": ["Era difficile! 😄 Con un po' di pratica ci riuscirai."]},
    "emoji": {"fr": ["🎹💜", "😍🎶", "🙌🎵"], "en": ["🎹💜", "🙌🎵"], "es": ["🎹💜"], "pt": ["🎹💜"], "de": ["🎹💜"], "it": ["🎹💜"]},
}
def tf(cle, lg): return random.choice(TOUT_FAIT[cle].get(lg) or TOUT_FAIT[cle]["fr"])

CONSIGNE = """Tu es la personne qui gère les réseaux de Solfito (jamais « IA », « assistant », « bot »). Solfito : appli (Android, iPhone) et site solfito.com pour apprendre le solfège et le piano en jouant, de 7 à 77 ans, avec Mélo, une petite note violette. Gratuit : lecture de notes, rythme, débuts au piano. Premium : oreille musicale, théorie, toutes les chansons. 7 langues.
Les vidéos sont des petits quiz : on montre des notes sur une portée et on demande de les lire, puis on donne la réponse.

Tu réponds à un {quoi}. Langue de réponse OBLIGATOIRE : {langue}.
Comment bien répondre :
- réagis à CE QUE la personne a écrit (reprends un détail de son message) ; une réponse qui irait sous n'importe quel commentaire est INTERDITE ;
- 1 ou 2 phrases courtes, ton complice et enthousiaste, tutoiement, au plus 1 émoji ;
- jamais : « Merci pour ton commentaire », « N'hésite pas », « Super commentaire », « Nous sommes ravis » ;
- s'il a répondu au quiz : dis s'il a juste avec les bonnes réponses ci-dessous (ne les invente JAMAIS) et félicite ou encourage ;
- s'il pose une question sur la musique : réponds vraiment, juste et simplement (clé de sol par défaut) ;
- s'il dit qu'il apprend / débute : encourage avec un petit conseil concret ;
- critique : calme, poli, reconnais le point, sans te justifier longuement ;
- tu peux finir par une petite question pour continuer la discussion (une fois sur deux) ;
- n'invente aucune fonction, prix, promo, date ; ne parle pas d'essai gratuit ; aucun lien sauf « solfito.com » si on te demande où trouver l'appli ;
- avis Google Play : remercie pour un point précis de l'avis ; si un problème est décrit, excuse-toi et propose d'écrire à contact@solfito.com ;
- spam, arnaque, insulte, sexuel, ou rien à répondre : écris exactement SKIP

Exemples (style à imiter, pas à recopier) :
« j'ai eu 2/3 j'ai confondu le la et le si » → « 2 sur 3, pas mal ! Le La et le Si sont voisins, astuce : le Si est sur la 3e ligne 😉 »
« trop dur pour moi je débute » → « Tout le monde a commencé là ! Commence par repérer le Sol sur la 2e ligne, le reste suit 💪 »
« c'est quoi l'appli ? » → « C'est Solfito, sur Android, iPhone ou solfito.com : des petits jeux pour lire les notes 🎹 »
« I got all of them!! » → « All three, nice! 🎉 Ready for a harder one next time? »

Contexte : {contexte}
Message de {auteur} : « {texte} »
Écris seulement la réponse, sans guillemets."""

NOMS_LANGUE = {"fr": "français", "en": "anglais", "es": "espagnol", "pt": "portugais (Brésil)", "de": "allemand", "it": "italien"}
NOTES = ["DO", "RE", "MI", "FA", "SOL", "LA", "SI"]
def notes_de(t):   # noms de notes écrits dans un commentaire (« mi ré la », « Mi-Ré-La »… ou « E D A »)
    import re, unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", t.upper()) if unicodedata.category(c) != "Mn")
    fr = re.findall(r"\b(DO|RE|MI|FA|SOL|LA|SI)\b", t)
    if len(fr) >= 2: return fr
    en = re.findall(r"\b([A-G])\b", t)
    return [{"C": "DO", "D": "RE", "E": "MI", "F": "FA", "G": "SOL", "A": "LA", "B": "SI"}[x] for x in en] if len(en) >= 2 else fr

def quiz(texte, contexte, lg):   # réponse sûre (sans IA) quand quelqu'un donne des notes à un quiz « lis ces notes »
    if "bonnes réponses dans l'ordre : " not in (contexte or ""): return None
    att = [notes_de(a)[0] if notes_de(a) else None for a in contexte.split("bonnes réponses dans l'ordre : ")[1].split(", ")]
    if None in att: return None
    dit = notes_de(texte)
    if len(dit) < 2: return None
    bon = sum(1 for a, b in zip(att, dit) if a == b)
    EN = {"DO": "C", "RE": "D", "MI": "E", "FA": "F", "SOL": "G", "LA": "A", "SI": "B"}
    sol = ", ".join((EN[a] if lg in ("en", "de") else a.replace("RE", "RÉ").capitalize() if lg == "fr" else a.capitalize()) for a in att)
    if bon == len(att): return tf("3/3", lg)
    if bon: return tf("2/3" if bon == 2 else "1/3", lg).split(" 👏")[0].split(" 💪")[0] + (" 👏 " if bon == 2 else " 💪 ") + {"fr": "Les bonnes réponses : ", "en": "The answers: ", "es": "Respuestas: ", "pt": "Respostas: ", "de": "Lösung: ", "it": "Risposte: "}.get(lg, "") + sol + "."
    return tf("0/3", lg).split(" 😄")[0] + " 😄 " + {"fr": "Les bonnes réponses : ", "en": "The answers: ", "es": "Respuestas: ", "pt": "Respostas: ", "de": "Lösung: ", "it": "Risposte: "}.get(lg, "") + sol + "."

def local(invite):   # IA gratuite sans clé (Ollama, sur la machine GitHub ; dépôt public = gratuit)
    try:
        r = requests.post("http://localhost:11434/api/generate", json={"model": MODELE_LOCAL, "prompt": invite, "stream": False,
                          "options": {"temperature": 0.7, "num_predict": 110}}, timeout=400)
        return r.json().get("response", "").strip() if r.status_code == 200 else None
    except Exception as e:
        print("IA locale indisponible :", e); return None

def court(texte, contexte, lg):   # réponses très courtes (« 3/3 », « 2 », émojis) : réponse toute faite, sans IA
    import re
    t = texte.strip()
    m = re.fullmatch(r"\D{0,16}([0-3])\s*(/|sur|out of|de|von|su)\s*3\D{0,10}", t, re.I)
    if m: return tf(m.group(1) + "/3", lg)
    m = re.fullmatch(r"\W*([0-3])\W*", t)
    if m: return tf(m.group(1) + "/3", lg) if "bonnes réponses" in (contexte or "") else None
    if not re.search(r"[A-Za-zÀ-ÿ]{2}", t): return None if not re.search(r"\S", t) else tf("emoji", lg)
    return False

MOTS_INTERDITS = ("qwen", "alibaba", "assistant", "intelligence artificielle", " ia ", " ai ", "je ne peux pas", "i cannot", "as an ai", "modèle de langage",
                  "merci pour ton commentaire", "merci pour votre commentaire", "thanks for your comment", "thank you for your comment",
                  "n'hésite pas", "nous sommes ravis", "super commentaire", "http", "www.", "@")

def correcte(t, lg):
    if not t or len(t) > 260 or t.count("\n") > 1: return False
    if any(m in " " + t.lower() + " " for m in MOTS_INTERDITS): return False
    if sum(1 for c in t if ord(c) > 0x2000 and not c.isalpha()) > 3: return False   # trop d'émojis
    if lg != "fr" and langue(t, lg) == "fr" and len(t) > 25: return False          # répond en français à un étranger
    return True

def ia(quoi, texte, auteur, contexte):
    lg = langue(texte, "fr")
    q = quiz(texte, contexte, lg)
    if q: return q
    c = court(texte, contexte, lg)
    if c is not False: return c
    inv = CONSIGNE.format(quoi=quoi, texte=texte[:1500], auteur=auteur or "quelqu'un", contexte=contexte or "aucun", langue=NOMS_LANGUE.get(lg, "la langue du message"))
    cle = os.environ.get("GEMINI_API_KEY", "")
    for essai in range(2):
        t = None
        if cle:
            corps = {"contents": [{"parts": [{"text": inv}]}], "generationConfig": {"temperature": 0.8, "maxOutputTokens": 200}}
            for m in MODELES:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={cle}", json=corps, timeout=60)
                if r.status_code == 200:
                    try: t = r.json()["candidates"][0]["content"]["parts"][0]["text"]; break
                    except Exception: continue
                print("Gemini", m, r.status_code, r.text[:120], flush=True); time.sleep(2)
        if t is None: t = local(inv)
        if t is None: return False
        t = t.strip().strip('"«»“” ').strip()
        if "SKIP" in t[:8].upper(): return None
        if correcte(t, lg): return t
        print("réponse refusée (qualité) :", t[:140], flush=True)
    return None   # deux réponses ratées : on ne répond pas

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
    up = requests.get(API + "channels?part=contentDetails&mine=true", headers=h, timeout=30).json()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    vids = requests.get(API + "playlistItems", headers=h, params={"part": "snippet", "playlistId": up, "maxResults": 30}, timeout=30).json().get("items", [])
    titres = {v["snippet"]["resourceId"]["videoId"]: v["snippet"]["title"] for v in vids}
    th = []
    for vid in titres:   # vidéo par vidéo (allThreadsRelatedToChannelId en oublie)
        th += requests.get(API + "commentThreads", headers=h, timeout=30, params={"part": "snippet,replies", "videoId": vid,
                           "maxResults": 50, "textFormat": "plainText"}).json().get("items", [])
        if os.environ.get("ESSAI"): print("vidéo", titres[vid][:40], "->", len(th), "fils", flush=True)
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
    if not js: print("Google Play : secret GOOGLE_PLAY_JSON absent"); return
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    cr = service_account.Credentials.from_service_account_info(json.loads(js), scopes=["https://www.googleapis.com/auth/androidpublisher"]); cr.refresh(Request())
    h = {"Authorization": "Bearer " + cr.token}; A = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/com.solfito.app/reviews"
    r = requests.get(A, headers=h, params={"maxResults": 50}, timeout=30)
    if r.status_code != 200: print("Google Play :", r.status_code, r.text[:200]); return
    print("Google Play : connecté,", len(r.json().get("reviews", [])), "avis récents")
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
