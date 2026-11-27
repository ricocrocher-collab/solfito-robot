# Chiffres d'installations App Store (API App Store Connect, clés ASC_* des secrets). Lancé à la main (workflow stats-apple.yml).
import os,time,jwt,requests,gzip,io,datetime as dt
kid,iss,p8=(os.environ.get(k,"").strip() for k in("ASC_KEY_ID","ASC_ISSUER_ID","ASC_KEY_P8"))
vendor=os.environ.get("ASC_VENDOR","").strip()
import re,base64
corps=re.sub(r"-----[A-Z ]*-----|\s","",p8)
try:
  dec=base64.b64decode(corps).decode("utf-8","ignore")
  if "BEGIN PRIVATE KEY" in dec: corps=re.sub(r"-----[A-Z ]*-----|\s","",dec)
except Exception: pass
cle="-----BEGIN PRIVATE KEY-----\n"+"\n".join(corps[i:i+64] for i in range(0,len(corps),64))+"\n-----END PRIVATE KEY-----\n"
tok=jwt.encode({"iss":iss,"iat":int(time.time()),"exp":int(time.time())+1100,"aud":"appstoreconnect-v1"},cle,algorithm="ES256",headers={"kid":kid,"typ":"JWT"})
H={"Authorization":"Bearer "+tok};A="https://api.appstoreconnect.apple.com"
APP="6827552782"
r=requests.get(f"{A}/v1/apps/{APP}",headers=H);print("Appli :",r.status_code,r.json().get("data",{}).get("attributes",{}).get("name") if r.ok else r.text[:200])
if not vendor:
  print("Pas de numéro de fournisseur (ASC_VENDOR) : rapports de ventes impossibles.")
else:
  tot={};pays={}
  for i in range(1,32):
    d=(dt.date.today()-dt.timedelta(days=i)).isoformat()
    r=requests.get(f"{A}/v1/salesReports",headers=H,params={"filter[frequency]":"DAILY","filter[reportType]":"SALES","filter[reportSubType]":"SUMMARY","filter[vendorNumber]":vendor,"filter[reportDate]":d,"filter[version]":"1_0"})
    if r.status_code!=200:
      if i<3: print(d,r.status_code,r.text[:200])
      continue
    lignes=gzip.GzipFile(fileobj=io.BytesIO(r.content)).read().decode().splitlines()
    h=lignes[0].split("\t");n=0
    for l in lignes[1:]:
      c=dict(zip(h,l.split("\t")))
      if c.get("Apple Identifier")!=APP: continue
      # 1 = premier téléchargement, 3 = re-téléchargement, 7 = mise à jour
      if c.get("Product Type Identifier","").startswith(("1","3")):
        u=int(c.get("Units","0") or 0);n+=u;pays[c.get("Country Code")]=pays.get(c.get("Country Code"),0)+u
    tot[d]=n
  print("Téléchargements (1ers + re-téléchargements), 31 derniers jours :",sum(tot.values()))
  for d in sorted(tot):print(" ",d,tot[d])
  print("Pays :",sorted(pays.items(),key=lambda x:-x[1]))
