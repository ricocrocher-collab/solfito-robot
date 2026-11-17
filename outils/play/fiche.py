"""Envoie la FICHE Google Play d'une langue (titre, descriptions, captures) par l'API, sans toucher aux versions ni à la production.
  python outils/play/fiche.py ja-JP      (textes et captures pris dans src/outils/play/fastlane/metadata/android/<langue>/)
Secret : GOOGLE_PLAY_JSON (compte de service solfito-fiches)."""
import json, os, sys, glob, requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request
L = sys.argv[1]; PKG = "com.solfito.app"
D = os.path.join("src", "outils", "play", "fastlane", "metadata", "android", L)
cr = service_account.Credentials.from_service_account_info(json.loads(os.environ["GOOGLE_PLAY_JSON"]), scopes=["https://www.googleapis.com/auth/androidpublisher"]); cr.refresh(Request())
H = {"Authorization": "Bearer " + cr.token}
A = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PKG}/edits"
U = f"https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/{PKG}/edits"
def ok(r, quoi):
    if r.status_code >= 300: sys.exit(f"{quoi} : {r.status_code} {r.text[:400]}")
    return r.json() if r.text else {}
e = ok(requests.post(A, headers=H, json={}, timeout=60), "ouverture")["id"]
lire = lambda f: open(os.path.join(D, f), encoding="utf-8").read().strip()
ok(requests.put(f"{A}/{e}/listings/{L}", headers=H, json={"language": L, "title": lire("title.txt"), "shortDescription": lire("short_description.txt"),
                "fullDescription": lire("full_description.txt")}, timeout=60), "textes")
caps = sorted(glob.glob(os.path.join(D, "images", "phoneScreenshots", "*.png")))
if caps:
    ok(requests.delete(f"{A}/{e}/listings/{L}/phoneScreenshots", headers=H, timeout=60), "effacer captures")
    for c in caps:
        ok(requests.post(f"{U}/{e}/listings/{L}/phoneScreenshots?uploadType=media", headers={**H, "Content-Type": "image/png"}, data=open(c, "rb").read(), timeout=120), c)
r = requests.post(f"{A}/{e}:commit", headers=H, timeout=60)
if r.status_code >= 300 and "changesNotSentForReview" in r.text:
    r = requests.post(f"{A}/{e}:commit?changesNotSentForReview=true", headers=H, timeout=60)
ok(r, "validation")
print(f"Fiche {L} envoyée : textes + {len(caps)} captures.")
