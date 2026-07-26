'use strict';

/* Motor de búsqueda de la biblioteca.
 *
 * Capas, de más precisa a más tolerante:
 *   1. Token exacto sobre el texto ya enriquecido en el indexado (el tesauro
 *      ES-EN y las abreviaturas UCS se expandieron allí, así que "caballo"
 *      está literalmente en el documento de un sonido de galope).
 *   2. Prefijo, para escrituras a medias: "caball" -> "caballo".
 *   3. Trigramas, para erratas: "caballlo", "wooosh".
 * El ranking es BM25 con refuerzo si la coincidencia cae en el nombre del
 * archivo. Además expone similitud coseno en el espacio TF-IDF para el
 * "buscar parecidos".
 */

const K1 = 1.2;   // saturación de frecuencia de término
const B = 0.75;   // normalización por longitud de documento

const NAME_BOOST = 2.6;   // coincidir en el nombre vale más que en los tags
const PREFIX_PENALTY = 0.55;
const FUZZY_PENALTY = 0.34;

const norm = (s) => s.toLowerCase()
  .normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9ñ]+/g, ' ')
  .trim();

const trigrams = (s) => {
  const p = `  ${s} `;
  const out = new Set();
  for (let i = 0; i < p.length - 2; i++) out.add(p.slice(i, i + 3));
  return out;
};

class SearchEngine {
  constructor(docs) {
    this.docs = docs;
    this.N = docs.length;

    this.postings = new Map();   // término -> Map(docIdx -> tf)
    this.nameTerms = [];         // Set de términos del nombre, por doc
    this.len = new Float32Array(this.N);

    for (let i = 0; i < this.N; i++) {
      const d = docs[i];
      const toks = (d.txt || norm(d.name)).split(' ').filter(Boolean);
      this.len[i] = toks.length || 1;

      const seen = new Map();
      for (const t of toks) seen.set(t, (seen.get(t) || 0) + 1);
      for (const [t, tf] of seen) {
        let p = this.postings.get(t);
        if (!p) { p = new Map(); this.postings.set(t, p); }
        p.set(i, tf);
      }
      this.nameTerms.push(new Set(norm(d.name).split(' ').filter(Boolean)));
    }

    this.avgdl = this.len.reduce((a, b) => a + b, 0) / (this.N || 1);
    this.vocab = [...this.postings.keys()];

    // Normas TF-IDF por documento, precalculadas de una pasada sobre las
    // listas de posteo. Sin esto, `similar()` recalcularía la norma de cada
    // candidato recorriendo todo el vocabulario: O(docs x vocab).
    this._idf = new Map();
    this.docNorm = new Float64Array(this.N);
    for (const [term, p] of this.postings) {
      const idf = Math.log(1 + (this.N - p.size + 0.5) / (p.size + 0.5));
      this._idf.set(term, idf);
      for (const [di, tf] of p) {
        const w = (1 + Math.log(tf)) * idf;
        this.docNorm[di] += w * w;
      }
    }
    for (let i = 0; i < this.N; i++) {
      this.docNorm[i] = Math.sqrt(this.docNorm[i]) || 1;
    }

    // Índice de trigramas del vocabulario, para el respaldo ante erratas
    // sin tener que recorrer las decenas de miles de términos en cada tecla.
    this.triIndex = new Map();
    for (const term of this.vocab) {
      if (term.length < 4) continue;
      for (const g of trigrams(term)) {
        let a = this.triIndex.get(g);
        if (!a) { a = []; this.triIndex.set(g, a); }
        a.push(term);
      }
    }
  }

  idf(term) {
    return this._idf.get(term) ?? Math.log(1 + (this.N + 0.5) / 0.5);
  }

  /** Términos del vocabulario que empiezan por el prefijo dado. */
  prefixMatches(q, limit = 24) {
    if (q.length < 3) return [];
    const out = [];
    for (const t of this.vocab) {
      if (t.length > q.length && t.startsWith(q)) {
        out.push(t);
        if (out.length >= limit) break;
      }
    }
    return out;
  }

  /** Términos parecidos por Jaccard de trigramas (tolera erratas). */
  fuzzyMatches(q, limit = 8, min = 0.42) {
    if (q.length < 4) return [];
    const qg = trigrams(q);
    const counts = new Map();
    for (const g of qg) {
      const arr = this.triIndex.get(g);
      if (!arr) continue;
      for (const t of arr) counts.set(t, (counts.get(t) || 0) + 1);
    }
    const scored = [];
    for (const [t, c] of counts) {
      const sim = c / (qg.size + trigrams(t).size - c);
      if (sim >= min) scored.push([t, sim]);
    }
    scored.sort((a, b) => b[1] - a[1]);
    return scored.slice(0, limit);
  }

  /**
   * Busca y devuelve índices de documento ordenados por relevancia.
   * `pool` limita a un subconjunto (categoría / favoritos / filtros).
   */
  search(query, pool = null) {
    const qTokens = norm(query).split(' ').filter((t) => t.length > 1);
    if (!qTokens.length) return null;

    const scores = new Map();
    const add = (term, weight) => {
      const p = this.postings.get(term);
      if (!p) return;
      const idf = this.idf(term);
      for (const [di, tf] of p) {
        if (pool && !pool.has(di)) continue;
        const dl = this.len[di];
        const bm = idf * (tf * (K1 + 1)) /
                   (tf + K1 * (1 - B + B * dl / this.avgdl));
        const boost = this.nameTerms[di].has(term) ? NAME_BOOST : 1;
        scores.set(di, (scores.get(di) || 0) + bm * weight * boost);
      }
    };

    // Cada token del usuario se resuelve en tres pasadas de precisión
    // decreciente; solo se cae a la siguiente si la anterior no dio nada.
    for (const qt of qTokens) {
      const exact = this.postings.has(qt);
      if (exact) add(qt, 1);

      const pref = this.prefixMatches(qt);
      for (const t of pref) add(t, PREFIX_PENALTY);

      if (!exact && !pref.length) {
        for (const [t, sim] of this.fuzzyMatches(qt)) {
          add(t, FUZZY_PENALTY * sim);
        }
      }
    }

    // Bonus por cubrir varios tokens distintos: buscar "puerta madera" debe
    // priorizar lo que casa con ambos, no lo que repite mucho uno solo.
    if (qTokens.length > 1) {
      for (const [di, sc] of scores) {
        let covered = 0;
        for (const qt of qTokens) {
          const p = this.postings.get(qt);
          if (p && p.has(di)) covered++;
        }
        scores.set(di, sc * (1 + 0.55 * covered / qTokens.length));
      }
    }

    return [...scores.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([di]) => di);
  }

  /**
   * Sonidos más parecidos por coseno en el espacio TF-IDF.
   *
   * Solo recorre las listas de posteo de los términos del documento origen,
   * así que toca únicamente los documentos que comparten algo con él, y usa
   * las normas precalculadas en el constructor.
   */
  similar(di, limit = 60, pool = null) {
    const dots = new Map();
    for (const [term, p] of this.postings) {
      const tfSelf = p.get(di);
      if (tfSelf === undefined) continue;
      const idf = this._idf.get(term);
      // Términos ubicuos no dicen nada del parecido y cuestan mucho recorrer.
      if (p.size > this.N * 0.25) continue;
      const wSelf = (1 + Math.log(tfSelf)) * idf;
      for (const [dj, tf] of p) {
        if (dj === di) continue;
        if (pool && !pool.has(dj)) continue;
        dots.set(dj, (dots.get(dj) || 0) + wSelf * (1 + Math.log(tf)) * idf);
      }
    }
    const selfNorm = this.docNorm[di];
    const out = [];
    for (const [dj, dot] of dots) {
      out.push([dj, dot / (selfNorm * this.docNorm[dj])]);
    }
    out.sort((a, b) => b[1] - a[1]);
    return out.slice(0, limit).map(([dj]) => dj);
  }
}

window.SearchEngine = SearchEngine;
window.searchNorm = norm;
