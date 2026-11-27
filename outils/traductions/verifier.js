// Détecteur de français oublié (lancé après chaque mise en ligne, voir .github/workflows/verif-traductions.yml).
// Réutilise les robots de solfito/outils/i18n/robots/ (ecrans, boutons, joueur) : on en copie le code dans un dossier temporaire
// en changeant seulement l'adresse du serveur local et le chemin du dépôt, puis on lit ce qu'ils notent.
// Usage : node verifier.js [langues...]   (défaut : en es pt de it ja ko zh ar)   Variables : SRC (dépôt solfito, défaut ../../src), PORT (8765)
// Sortie : rapport.txt (vide si rien) + code de sortie 0 (rien) / 3 (textes manquants) / 1 (le robot lui-même a planté).
const fs = require('fs'), path = require('path'), {spawn, spawnSync} = require('child_process');
const SRC = path.resolve(process.env.SRC || path.join(__dirname, '..', '..', 'src'));
const PORT = process.env.PORT || '8765';
const LANGS = process.argv.slice(2).length ? process.argv.slice(2) : ['en', 'es', 'pt', 'de', 'it', 'ja', 'ko', 'zh', 'ar'];
const NOMS = {en: 'anglais', es: 'espagnol', pt: 'portugais', de: 'allemand', it: 'italien', ja: 'japonais', ko: 'coréen', zh: 'chinois', ar: 'arabe'};
const PAR = +(process.env.PARALLELE || 3), LIMITE_MS = +(process.env.LIMITE_MIN || 12) * 60000;
const ROB = path.join(SRC, 'outils', 'i18n', 'robots'), TMP = path.join(__dirname, '.tmp');
fs.rmSync(TMP, {recursive: true, force: true}); fs.mkdirSync(TMP, {recursive: true});
for (const f of ['robot-ecrans.js', 'robot-boutons.js', 'robot-joueur.js']) {
  if (!fs.existsSync(path.join(ROB, f))) { console.error('robot introuvable : ' + f); process.exit(1); }
  fs.writeFileSync(path.join(TMP, f), fs.readFileSync(path.join(ROB, f), 'utf8')
    .split('http://localhost:8765').join('http://localhost:' + PORT).split('/home/user/solfito/').join(SRC + '/'));
}
// ---- anti-bruit : on garde seulement ce qui ressemble vraiment à du français ----
const NOTE = /^(do|ré|re|mi|fa|sol|la|si|[a-g])\s*[#♯♭b]?\s*\d*$/i;
const FRANC = /[àâçéèêëîïôûùüœ«»]|(^|[\s'’(])(le|la|les|des|du|une|un|et|est|pour|avec|tu|ton|ta|tes|pas|sur|dans|de|ce|cette|vous|nous|ou|que|qui|ne|plus|mon|ma|mes)(?=$|[\s,.!?:;'’)])/i;
function garde(t, L) {
  t = String(t).replace(/\s+/g, ' ').trim();
  let s = t.replace(/solfito|m[ée]lo|[0-9]+|[♯♭#%+\-–—·•×x/:.,;!?()'’"«»]/gi, ' ').replace(/\s+/g, ' ').trim();
  if (s.length < 4 || NOTE.test(s) || /^(fran[cç]ais|portugu[eê]s|english|espa[nñ]ol|deutsch|italiano)$/i.test(s)) return null;   // noms des langues (sélecteur de langue)
  if (!/[a-zàâçéèêëîïôûùüœ]{3,}/i.test(s)) return null;
  if (['ja', 'ko', 'zh', 'ar'].includes(L) && /[؀-ۿ぀-ヿ㐀-鿿가-힯]/.test(t)) return null; // phrase déjà dans la langue (mélange : trop bruyant)
  if (!FRANC.test(s)) return null;
  return t.slice(0, 110);
}
const lance = (f, args, cwd, ms) => new Promise(res => {
  const p = spawn('node', [path.join(TMP, f), ...args], {cwd, stdio: ['ignore', 'pipe', 'pipe'], env: {...process.env, NODE_PATH: [process.env.NODE_PATH, path.join(__dirname, '..', '..', 'node_modules'), '/opt/node-tools/node_modules'].filter(Boolean).join(path.delimiter)}});
  let err = ''; p.stderr.on('data', d => { err += d; if (err.length > 4000) err = err.slice(-2000); });
  const t = setTimeout(() => { p.kill('SIGKILL'); }, ms);
  p.on('close', c => { clearTimeout(t); res({code: c, err}); });
});
const lis = (f, def) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (e) { return def; } };
(async () => {
  // serveur local sur site/
  const srv = spawn('python3', ['-m', 'http.server', PORT, '--bind', '127.0.0.1'], {cwd: path.join(SRC, 'site'), stdio: 'ignore'});
  await new Promise(r => setTimeout(r, 1500));
  const debut = Date.now(), res = {}, pannes = [];
  const file = [...LANGS];
  const worker = async () => {
    while (file.length) {
      const L = file.shift(), d = path.join(TMP, L); fs.mkdirSync(d, {recursive: true});
      const reste = () => Math.max(20000, (LIMITE_MS - (Date.now() - debut)) / 2);
      const a = await lance('robot-ecrans.js', [L], d, reste());
      const b = await lance('robot-boutons.js', [L, 'prem'], d, reste());
      const c = await lance('robot-joueur.js', [L], TMP, reste());   // écrit joueur-<L>.txt à côté du script
      if (a.code || b.code || c.code) pannes.push(`${L} (${[a, b, c].map(x => x.code).join('/')})`);
      const tous = new Set();
      for (const k of lis(path.join(d, `manque-${L}.json`), [])) tous.add(k);
      for (const k of lis(path.join(d, `manque2-${L}-prem.json`), [])) tous.add(k);
      try { for (const l of fs.readFileSync(path.join(TMP, `joueur-${L}.txt`), 'utf8').split('\n')) if (l && !l.startsWith('---')) tous.add(l); } catch (e) {}
      res[L] = [...new Set([...tous].map(t => garde(t, L)).filter(Boolean))];
      console.log(`${L} : ${res[L].length} texte(s) en français`);
    }
  };
  await Promise.all(Array.from({length: PAR}, worker));
  srv.kill();
  const total = Object.values(res).reduce((n, a) => n + a.length, 0);
  fs.writeFileSync(path.join(__dirname, 'resultats.json'), JSON.stringify(res, null, 1));
  // ---- rapport court, français simple, 30 lignes max ----
  let rapport = '';
  if (total) {
    const lignes = [`Traductions : ${total} texte(s) restent en français après la mise en ligne.`];
    const langs = LANGS.filter(l => res[l] && res[l].length);
    lignes.push('Langues touchées : ' + langs.map(l => `${NOMS[l] || l} (${res[l].length})`).join(', ') + '.');
    const dispo = 30 - lignes.length - 1;
    const par = Math.max(1, Math.floor(dispo / langs.length));
    for (const l of langs) {
      res[l].slice(0, par).forEach(t => lignes.push(`[${l}] ${t}`));
      if (lignes.length >= 29) break;
    }
    const vus = lignes.filter(x => x.startsWith('[')).length;
    if (vus < total) lignes.push(`… et ${total - vus} autre(s) (liste complète dans le journal de l'action).`);
    rapport = lignes.slice(0, 30).join('\n') + '\n';
  }
  fs.writeFileSync(path.join(__dirname, 'rapport.txt'), rapport);
  if (rapport) console.log('\n' + rapport);
  if (pannes.length) console.log('Robots en erreur (résultat peut-être incomplet) : ' + pannes.join(', '));
  if (!total && pannes.length === LANGS.length) process.exit(1);   // tout a planté : ce n'est pas « 0 manquant »
  process.exit(total ? 3 : 0);
})();
