#!/usr/bin/env node
/**
 * ig-sync.js — Synchronise les transactions IG avec Firebase
 *
 * Récupère les 3 derniers jours de transactions via l'API REST IG,
 * convertit au format du Dashboard, fusionne avec les données existantes
 * dans Firebase (avec détection des doublons par référence IG).
 *
 * Usage : node ig-sync.js
 * Prérequis : fichier .env avec IG_API_KEY, IG_USERNAME, IG_PASSWORD, IG_ACCOUNT_ID
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

// ── Charger .env ──
const envPath = path.join(__dirname, '.env');
if (!fs.existsSync(envPath)) { console.error('❌ Fichier .env introuvable'); process.exit(1); }
const envLines = fs.readFileSync(envPath, 'utf8').split('\n');
const env = {};
envLines.forEach(line => {
  const [k, ...v] = line.split('=');
  if (k && v.length) env[k.trim()] = v.join('=').trim();
});

const IG_API_KEY  = env.IG_API_KEY;
const IG_USERNAME = env.IG_USERNAME;
const IG_PASSWORD = env.IG_PASSWORD;
const IG_ACCOUNT  = env.IG_ACCOUNT_ID;

if (!IG_API_KEY || !IG_USERNAME || !IG_PASSWORD) {
  console.error('❌ Remplis IG_API_KEY, IG_USERNAME et IG_PASSWORD dans .env');
  process.exit(1);
}

// ── Firebase REST config ──
const FB_DB_URL = 'https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com';

// ── Helpers HTTP ──
function request(options, body) {
  return new Promise((resolve, reject) => {
    const req = https.request(options, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (res.statusCode >= 400) {
            reject(new Error(`HTTP ${res.statusCode}: ${json.errorCode || JSON.stringify(json)}`));
          } else {
            resolve({ headers: res.headers, body: json });
          }
        } catch (e) {
          reject(new Error(`Parse error: ${data.substring(0, 200)}`));
        }
      });
    });
    req.on('error', reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

function firebaseGet(path) {
  return new Promise((resolve, reject) => {
    https.get(`${FB_DB_URL}${path}.json`, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => { try { resolve(JSON.parse(data)); } catch(e) { reject(e); } });
    }).on('error', reject);
  });
}

function firebasePut(fbPath, data) {
  const url = new URL(`${FB_DB_URL}${fbPath}.json`);
  return new Promise((resolve, reject) => {
    const req = https.request({ hostname: url.hostname, path: url.pathname + url.search, method: 'PUT',
      headers: { 'Content-Type': 'application/json' }
    }, res => {
      let d = '';
      res.on('data', chunk => d += chunk);
      res.on('end', () => resolve(d));
    });
    req.on('error', reject);
    req.write(JSON.stringify(data));
    req.end();
  });
}

// ── IG API ──
async function igLogin() {
  console.log('🔑 Connexion à l\'API IG...');
  const res = await request({
    hostname: 'api.ig.com',
    path: '/gateway/deal/session',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json; charset=UTF-8',
      'X-IG-API-KEY': IG_API_KEY,
      'Version': '2'
    }
  }, {
    identifier: IG_USERNAME,
    password: IG_PASSWORD
  });

  const cst = res.headers['cst'];
  const securityToken = res.headers['x-security-token'];
  if (!cst || !securityToken) throw new Error('Tokens de session manquants');

  // Changer de compte si nécessaire
  const currentAccount = res.body.currentAccountId;
  if (IG_ACCOUNT && currentAccount !== IG_ACCOUNT) {
    console.log(`  Changement vers le compte ${IG_ACCOUNT}...`);
    await request({
      hostname: 'api.ig.com',
      path: '/gateway/deal/session',
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json; charset=UTF-8',
        'X-IG-API-KEY': IG_API_KEY,
        'CST': cst,
        'X-SECURITY-TOKEN': securityToken,
        'Version': '1'
      }
    }, { accountId: IG_ACCOUNT, defaultAccount: false });
  }

  console.log('  ✅ Connecté (compte: ' + (IG_ACCOUNT || currentAccount) + ')');
  return { cst, securityToken };
}

async function igGetTransactions(session, fromDate, toDate) {
  console.log(`📥 Récupération des transactions du ${fromDate} au ${toDate}...`);
  const from = fromDate + 'T00:00:00';
  const to   = toDate   + 'T23:59:59';
  const res = await request({
    hostname: 'api.ig.com',
    path: `/gateway/deal/history/transactions?from=${from}&to=${to}&type=ALL&pageSize=500`,
    method: 'GET',
    headers: {
      'Accept': 'application/json; charset=UTF-8',
      'X-IG-API-KEY': IG_API_KEY,
      'CST': session.cst,
      'X-SECURITY-TOKEN': session.securityToken,
      'Version': '2'
    }
  });
  const txs = res.body.transactions || [];
  console.log(`  ✅ ${txs.length} transaction(s) récupérée(s)`);
  return txs;
}

// ── Conversion API → format Dashboard ──
function mapMarketName(name) {
  if (!name) return name;
  const n = name.toLowerCase();
  if (n.includes('us tech 100') || n.includes('nasdaq')) return 'NASDAQ';
  if (n.includes('allemagne 40') || n.includes('germany 40') || n.includes('dax')) return 'DAX';
  return name;
}

function parsePL(plStr) {
  // "€-108.38" ou "€2,000.00" → nombre
  if (!plStr) return 0;
  const cleaned = plStr.replace(/[^0-9.\-]/g, '');
  return parseFloat(cleaned) || 0;
}

function convertTransactions(txs) {
  const trades = [];
  const dividends = [];
  const deposits = [];
  const fees = [];

  for (const tx of txs) {
    const amount = parsePL(tx.profitAndLoss);
    if (isNaN(amount)) continue;

    const dateUtc = tx.dateUtc || tx.date || '';
    if (!dateUtc || dateUtc.length < 10) continue;
    const dateStr = dateUtc.substring(0, 10);
    const ref = tx.reference || '';
    const txType = (tx.transactionType || '').toUpperCase();
    const market = tx.instrumentName || '';

    if (txType === 'DEPO' || txType === 'DEPOSIT') {
      // Intérêts de financement CFD → dividende
      if (/int[eé]r[eê]t\s+(de\s+)?financement/i.test(market)) {
        dividends.push({ date: dateStr, amount, ref, market });
        continue;
      }
      deposits.push({ date: dateStr, amount, ref });
      continue;
    }

    if (txType === 'DIVIDEND') {
      dividends.push({ date: dateStr, amount, ref, market });
      continue;
    }

    if (txType !== 'ORDRE' && txType !== 'TRADE' && txType !== 'DEAL') {
      fees.push({ date: dateStr, amount, ref, type: txType, market });
      continue;
    }

    // ── TRADE ──
    const symbol = mapMarketName(market);
    const size = tx.size ? parseFloat(tx.size) : 0;
    const openLevel = tx.openLevel ? parseFloat(tx.openLevel) : 0;
    const closeLevel = tx.closeLevel ? parseFloat(tx.closeLevel) : 0;
    const openDate = tx.openDateUtc || '';

    // Date du trade = date d'ouverture si disponible
    const tradeDate = openDate && openDate.length >= 10 ? openDate.substring(0, 10) : dateStr;

    trades.push({
      date: tradeDate,
      symbol,
      gain: amount,
      ref,
      size,
      openLevel,
      closeLevel,
      openDate,
      closeDate: dateUtc
    });
  }

  return { trades, dividends, deposits, fees };
}

// ── Merge avec Firebase ──
function tradeKey(t) {
  if (t.ref) return t.ref;
  const sym = t.symbol.trim().replace(/\s+/g, ' ').toLowerCase();
  return t.date + '|' + sym + '|' + t.gain.toFixed(2);
}

async function mergeWithFirebase(newData) {
  console.log('🔄 Fusion avec Firebase...');

  // Charger données existantes
  const [existingTradesRaw, existingDivs, existingDeps, existingFees] = await Promise.all([
    firebaseGet('/trades'),
    firebaseGet('/dividends'),
    firebaseGet('/deposits'),
    firebaseGet('/fees')
  ]);

  // Convertir trades existants
  let existingTrades = [];
  if (existingTradesRaw) {
    const arr = Array.isArray(existingTradesRaw) ? existingTradesRaw : Object.values(existingTradesRaw);
    existingTrades = arr.map(t => ({
      date: t.date, symbol: t.symbol, gain: t.gain,
      ref: t.ref || '', size: t.size || 0,
      openLevel: t.openLevel || 0, closeLevel: t.closeLevel || 0,
      openDate: t.openDate || '', closeDate: t.closeDate || ''
    }));
  }

  // Merge trades (détection doublons par ref/tradeKey, mise à jour date si changée)
  const existingByKey = {};
  existingTrades.forEach(t => { existingByKey[tradeKey(t)] = t; });

  let newCount = 0, updatedCount = 0, dupCount = 0;
  for (const t of newData.trades) {
    const key = tradeKey(t);
    const existing = existingByKey[key];
    if (existing) {
      // Mise à jour date d'ouverture si elle a changé
      if (existing.date !== t.date) { existing.date = t.date; updatedCount++; }
      else dupCount++;
    } else {
      existingTrades.push(t);
      existingByKey[key] = t;
      newCount++;
    }
  }

  // Trier par date décroissante
  existingTrades.sort((a, b) => b.date.localeCompare(a.date));

  // Merge dividendes
  const divArr = Array.isArray(existingDivs) ? existingDivs : (existingDivs ? Object.values(existingDivs) : []);
  const divRefs = new Set(divArr.map(d => d.ref));
  const newDivs = newData.dividends.filter(d => !divRefs.has(d.ref));
  const mergedDivs = [...divArr, ...newDivs];

  // Merge dépôts
  const depArr = Array.isArray(existingDeps) ? existingDeps : (existingDeps ? Object.values(existingDeps) : []);
  // Retirer dépôts reclassés en dividendes
  const newDivRefSet = new Set(newData.dividends.map(d => d.ref));
  const filteredDeps = depArr.filter(d => !newDivRefSet.has(d.ref));
  const depRefs = new Set(filteredDeps.map(d => d.ref));
  const newDeps = newData.deposits.filter(d => !depRefs.has(d.ref));
  const mergedDeps = [...filteredDeps, ...newDeps];

  // Merge frais
  const feeArr = Array.isArray(existingFees) ? existingFees : (existingFees ? Object.values(existingFees) : []);
  const feeRefs = new Set(feeArr.map(f => f.ref));
  const newFees = newData.fees.filter(f => !feeRefs.has(f.ref));
  const mergedFees = [...feeArr, ...newFees];

  // Sauvegarder dans Firebase
  console.log('💾 Sauvegarde dans Firebase...');
  await Promise.all([
    firebasePut('/trades', existingTrades),
    firebasePut('/dividends', mergedDivs),
    firebasePut('/deposits', mergedDeps),
    firebasePut('/fees', mergedFees),
    firebasePut('/lastDataUpdate', Date.now())
  ]);

  // Résumé
  console.log('');
  console.log('═══════════════════════════════════');
  console.log('  📊 RÉSUMÉ DE LA SYNCHRONISATION');
  console.log('═══════════════════════════════════');
  console.log(`  Trades    : ${newCount} nouveau(x), ${updatedCount} mis à jour, ${dupCount} doublon(s)`);
  console.log(`  Dividendes: ${newDivs.length} nouveau(x) (total: ${mergedDivs.length})`);
  console.log(`  Dépôts    : ${newDeps.length} nouveau(x) (total: ${mergedDeps.length})`);
  console.log(`  Frais     : ${newFees.length} nouveau(x) (total: ${mergedFees.length})`);
  console.log(`  Total trades en base: ${existingTrades.length}`);
  console.log('═══════════════════════════════════');

  return { newCount, updatedCount, dupCount, newDivs: newDivs.length, newDeps: newDeps.length, newFees: newFees.length };
}

// ── Main ──
async function main() {
  console.log('');
  console.log('🚀 IG → Firebase Sync');
  console.log('  ' + new Date().toLocaleString('fr-FR'));
  console.log('');

  try {
    // 1. Login IG
    const session = await igLogin();

    // 2. Dates : 3 derniers jours
    const now = new Date();
    const from = new Date(now);
    from.setDate(from.getDate() - 3);
    const toDate   = now.toISOString().substring(0, 10);
    const fromDate = from.toISOString().substring(0, 10);

    // 3. Récupérer les transactions
    const txs = await igGetTransactions(session, fromDate, toDate);

    if (txs.length === 0) {
      console.log('ℹ️  Aucune transaction sur les 3 derniers jours.');
      return;
    }

    // 4. Convertir au format Dashboard
    const converted = convertTransactions(txs);
    console.log(`  → ${converted.trades.length} trade(s), ${converted.dividends.length} dividende(s), ${converted.deposits.length} dépôt(s), ${converted.fees.length} frais`);

    // 5. Fusionner avec Firebase
    await mergeWithFirebase(converted);

    console.log('\n✅ Synchronisation terminée avec succès !');

  } catch (err) {
    console.error('\n❌ Erreur:', err.message);
    if (err.message.includes('error.security.invalid-details')) {
      console.error('   → Vérifie IG_USERNAME et IG_PASSWORD dans .env');
    }
    if (err.message.includes('error.security.api-key-invalid')) {
      console.error('   → Vérifie IG_API_KEY dans .env');
    }
    process.exit(1);
  }
}

main();
