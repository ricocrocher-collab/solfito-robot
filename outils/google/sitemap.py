# Après chaque mise en ligne : dit à Google « le plan du site a changé, viens le relire » (Search Console, sitemaps.submit).
# Compte de service GOOGLE_PLAY_JSON (solfito-fiches@…), droit « Complet » dans Search Console depuis le 27 nov.
# Google relit alors les pages dont la date <lastmod> a changé. (L'API Indexing n'est PAS utilisée : réservée aux offres d'emploi.)
import json, os, sys, urllib.parse
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
cle = os.environ.get("GOOGLE_PLAY_JSON", "").strip()
if not cle: print("Pas de compte de service : rien à faire"); sys.exit(0)
s = AuthorizedSession(service_account.Credentials.from_service_account_info(json.loads(cle), scopes=["https://www.googleapis.com/auth/webmasters"]))
q = lambda x: urllib.parse.quote(x, safe="")
sites = [x["siteUrl"] for x in s.get("https://www.googleapis.com/webmasters/v3/sites").json().get("siteEntry", []) if "solfito.com" in x["siteUrl"]]
site = sites[0] if sites else "https://solfito.com/"
r = s.put(f"https://www.googleapis.com/webmasters/v3/sites/{q(site)}/sitemaps/{q('https://solfito.com/sitemap.xml')}")
print("Plan du site envoyé à Google :", r.status_code, r.text[:300] or "OK")
if r.status_code == 403: print("→ le compte de service doit avoir le droit « Complet » dans Search Console")
sys.exit(0 if r.ok else 1)
