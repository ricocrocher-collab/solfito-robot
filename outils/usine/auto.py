"""Usine à vidéos AUTOMATIQUE (dépôt public solfito-robot, minutes gratuites).
  python outils/usine/auto.py lancer      -> s'il reste moins de RESERVE jours de vidéos au planning : 2 calculs Kaggle (2 x 7 vidéos)
  python outils/usine/auto.py recuperer   -> quand les calculs sont finis : vidéos dans videos/NNN.mp4 + planning (2 par jour à la suite)
Le code de l'usine vient du dépôt privé solfito (copié dans src/ par le workflow, secret SOLFITO_PAT).
Secrets : KAGGLE_USERNAME / KAGGLE_KEY. Une vidéo dont une phrase de voix est mal relue par Whisper (< 0,6) est écartée."""
import json, os, sys, glob, shutil, subprocess, datetime
R = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(R, "src", "outils", "usine-videos")
P = os.path.join(R, "outils", "reseaux", "planning.json"); E = os.path.join(R, "outils", "usine", "etat.json")
DEJA = os.path.join(R, "outils", "usine", "deja.json")
PARTS, PAR_CALCUL, RESERVE = 2, 7, 12
plan = json.load(open(P, encoding="utf-8")); etat = json.load(open(E)) if os.path.exists(E) else {}
auj = datetime.date.today()
def k(*a): return subprocess.run([sys.executable, os.path.join(SRC, "kaggle.py"), *a], capture_output=True, text=True, cwd=os.path.join(R, "src"))
def sauver(): json.dump(etat, open(E, "w"), indent=1)

if sys.argv[1] == "lancer":
    derniere = max(datetime.date.fromisoformat(x["date"]) for x in plan)
    if etat.get("lance") and not etat.get("recupere"): print("Calculs déjà en cours depuis", etat["lance"]); sys.exit(0)
    if (derniere - auj).days >= RESERVE: print(f"Encore {(derniere - auj).days} jours de vidéos : rien à fabriquer."); sys.exit(0)
    shutil.copy(DEJA, os.path.join(SRC, "deja.json"))
    for i in range(PARTS):
        r = k("lancer", "--nombre", str(PAR_CALCUL), "--type", "hasard", "--cpu", "--part", f"{i}/{PARTS}"); print(r.stdout[-400:], r.stderr[-400:])
    etat = {"lance": auj.isoformat(), "recupere": False}; sauver()

elif sys.argv[1] == "recuperer":
    if not etat.get("lance") or etat.get("recupere"): print("Rien en attente."); sys.exit(0)
    st = [k("etat", str(i)).stdout for i in range(PARTS)]; print(st)
    if any('"running"' in s or '"queued"' in s for s in st): print("Pas fini."); sys.exit(0)
    shutil.copy(DEJA, os.path.join(SRC, "deja.json"))
    for i in range(PARTS): r = k("recuperer", str(i)); print(r.stdout[-1500:], r.stderr[-400:])
    shutil.copy(os.path.join(SRC, "deja.json"), DEJA)
    num = max([int(os.path.basename(x["fichier"])[:-4]) for x in plan if os.path.basename(x["fichier"])[:-4].isdigit()] + [0])
    jour = max(datetime.date.fromisoformat(x["date"]) for x in plan); jour = max(jour, auj)
    par_jour = {}
    for x in plan: par_jour[x["date"]] = par_jour.get(x["date"], 0) + 1
    ajout = 0
    for d in sorted(glob.glob(os.path.join(SRC, "sortie", "kaggle-*", "*", "video.mp4"))):
        dos = os.path.dirname(d); i = json.load(open(os.path.join(dos, "infos.json"), encoding="utf-8"))
        sc = os.path.join(dos, "voix", "scores.json")
        if os.path.exists(sc) and min([v["score"] for v in json.load(open(sc, encoding="utf-8")).values()] or [1]) < 0.6:
            print("écartée (voix) :", i["id"]); continue
        while par_jour.get(jour.isoformat(), 0) >= 2: jour += datetime.timedelta(days=1)
        num += 1; f = f"videos/{num:03d}.mp4"; shutil.copy(d, os.path.join(R, f))
        plan.append({"fichier": f, "date": jour.isoformat(), "titre": i["titre"], "legende": i["legende"], "attendu": i.get("noms", []), "fait": {}, "source": "usine-auto " + i["id"]})
        par_jour[jour.isoformat()] = par_jour.get(jour.isoformat(), 0) + 1; ajout += 1
    json.dump(plan, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    etat["recupere"] = True; etat["ajoutees"] = ajout; sauver(); print("Vidéos ajoutées :", ajout)
