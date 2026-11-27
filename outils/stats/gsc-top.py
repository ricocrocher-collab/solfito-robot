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

    # ---- Opportunités : (page, recherche) presque en 1re page, et pages vues mais peu cliquées ----
    r = s.post(Q, json={"startDate": d0, "endDate": J, "dimensions": ["page", "query"], "rowLimit": 5000}).json()
    rows = r.get("rows", [])
    print(f"\n== OPPORTUNITES page+query, position 7-20, >= 5 vues ({len(rows)} lignes au total)")
    op = sorted([x for x in rows if 7 <= x["position"] <= 20 and x["impressions"] >= 5], key=lambda x: -x["impressions"])
    for x in op[:150]:
        p, q = x["keys"]; print(f"OP\t{x['impressions']:.0f}\t{x['clicks']:.0f}\t{x['position']:.1f}\t{p.replace('https://solfito.com','')}\t{q}")
    r = s.post(Q, json={"startDate": d0, "endDate": J, "dimensions": ["page"], "rowLimit": 1000}).json()
    print("\n== PAGES >= 40 vues, taux de clic < 1,5 %")
    for x in sorted(r.get("rows", []), key=lambda x: -x["impressions"]):
        if x["impressions"] >= 40 and x["ctr"] < 0.015:
            print(f"CTR\t{x['impressions']:.0f}\t{x['clicks']:.0f}\t{x['ctr']*100:.1f}%\t{x['position']:.1f}\t{x['keys'][0].replace('https://solfito.com','')}")
    break
