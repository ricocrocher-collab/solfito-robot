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
    import urllib.parse
    sites = [x["siteUrl"] for x in s.get("https://www.googleapis.com/webmasters/v3/sites").json().get("siteEntry", []) if "solfito.com" in x["siteUrl"]]
    if not sites: continue
    Q = "https://www.googleapis.com/webmasters/v3/sites/" + urllib.parse.quote(sites[0], safe="") + "/searchAnalytics/query"
    auj = datetime.date.today(); d0 = (auj - datetime.timedelta(days=28)).isoformat(); J = auj.isoformat()
    for dims in (["page"], ["query"], ["country"], ["page", "query"]):
        r = s.post(Q, json={"startDate": d0, "endDate": J, "dimensions": dims, "rowLimit": 40}).json()
        if "error" in r: print("  ERREUR", dims, r["error"].get("message")); continue
        print(f"\n== {'+'.join(dims)} ({len(r.get('rows', []))})")
        for x in r.get("rows", []): print(f"  {x['clicks']:4.0f} clics {x['impressions']:6.0f} vues pos {x['position']:5.1f}  {' | '.join(k.replace('https://solfito.com','') for k in x['keys'])}")

    # 28 nov. : « presque en 1re page » (positions 6 à 25), triées par affichages : les cibles du travail SEO
    r = s.post(Q, json={"startDate": d0, "endDate": J, "dimensions": ["page", "query"], "rowLimit": 5000}).json()
    rows = [x for x in r.get("rows", []) if 5.5 <= x["position"] <= 25]
    rows.sort(key=lambda x: -x["impressions"])
    print(f"\n== PROCHES DE LA 1re PAGE ({len(rows)} couples page+recherche, 150 premiers)")
    for x in rows[:150]: print(f"  {x['clicks']:4.0f} clics {x['impressions']:6.0f} vues pos {x['position']:5.1f}  {' | '.join(k.replace('https://solfito.com','') for k in x['keys'])}")
    r = s.post(Q, json={"startDate": d0, "endDate": J, "dimensions": ["page"], "rowLimit": 1000}).json()
    rows = sorted(r.get("rows", []), key=lambda x: -x["impressions"])
    print(f"\n== TOUTES LES PAGES PAR AFFICHAGES ({len(rows)}, 120 premières)")
    for x in rows[:120]: print(f"  {x['clicks']:4.0f} clics {x['impressions']:6.0f} vues ctr {100*x['ctr']:4.1f}% pos {x['position']:5.1f}  {x['keys'][0].replace('https://solfito.com','')}")
    break
