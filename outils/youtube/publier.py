"""Envoie une vidéo sur la chaîne YouTube Solfito (lancé par .github/workflows/youtube.yml).
Les clés viennent des secrets GitHub YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN (jamais dans un fichier).
Tant que Google n'a pas validé le projet (formulaire yt_api_form), YouTube garde les vidéos en PRIVÉ."""
import json, os, sys, requests

def jeton():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Jeton refusé par Google ({r.status_code}) : {r.json().get('error')} — refaire le refresh token ?")
    return r.json()["access_token"]

def main():
    fichier, titre = os.environ.get("FICHIER", ""), os.environ.get("TITRE", "")
    desc, quand = os.environ.get("DESCRIPTION", ""), os.environ.get("PUBLIER_LE", "").strip()
    statut = os.environ.get("STATUT", "private")
    h = {"Authorization": "Bearer " + jeton()}
    ch = requests.get("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true", headers=h, timeout=30).json()
    if not ch.get("items"):
        sys.exit(f"Aucune chaîne trouvée pour ce compte : {json.dumps(ch)[:300]}")
    print("Chaîne :", ch["items"][0]["snippet"]["title"])
    if not fichier:
        print("Test de connexion OK (aucune vidéo demandée)."); return
    status = {"privacyStatus": statut, "selfDeclaredMadeForKids": False}
    if quand:   # programmation : YouTube exige privé + publishAt (ISO 8601, ex. 2026-11-15T17:30:00+01:00)
        status.update(privacyStatus="private", publishAt=quand)
    meta = {"snippet": {"title": titre[:100], "description": desc, "categoryId": "27",
                        "defaultLanguage": "fr", "tags": ["solfège", "piano", "musique", "Solfito"]},
            "status": status}
    loc = json.loads(os.environ.get("LOCALISATIONS", "") or "{}")   # titres traduits (YouTube les montre dans la langue de chacun)
    if loc: meta["localizations"] = loc
    taille = os.path.getsize(fichier)
    r = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status" + (",localizations" if loc else ""),
                      headers={**h, "Content-Type": "application/json; charset=UTF-8",
                               "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(taille)},
                      data=json.dumps(meta), timeout=60)
    if r.status_code != 200:
        sys.exit(f"Envoi refusé ({r.status_code}) : {r.text[:500]}")
    with open(fichier, "rb") as f:
        r2 = requests.put(r.headers["Location"], headers={**h, "Content-Type": "video/mp4"}, data=f, timeout=900)
    if r2.status_code not in (200, 201):
        sys.exit(f"Envoi de la vidéo refusé ({r2.status_code}) : {r2.text[:500]}")
    v = r2.json()
    print(f"Vidéo envoyée : https://youtu.be/{v['id']}  (statut : {v['status'].get('privacyStatus')}"
          f"{', programmée le ' + v['status']['publishAt'] if v['status'].get('publishAt') else ''})")

main()
