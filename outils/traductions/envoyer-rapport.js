// Envoie le résultat dans l'onglet Admin (même canal que stats.yml : fonction Supabase stats-robot, jeton OIDC de GitHub, aucune clé).
// Seulement s'il manque des textes (resultats.json). Ne fait jamais échouer le workflow.
const fs = require('fs'), path = require('path');
(async () => {
  try {
    const res = JSON.parse(fs.readFileSync(path.join(__dirname, 'resultats.json'), 'utf8'));
    const jour = new Date().toISOString().slice(0, 10), L = [];
    for (const [l, a] of Object.entries(res)) if (a.length) L.push({jour, source: 'traductions', cle: 'manquants-' + l, valeur: a.length, detail: a.slice(0, 15)});
    if (!L.length) return console.log('Rien à envoyer.');
    const u = process.env.ACTIONS_ID_TOKEN_REQUEST_URL; if (!u) return console.log('Pas de jeton OIDC (exécution locale).');
    const o = (await (await fetch(u + '&audience=solfito-stats', {headers: {Authorization: 'Bearer ' + process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN}})).json()).value;
    const r = await fetch('https://lskljjzijrtmakbinecr.supabase.co/functions/v1/stats-robot', {method: 'POST', headers: {Authorization: 'Bearer ' + o, 'Content-Type': 'application/json'}, body: JSON.stringify(L)});
    console.log('Supabase :', r.status, (await r.text()).slice(0, 200));
  } catch (e) { console.log('Envoi impossible :', e.message); }
})();
