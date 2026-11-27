"""Search Console : pages et recherches qui amènent le plus de clics (28 derniers jours). Affiche aussi les erreurs."""
import os, json, datetime
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
for nom in ("GSC_SERVICE_ACCOUNT", "GOOGLE_PLAY_JSON"):
    v = os.environ.get(nom, "").strip()
    if not v: print(nom, ": absent"); continue
    info = json.loads(v); print(nom, ":", info.get("client_email"))
    s = AuthorizedSession(service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]))
    print("  sites :", s.get("https://www.googleapis.com/webmasters/v3/sites").json())
    Q = "https://www.googleapis.com/webmasters/v3/sites/sc-domain%3Asolfito.com/searchAnalytics/query"
    auj = datetime.date.today(); d0 = (auj - datetime.timedelta(days=28)).isoformat(); J = auj.isoformat()
    for dims in (["page"], ["query"], ["country"], ["page", "query"]):
        r = s.post(Q, json={"startDate": d0, "endDate": J, "dimensions": dims, "rowLimit": 40}).json()
        if "error" in r: print("  ERREUR", dims, r["error"].get("message")); continue
        print(f"\n== {'+'.join(dims)} ({len(r.get('rows', []))})")
        for x in r.get("rows", []): print(f"  {x['clicks']:4.0f} clics {x['impressions']:6.0f} vues pos {x['position']:5.1f}  {' | '.join(k.replace('https://solfito.com','') for k in x['keys'])}")
