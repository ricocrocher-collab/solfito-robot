// 27 nov. : compte les textes manquants NOUVEAUX par rapport au passage précédent (precedent/resultats.json, gardé en cache GitHub),
// pour ne prévenir le propriétaire qu'une fois par oubli, pas à chaque mise en ligne. Écrit n=<nombre> dans GITHUB_OUTPUT.
const fs = require('fs'), path = require('path');
const lire = f => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch (e) { return {}; } };
const prec = process.argv[2] || 'precedent', a = lire(path.join(prec, 'resultats.json')), b = lire(path.join(__dirname, 'resultats.json'));
const k = x => typeof x === 'string' ? x : JSON.stringify(x);
let n = 0;
for (const [l, t] of Object.entries(b)) { const vu = new Set((a[l] || []).map(k)); for (const x of t || []) if (!vu.has(k(x))) n++; }
console.log('nouveaux textes manquants :', n);
if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, 'n=' + n + '\n');
fs.mkdirSync(prec, {recursive: true});
if (fs.existsSync(path.join(__dirname, 'resultats.json'))) fs.copyFileSync(path.join(__dirname, 'resultats.json'), path.join(prec, 'resultats.json'));
