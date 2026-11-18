"""Usine à ANECDOTES automatique (dépôt public solfito-robot : minutes gratuites). 1 anecdote par jour, voix « Benjamin », Mélo.
  python outils/usine/anecdotes.py lancer     -> s'il reste moins de 10 anecdotes à venir au planning : voix de 7 anecdotes sur Kaggle (CPU)
  python outils/usine/anecdotes.py recuperer  -> voix finies : rendu des vidéos ICI (Chromium + ffmpeg du runner), videos/anecdote-NNN.mp4,
                                                 planning (1 par jour après la dernière anecdote, type "anecdote"), deja-anecdotes.json
Le code et la banque de 120 anecdotes vraies (src/outils/usine-videos/anecdotes.json) viennent du dépôt privé solfito (src/, secret SOLFITO_PAT).
Secrets : KAGGLE_USERNAME / KAGGLE_KEY. Une anecdote dont une phrase de voix est mal relue par Whisper (< 0,6) est écartée (retentée plus tard)."""
import json, os, sys, shutil, subprocess, datetime
R = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(R, "src", "outils", "usine-videos"); sys.path.insert(0, SRC)
P = os.path.join(R, "outils", "reseaux", "planning.json"); E = os.path.join(R, "outils", "usine", "etat-anecdotes.json")
DEJA = os.path.join(R, "outils", "usine", "deja-anecdotes.json")
PAR_CALCUL, RESERVE, SUFFIXE = 7, 10, "auto"
auj = datetime.date.today()
def charger(p, dflt): return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else dflt
def sauver(p, d): json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
def kg(*a): return subprocess.run([sys.executable, os.path.join(SRC, "kaggle-anecdotes.py"), *a], capture_output=True, text=True, cwd=SRC)
plan = charger(P, []); etat = charger(E, {}); deja = charger(DEJA, [])
anec = [x for x in plan if x.get("type") == "anecdote"]
def jour(x): return datetime.date.fromisoformat(x["date"])

if sys.argv[1] == "lancer":
    if etat.get("lance") and not etat.get("recupere"): print("Calcul déjà en cours depuis", etat["lance"]); sys.exit(0)
    avenir = [x for x in anec if jour(x) >= auj]
    if len(avenir) >= RESERVE: print(f"{len(avenir)} anecdotes à venir : rien à fabriquer."); sys.exit(0)
    import banque
    ids = [a["id"] for a in banque.A if a["id"] not in deja][:PAR_CALCUL]
    if not ids: print("Banque épuisée : écrire de nouvelles anecdotes."); sys.exit(0)
    r = kg("lancer", SUFFIXE, ",".join(ids), "--cpu"); print(r.stdout[-400:], r.stderr[-400:])
    if "hasError\":false" not in r.stdout: print("Lancement refusé."); sys.exit(0)
    etat = {"lance": auj.isoformat(), "ids": ids, "recupere": False}; sauver(E, etat)

elif sys.argv[1] == "recuperer":
    if not etat.get("lance") or etat.get("recupere"): print("Rien en attente."); sys.exit(0)
    st = kg("etat", SUFFIXE).stdout; print(st)
    if '"running"' in st or '"queued"' in st: print("Pas fini."); sys.exit(0)
    import banque
    dest = os.path.join(R, "_voix"); shutil.rmtree(dest, ignore_errors=True)
    r = kg("recuperer", SUFFIXE, dest); print(r.stdout[-500:], r.stderr[-500:])
    ids = etat["ids"]; ajout = 0
    dernier = max([jour(x) for x in anec] + [auj])
    num = {a["id"]: i + 1 for i, a in enumerate(banque.A)}
    for i in ids:
        dv = os.path.join(dest, i); sc = os.path.join(dv, "scores.json")
        if not os.path.exists(sc): print("pas de voix :", i); continue
        pire = min([v["score"] for v in json.load(open(sc, encoding="utf-8")).values()] or [0])
        if pire < 0.6: print("écartée (voix mal relue) :", i, pire); continue
        n = num[i]; f = f"videos/anecdote-{n:03d}.mp4"
        c = subprocess.run([sys.executable, os.path.join(SRC, "fabriquer-anecdotes.py"), str(n), "--voix", dest, "--sortie", os.path.join(R, "_rendu")],
                           capture_output=True, text=True, cwd=SRC, env=dict(os.environ, TEMPO="1.08")); print(c.stdout[-300:], c.stderr[-600:])
        mp4 = os.path.join(R, "_rendu", f"anecdote-{n:02d}.mp4")
        if not os.path.exists(mp4): print("rendu raté :", i); continue
        shutil.copy(mp4, os.path.join(R, f))
        a = banque.A[n - 1]
        q = " ".join(l.replace("**", "") for l in a["q"]).strip(); q = q if q.endswith("?") else q + " ?"
        leg = q + "\n" + a["rep"] + "\n" + " ".join(["#musique", "#anecdote", "#solfito"] + ["#" + t for t in a["tags"]])
        dernier += datetime.timedelta(days=1)
        plan.append({"fichier": f, "date": dernier.isoformat(), "titre": a["titre"], "legende": leg, "type": "anecdote", "fait": {}, "source": a["src"]})
        deja.append(i); ajout += 1
    sauver(P, plan); sauver(DEJA, deja)
    etat["recupere"] = True; etat["ajoutees"] = ajout; sauver(E, etat)
    shutil.rmtree(dest, ignore_errors=True); shutil.rmtree(os.path.join(R, "_rendu"), ignore_errors=True); print("Anecdotes ajoutées :", ajout)
