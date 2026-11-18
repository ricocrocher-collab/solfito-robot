"""Usine à TUTOS piano (Synthesia néon) AUTOMATIQUE (dépôt public solfito-robot, minutes gratuites).
  python outils/usine/tutos.py          -> s'il reste moins de 10 tutos à venir au planning : fabrique 7 tutos (extraits du domaine public jamais utilisés),
                                           les range dans videos/tuto-NNN.mp4, les ajoute au planning (1 par jour après le dernier) et recopie deja-tutos.json.
Variables : TUTOS_FORCER=1 (fabrique même s'il reste des tutos), TUTOS_NOMBRE=7, TUTOS_MINI=10.
Le code vient du dépôt privé solfito (copié dans src/ par le workflow, secret SOLFITO_PAT). Aucune clé ici."""
import json, os, re, sys, shutil, subprocess, datetime, tempfile
R = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(R, "src", "outils", "usine-videos")
P = os.path.join(R, "outils", "reseaux", "planning.json")
DEJA = os.path.join(R, "outils", "usine", "deja-tutos.json")     # source de vérité côté robot
NOMBRE = int(os.environ.get("TUTOS_NOMBRE", "7")); MINI = int(os.environ.get("TUTOS_MINI", "10")); FORCER = os.environ.get("TUTOS_FORCER") == "1"
plan = json.load(open(P, encoding="utf-8")); auj = datetime.date.today()
def tuto(x): return x.get("type") == "tuto"
a_venir = [x for x in plan if tuto(x) and datetime.date.fromisoformat(x["date"]) >= auj]
print(f"Tutos à venir au planning : {len(a_venir)}")
if len(a_venir) >= MINI and not FORCER: print("Assez de tutos : rien à fabriquer."); sys.exit(0)
if not os.path.isdir(SRC): sys.exit("src/outils/usine-videos manquant (checkout de solfito)")

deja_src = os.path.join(SRC, "deja-tutos.json")
if os.path.exists(DEJA): shutil.copy(DEJA, deja_src)             # sinon : le fichier de départ de solfito sert d'amorce
tmp = tempfile.mkdtemp(prefix="tutos-"); infos_json = os.path.join(tmp, "infos.json")
env = dict(os.environ)
if not env.get("NODE_PATH"): env["NODE_PATH"] = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
r = subprocess.run([sys.executable, os.path.join(SRC, "tutos-auto.py"), str(NOMBRE), "--sortie", tmp, "--deja", deja_src, "--json", infos_json, "--tmp", os.path.join(tmp, "w")], env=env)
if os.path.exists(infos_json): infos = json.load(open(infos_json, encoding="utf-8"))
else: infos = []
shutil.copy(deja_src, DEJA)       # même si le calcul s'arrête en route, ce qui est fait est noté

os.makedirs(os.path.join(R, "videos"), exist_ok=True)
num = max([int(m.group(1)) for f in os.listdir(os.path.join(R, "videos")) if (m := re.fullmatch(r"tuto-(\d+)\.mp4", f))] + [0])
jour = max([datetime.date.fromisoformat(x["date"]) for x in plan if tuto(x)] + [auj - datetime.timedelta(days=1)]) + datetime.timedelta(days=1)
jour = max(jour, auj)
for i in infos:
    if not os.path.exists(i["fichier"]) or os.path.getsize(i["fichier"]) < 100_000: print("vidéo ignorée :", i["morceau"]); continue
    num += 1; f = f"videos/tuto-{num:03d}.mp4"; shutil.copy(i["fichier"], os.path.join(R, f))
    plan.append({"fichier": f, "date": jour.isoformat(), "titre": i["titre"], "legende": i["legende"], "type": "tuto", "fait": {},
                 "source": f"{i['morceau']} — {i['compositeur']} (domaine public)"})
    print("ajouté :", f, jour, i["titre"]); jour += datetime.timedelta(days=1)
json.dump(plan, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(r.returncode)
