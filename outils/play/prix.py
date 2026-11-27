"""Prix Premium Google Play adaptés au niveau de vie de chaque pays (abonnements Solfito).
  python outils/play/prix.py voir        -> affiche les prix actuels (ne change rien)
  python outils/play/prix.py appliquer   -> baisse les prix des pays moins riches (seulement les NOUVEAUX abonnés ;
                                            les abonnés actuels gardent leur prix, règle Google)
Méthode : prix de la France converti par Google dans chaque monnaie (convertRegionPrices), puis multiplié par
un coefficient selon le pays (COEF ci-dessous). Les pays riches ne changent pas. Jamais de hausse.
Secret : GOOGLE_PLAY_JSON (compte de service, droit « Gérer les commandes et les abonnements »)."""
import json, os, sys, math, requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request
MODE = sys.argv[1] if len(sys.argv) > 1 else "voir"; PKG = "com.solfito.app"
cr = service_account.Credentials.from_service_account_info(json.loads(os.environ["GOOGLE_PLAY_JSON"]), scopes=["https://www.googleapis.com/auth/androidpublisher"]); cr.refresh(Request())
H = {"Authorization": "Bearer " + cr.token}
B = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PKG}"
# Coefficients (1 = prix de la France converti). 0,4 : pays à faible revenu ; 0,55 : revenu intermédiaire ; 0,75 : Europe de l'Est / sud.
C40 = "IN ID PK BD EG NG KE GH VN PH LK NP MA DZ TN UA ET TZ UG CM CI SN BO PY NI HN GT SV MM KH LA UZ KZ KG TJ GE AM AZ MN JO IQ".split()
C55 = "BR MX CO AR PE CL EC TR ZA TH MY RS BA MK AL ME MD BY DO CR PA JM UY VE SA OM".split()
C75 = "PL HU RO BG HR CZ SK SI LT LV EE PT GR CY MT TW KR".split()
COEF = {**{c: .4 for c in C40}, **{c: .55 for c in C55}, **{c: .75 for c in C75}}
def ok(r, quoi):
    if r.status_code >= 300: sys.exit(f"{quoi} : {r.status_code} {r.text[:500]}")
    return r.json() if r.text else {}
def money(units, nanos): return int(units or 0) + (nanos or 0) / 1e9
def mk(cur, v):
    u = math.floor(v); n = int(round((v - u) * 1e9)); return {"currencyCode": cur, "units": str(u), "nanos": n}
def arrondi(v, cur):
    # Prix « propres » : sans centimes pour les monnaies à gros chiffres, sinon .99
    if v >= 1000: return float(round(v, -1 if v < 10000 else -2))
    if v >= 100 or cur in ("JPY", "KRW", "IDR", "VND", "CLP", "COP", "PYG", "HUF", "UGX", "TZS", "KZT", "MNT", "LAK", "KHR", "MMK", "UZS", "NGN", "PKR", "LKR", "INR"): return float(max(1, round(v)))
    return max(0.99, math.floor(v) + 0.99 if v - math.floor(v) > 0.5 else math.floor(v) - 0.01) if v > 1 else round(v, 2)
subs = ok(requests.get(f"{B}/subscriptions", headers=H, timeout=60), "liste").get("subscriptions", [])
print(f"{len(subs)} abonnement(s)")
for s in subs:
    pid = s["productId"]; chg = False
    for bp in s.get("basePlans", []):
        rc = {r["regionCode"]: r for r in bp.get("regionalConfigs", [])}
        fr = rc.get("FR")
        if not fr: print(f"  {pid}/{bp['basePlanId']} : pas de prix France, ignoré"); continue
        e = money(fr["price"].get("units"), fr["price"].get("nanos"))
        print(f"\n{pid}/{bp['basePlanId']} ({bp.get('state')}) : France {e:.2f} EUR, {len(rc)} pays")
        conv = ok(requests.post(f"{B}/pricing:convertRegionPrices", headers=H, json={"price": mk("EUR", e)}, timeout=60), "conversion").get("convertedRegionPrices", {})
        for cc, r in sorted(rc.items()):
            if cc not in COEF or cc not in conv: continue
            cur = r["price"]["currencyCode"]; avant = money(r["price"].get("units"), r["price"].get("nanos"))
            cp = conv[cc]["price"]
            if cp["currencyCode"] != cur: print(f"   {cc} : monnaie différente ({cur} / {cp['currencyCode']}), ignoré"); continue
            cible = arrondi(money(cp.get("units"), cp.get("nanos")) * COEF[cc], cur)
            if cible >= avant * 0.97: continue   # jamais de hausse, pas de micro-changement
            print(f"   {cc} : {avant:g} -> {cible:g} {cur} (x{COEF[cc]})")
            r["price"] = mk(cur, cible); chg = True
    if chg and MODE == "appliquer":
        # version de la liste des pays de Google : on essaie de la plus récente à la plus ancienne
        for ver in ["2026/01", "2025/07", "2025/03", "2025/01", "2024/07", "2024/01", "2023/07", "2023/01", "2022/02"]:
            r = requests.patch(f"{B}/subscriptions/{pid}", headers=H, params={"updateMask": "basePlans", "regionsVersion.version": ver, "latencyTolerance": "PRODUCT_UPDATE_LATENCY_TOLERANCE_LATENCY_TOLERANT"}, json=s, timeout=120)
            if r.status_code < 300: print(f"  -> {pid} mis à jour (pays {ver})"); break
            if "version" in r.text.lower(): print(f"   (pays {ver} : {r.json().get('error',{}).get('message','')[:120]})"); continue
            ok(r, f"mise à jour {pid}")
        else: sys.exit(f"aucune version des pays acceptée pour {pid}")
print("\nMode :", MODE, "(rien n'a été changé)" if MODE != "appliquer" else "")
