"""Publie une vidéo en Reel sur la page Facebook Solfito et sur l'Instagram relié (lancé par .github/workflows/meta.yml).
Le jeton de la page vient du secret GitHub META_PAGE_TOKEN (jamais dans un fichier). Il ne périme pas s'il a été fait
à partir d'un jeton utilisateur « prolongé » (60 jours). La page et le compte Instagram sont retrouvés à partir du jeton.
Sans FICHIER : simple test de connexion (affiche la page et le compte Instagram, ne publie rien)."""
import os, sys, time, json, requests

V = "v21.0"
G = f"https://graph.facebook.com/{V}"

def stop(msg, r=None):
    sys.exit(msg + (f" ({r.status_code}) : {r.text[:600]}" if r is not None else ""))

def main():
    tok = os.environ.get("META_PAGE_TOKEN", "").strip()
    if not tok: stop("Secret META_PAGE_TOKEN absent : le ranger dans GitHub (Settings › Secrets and variables › Actions).")
    fichier, legende = os.environ.get("FICHIER", "").strip(), os.environ.get("LEGENDE", "")
    cibles = [c.strip() for c in os.environ.get("CIBLES", "facebook,instagram").lower().split(",") if c.strip()]
    r = requests.get(f"{G}/me", params={"fields": "id,name,instagram_business_account{id,username}", "access_token": tok}, timeout=30)
    if r.status_code != 200 and "instagram_business_account" in r.text:
        # jeton UTILISATEUR rangé à la place du jeton de la page : on récupère le jeton de la page Solfito
        r2 = requests.get(f"{G}/me/accounts", params={"fields": "id,name,access_token", "access_token": tok}, timeout=30)
        pages = (r2.json().get("data") or []) if r2.status_code == 200 else []
        pg = next((p for p in pages if "solfito" in (p.get("name") or "").lower()), pages[0] if pages else None)
        if not pg: stop("Jeton utilisateur sans accès à la page Solfito", r2)
        print("⚠️ META_PAGE_TOKEN contient le jeton UTILISATEUR (il périme). Mieux : y ranger l'access_token de la page (dans data).")
        tok = pg["access_token"]
        r = requests.get(f"{G}/me", params={"fields": "id,name,instagram_business_account{id,username}", "access_token": tok}, timeout=30)
    if r.status_code != 200: stop("Jeton refusé par Meta (refaire le jeton de la page ?)", r)
    me = r.json(); page_id = me["id"]; ig = (me.get("instagram_business_account") or {})
    print("Page Facebook :", me.get("name"), "| Instagram :", ig.get("username") or "(non relié)")
    if not fichier:
        print("Test de connexion OK (aucune vidéo demandée)."); return
    taille = os.path.getsize(fichier); data = open(fichier, "rb").read()
    erreurs = []
    if "facebook" in cibles:
        try:
            # Reel de la page : démarrer, envoyer le fichier, publier
            r = requests.post(f"{G}/{page_id}/video_reels", data={"upload_phase": "start", "access_token": tok}, timeout=60)
            if r.status_code != 200: raise RuntimeError(f"début ({r.status_code}) {r.text[:300]}")
            vid = r.json()["video_id"]
            r = requests.post(f"https://rupload.facebook.com/video-upload/{V}/{vid}",
                              headers={"Authorization": "OAuth " + tok, "offset": "0", "file_size": str(taille)}, data=data, timeout=900)
            if r.status_code != 200: raise RuntimeError(f"envoi ({r.status_code}) {r.text[:300]}")
            r = requests.post(f"{G}/{page_id}/video_reels", data={"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                                                 "description": legende, "access_token": tok}, timeout=60)
            if r.status_code != 200: raise RuntimeError(f"publication ({r.status_code}) {r.text[:300]}")
            print("✅ Facebook : Reel envoyé (id", vid, ") — Facebook le traite, il apparaît en quelques minutes.")
        except Exception as e: erreurs.append(f"Facebook : {e}")
    if "instagram" in cibles:
        try:
            if not ig.get("id"): raise RuntimeError("aucun compte Instagram relié à la page")
            # vidéo du site (site/…) : Instagram va la chercher lui-même sur solfito.com (l'envoi direct « resumable » échouait)
            url = os.environ.get("VIDEO_URL", "").strip() or ("https://solfito.com/" + fichier[5:] if fichier.startswith("site/") else "")
            if url:
                r = requests.post(f"{G}/{ig['id']}/media", data={"media_type": "REELS", "video_url": url, "caption": legende,
                                                                "share_to_feed": "true", "access_token": tok}, timeout=60)
                if r.status_code != 200: raise RuntimeError(f"création ({r.status_code}) {r.text[:300]}")
                cid = r.json()["id"]
            else:
                r = requests.post(f"{G}/{ig['id']}/media", data={"media_type": "REELS", "upload_type": "resumable", "caption": legende,
                                                                "share_to_feed": "true", "access_token": tok}, timeout=60)
                if r.status_code != 200: raise RuntimeError(f"création ({r.status_code}) {r.text[:300]}")
                cid, uri = r.json()["id"], r.json()["uri"]
                r = requests.post(uri, headers={"Authorization": "OAuth " + tok, "offset": "0", "file_size": str(taille)}, data=data, timeout=900)
                if r.status_code != 200: raise RuntimeError(f"envoi ({r.status_code}) {r.text[:300]}")
            for _ in range(60):   # Instagram prépare la vidéo (jusqu'à ~5 min)
                st = requests.get(f"{G}/{cid}", params={"fields": "status_code,status", "access_token": tok}, timeout=30).json()
                if st.get("status_code") == "FINISHED": break
                if st.get("status_code") == "ERROR": raise RuntimeError(f"traitement : {json.dumps(st)[:300]}")
                time.sleep(5)
            else: raise RuntimeError("traitement trop long (plus de 5 min)")
            r = requests.post(f"{G}/{ig['id']}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
            if r.status_code != 200: raise RuntimeError(f"publication ({r.status_code}) {r.text[:300]}")
            print("✅ Instagram : Reel publié (id", r.json().get("id"), ")")
        except Exception as e: erreurs.append(f"Instagram : {e}")
    if erreurs: stop("Problème : " + " | ".join(erreurs))

if __name__ == "__main__": main()
