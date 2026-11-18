"""
main.py — Point d'entrée principal du Livrable 3 Multi-Sources (Jobboom, Guichet-Emplois, Jobillico, Remotive).
Auteure : Elvira (Projet jobs-insights)

Commandes principales :
  # 1. Consolider les 4 sources (uniquement offres 2026 valides), exporter JSON + CSV et générer visualiseur.html :
  python main.py

  # 2. Filtrer en ligne de commande (par source, ville, compétence ou stage) :
  python main.py --source Jobboom
  python main.py --ville Québec --competence Python
  python main.py --stage

  # 3. Lancer une collecte en direct sur Jobboom :
  python main.py --live --max-live 6
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from collecteurs import JobboomCollector
from models import JobOffer
from pipeline import MultiSourcePipeline

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent.parent


HTML_VIEWER_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Visualiseur Multi-Sources TI (2026) — jobs-insights (Elvira)</title>
  <style>
    :root {
      --bg: #f8fafc;
      --surface: #ffffff;
      --border: #e2e8f0;
      --text: #0f172a;
      --muted: #475569;
      --primary: #2563eb;
      --primary-light: #dbeafe;
      --stage-bg: #fef3c7;
      --stage-text: #92400e;
      --remote-bg: #dcfce7;
      --remote-text: #166534;
      --hybrid-bg: #e0e7ff;
      --hybrid-text: #3730a3;
      --onsite-bg: #f1f5f9;
      --onsite-text: #334155;
      --skill-bg: #f0fdf4;
      --skill-border: #bbf7d0;
      --skill-text: #15803d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }
    header {
      background: linear-gradient(135deg, #1e3a8a, #2563eb);
      color: white;
      padding: 1.5rem 2rem;
      box-shadow: 0 2px 10px rgba(0,0,0,0.08);
    }
    .header-top {
      max-width: 1320px;
      margin: 0 auto;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
    }
    header h1 { margin: 0; font-size: 1.45rem; }
    header p { margin: 0.25rem 0 0; opacity: 0.92; font-size: 0.92rem; }
    .file-loader {
      background: rgba(255,255,255,0.15);
      border: 1px solid rgba(255,255,255,0.35);
      padding: 0.5rem 0.9rem;
      border-radius: 8px;
      color: white;
      font-size: 0.85rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
    }
    .file-loader:hover { background: rgba(255,255,255,0.25); }
    .file-loader input { display: none; }
    main {
      max-width: 1320px;
      margin: 1.5rem auto;
      padding: 0 1.25rem 3rem;
    }
    details.schema-guide {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.85rem 1.2rem;
      margin-bottom: 1.25rem;
    }
    details.schema-guide summary {
      cursor: pointer;
      font-weight: 600;
      color: var(--primary);
      font-size: 0.95rem;
    }
    .schema-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 0.65rem;
      margin-top: 0.85rem;
      font-size: 0.84rem;
    }
    .schema-item {
      background: #f8fafc;
      border: 1px solid var(--border);
      padding: 0.5rem 0.7rem;
      border-radius: 6px;
    }
    .schema-item code {
      color: #b91c1c;
      font-weight: 700;
      background: #fee2e2;
      padding: 0.1rem 0.35rem;
      border-radius: 4px;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
      margin-bottom: 1.25rem;
    }
    .kpi-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem 1.15rem;
      box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .kpi-label {
      font-size: 0.78rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      font-weight: 600;
    }
    .kpi-value {
      font-size: 1.7rem;
      font-weight: 700;
      color: var(--primary);
      margin-top: 0.2rem;
    }
    .kpi-sub { font-size: 0.78rem; color: var(--muted); margin-top: 0.15rem; }
    .filters-bar {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem 1.15rem;
      margin-bottom: 1.25rem;
      display: grid;
      grid-template-columns: 1.8fr repeat(5, 1fr) auto;
      gap: 0.7rem;
      align-items: end;
    }
    @media (max-width: 1100px) {
      .filters-bar { grid-template-columns: 1fr 1fr; }
    }
    .filter-group label {
      display: block;
      font-size: 0.76rem;
      font-weight: 600;
      color: var(--muted);
      margin-bottom: 0.3rem;
    }
    .filter-group input, .filter-group select {
      width: 100%;
      padding: 0.48rem 0.6rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 0.86rem;
      background: white;
    }
    .btn-reset {
      padding: 0.5rem 0.85rem;
      border: 1px solid var(--border);
      background: #f1f5f9;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.84rem;
      font-weight: 600;
      color: var(--text);
    }
    .btn-reset:hover { background: #e2e8f0; }
    .results-info {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.85rem;
      font-size: 0.9rem;
      color: var(--muted);
      flex-wrap: wrap;
      gap: 0.5rem;
    }
    .jobs-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(370px, 1fr));
      gap: 1.1rem;
    }
    @media (max-width: 500px) {
      .jobs-grid { grid-template-columns: 1fr; }
    }
    .job-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.15rem;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 0.8rem;
      transition: transform 0.12s ease, box-shadow 0.12s ease;
    }
    .job-card:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 16px rgba(15, 23, 42, 0.07);
    }
    .card-header { display: flex; gap: 0.85rem; align-items: flex-start; }
    .company-placeholder {
      width: 46px;
      height: 46px;
      border-radius: 8px;
      background: var(--primary-light);
      color: var(--primary);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 1.05rem;
      flex-shrink: 0;
    }
    .job-title { margin: 0; font-size: 1.0rem; color: var(--text); line-height: 1.3; }
    .job-company { margin: 0.2rem 0 0; font-size: 0.86rem; color: var(--muted); font-weight: 500; }
    .job-id-badge {
      font-family: monospace;
      font-size: 0.72rem;
      color: #64748b;
      background: #f1f5f9;
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
    }
    .badges-row { display: flex; flex-wrap: wrap; gap: 0.38rem; }
    .badge {
      font-size: 0.74rem;
      font-weight: 600;
      padding: 0.18rem 0.52rem;
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
    }
    .badge-src-jobboom { background: #dbeafe; color: #1e40af; }
    .badge-src-guichet { background: #fee2e2; color: #991b1b; }
    .badge-src-jobillico { background: #fef3c7; color: #92400e; }
    .badge-src-remotive { background: #f3e8ff; color: #6b21a8; }
    .badge-location { background: #f1f5f9; color: #334155; }
    .badge-stage { background: var(--stage-bg); color: var(--stage-text); }
    .badge-remote { background: var(--remote-bg); color: var(--remote-text); }
    .badge-hybrid { background: var(--hybrid-bg); color: var(--hybrid-text); }
    .badge-onsite { background: var(--onsite-bg); color: var(--onsite-text); }
    .skills-row { display: flex; flex-wrap: wrap; gap: 0.35rem; }
    .skill-tag {
      font-size: 0.72rem;
      background: var(--skill-bg);
      border: 1px solid var(--skill-border);
      color: var(--skill-text);
      padding: 0.1rem 0.45rem;
      border-radius: 5px;
      cursor: pointer;
      font-weight: 600;
    }
    .skill-tag:hover { background: #dcfce7; }
    .meta-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.3rem 0.7rem;
      font-size: 0.76rem;
      color: var(--muted);
      background: #f8fafc;
      padding: 0.5rem 0.65rem;
      border-radius: 8px;
      border: 1px solid #f1f5f9;
    }
    .desc-preview { font-size: 0.83rem; color: #334155; margin: 0; }
    .card-actions {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.5rem;
      padding-top: 0.45rem;
      border-top: 1px solid var(--border);
    }
    .btn-detail {
      background: var(--primary-light);
      color: var(--primary);
      border: none;
      padding: 0.4rem 0.7rem;
      border-radius: 6px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
    }
    .btn-detail:hover { background: #bfdbfe; }
    .btn-link { font-size: 0.8rem; color: var(--primary); text-decoration: none; font-weight: 600; }
    .btn-link:hover { text-decoration: underline; }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.55);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 1rem;
      z-index: 1000;
    }
    .modal-backdrop.open { display: flex; }
    .modal {
      background: white;
      max-width: 820px;
      width: 100%;
      max-height: 88vh;
      border-radius: 12px;
      overflow-y: auto;
      padding: 1.5rem;
      box-shadow: 0 20px 40px rgba(0,0,0,0.2);
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.85rem;
      margin-bottom: 1rem;
    }
    .btn-close {
      background: #f1f5f9;
      border: none;
      border-radius: 6px;
      padding: 0.35rem 0.65rem;
      font-size: 0.9rem;
      cursor: pointer;
      font-weight: 700;
    }
    .modal-section-title {
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
      margin: 1rem 0 0.4rem;
    }
    .full-desc {
      white-space: pre-wrap;
      background: #f8fafc;
      border: 1px solid var(--border);
      padding: 0.9rem;
      border-radius: 8px;
      font-size: 0.86rem;
      line-height: 1.6;
    }
    pre.json-view {
      background: #0f172a;
      color: #e2e8f0;
      padding: 0.9rem;
      border-radius: 8px;
      font-size: 0.76rem;
      overflow-x: auto;
    }
  </style>
</head>
<body>
  <header>
    <div class="header-top">
      <div>
        <h1>📊 Visualiseur Multi-Sources d'Offres TI 2026 — jobs-insights (Elvira)</h1>
        <p>Agrégation dédupliquée : <b>Jobboom</b> + <b>Guichet-Emplois</b> + <b>Jobillico</b> + <b>Remotive</b> (100 % offres 2026 valides)</p>
      </div>
      <label class="file-loader" title="Charger un autre fichier JSON local">
        📂 Charger un fichier .json
        <input type="file" id="fileInput" accept=".json" />
      </label>
    </div>
  </header>

  <main>
    <details class="schema-guide">
      <summary>📖 Comprendre chaque champ du modèle unifié JobOffer (cliquer pour ouvrir/fermer)</summary>
      <div class="schema-grid">
        <div class="schema-item"><code>id</code> : Identifiant préfixé par source (<code>jb-</code>, <code>ge-</code>, <code>ji-</code>, <code>rem-</code>).</div>
        <div class="schema-item"><code>source</code> &amp; <code>partenaire_origine</code> : Plateforme collectée et partenaire éventuel.</div>
        <div class="schema-item"><code>origines_decouverte</code> &amp; <code>urls_sources</code> : Canaux et URLs fusionnés lors de la déduplication.</div>
        <div class="schema-item"><code>titre</code> &amp; <code>entreprise</code> : Intitulé nettoyé du poste TI et nom de l'employeur.</div>
        <div class="schema-item"><code>ville</code>, <code>province</code>, <code>coordonnees_gps</code> : Localisation normalisée au Québec / Canada.</div>
        <div class="schema-item"><code>modalite</code> : Mode de travail (<b>Sur place</b>, <b>Hybride</b> ou <b>Télétravail</b>).</div>
        <div class="schema-item"><code>est_stage</code> : Booléen (<code>true</code>/<code>false</code>) identifiant les stages TI.</div>
        <div class="schema-item"><code>competences_cles</code> : Technologies TI détectées sans faux positifs.</div>
        <div class="schema-item"><code>salaire</code> : Rémunération extraite lorsqu'elle est affichée (<code>null</code> sinon).</div>
        <div class="schema-item"><code>date_publication</code> / <code>date_expiration</code> : Exclusivement des offres récentes de <b>2026</b> et non expirées.</div>
        <div class="schema-item"><code>description_texte</code> : Description unique nettoyée de tout code HTML.</div>
      </div>
    </details>

    <section class="kpi-grid" id="kpiGrid"></section>

    <section class="filters-bar">
      <div class="filter-group">
        <label for="searchInput">🔎 Recherche (titre, entreprise, description)</label>
        <input type="text" id="searchInput" placeholder="Ex: développeur, stage, Python, Québec..." />
      </div>
      <div class="filter-group">
        <label for="sourceFilter">🌐 Source</label>
        <select id="sourceFilter"><option value="">Toutes les sources</option></select>
      </div>
      <div class="filter-group">
        <label for="cityFilter">📍 Ville</label>
        <select id="cityFilter"><option value="">Toutes les villes</option></select>
      </div>
      <div class="filter-group">
        <label for="modeFilter">🏠 Modalité</label>
        <select id="modeFilter"><option value="">Toutes les modalités</option></select>
      </div>
      <div class="filter-group">
        <label for="skillFilter">💻 Compétence TI</label>
        <select id="skillFilter"><option value="">Toutes les compétences</option></select>
      </div>
      <div class="filter-group">
        <label for="typeFilter">🎓 Type d'offre</label>
        <select id="typeFilter">
          <option value="">Toutes les offres (2026)</option>
          <option value="stage">🎓 Stages uniquement</option>
          <option value="salary">💰 Avec salaire affiché</option>
        </select>
      </div>
      <button class="btn-reset" id="resetBtn">Réinitialiser</button>
    </section>

    <div class="results-info">
      <span id="resultsCount"></span>
      <span>Astuce : cliquez sur une compétence verte ou sur « Inspecter l'offre &amp; JSON » pour voir tous les détails.</span>
    </div>

    <section class="jobs-grid" id="jobsGrid"></section>
  </main>

  <div class="modal-backdrop" id="modalBackdrop">
    <div class="modal">
      <div class="modal-header">
        <div>
          <h2 id="modalTitle" style="margin:0;font-size:1.15rem;"></h2>
          <p id="modalSub" style="margin:0.25rem 0 0;color:#475569;font-size:0.88rem;"></p>
        </div>
        <button class="btn-close" id="closeModalBtn">✕ Fermer</button>
      </div>
      <div class="modal-section-title">Description nettoyée (<code>description_texte</code>)</div>
      <div class="full-desc" id="modalDesc"></div>
      <div class="modal-section-title">Objet JSON complet de cette offre</div>
      <pre class="json-view" id="modalJson"></pre>
    </div>
  </div>

  <script>
    let ALL_OFFERS = __OFFERS_JSON__;

    const searchInput = document.getElementById('searchInput');
    const sourceFilter = document.getElementById('sourceFilter');
    const cityFilter = document.getElementById('cityFilter');
    const modeFilter = document.getElementById('modeFilter');
    const skillFilter = document.getElementById('skillFilter');
    const typeFilter = document.getElementById('typeFilter');
    const resetBtn = document.getElementById('resetBtn');
    const jobsGrid = document.getElementById('jobsGrid');
    const kpiGrid = document.getElementById('kpiGrid');
    const resultsCount = document.getElementById('resultsCount');
    const fileInput = document.getElementById('fileInput');

    function populateFilters(offers) {
      const sources = [...new Set(offers.map(o => o.source).filter(Boolean))].sort();
      const cities = [...new Set(offers.map(o => o.ville).filter(Boolean))].sort();
      const modes = [...new Set(offers.map(o => o.modalite).filter(Boolean))].sort();
      const skills = [...new Set(offers.flatMap(o => o.competences_cles || []))].sort();

      sourceFilter.innerHTML = '<option value="">Toutes les sources (' + sources.length + ')</option>' +
        sources.map(s => `<option value="${s}">${s}</option>`).join('');
      cityFilter.innerHTML = '<option value="">Toutes les villes (' + cities.length + ')</option>' +
        cities.map(c => `<option value="${c}">${c}</option>`).join('');
      modeFilter.innerHTML = '<option value="">Toutes les modalités</option>' +
        modes.map(m => `<option value="${m}">${m}</option>`).join('');
      skillFilter.innerHTML = '<option value="">Toutes les compétences (' + skills.length + ')</option>' +
        skills.map(s => `<option value="${s}">${s}</option>`).join('');
    }

    function renderKPIs(offers) {
      const total = offers.length;
      const stages = offers.filter(o => o.est_stage).length;
      const withSalary = offers.filter(o => o.salaire).length;
      const remoteOrHybrid = offers.filter(o => o.modalite === 'Télétravail' || o.modalite === 'Hybride').length;
      const bySrc = {};
      offers.forEach(o => { bySrc[o.source] = (bySrc[o.source] || 0) + 1; });
      const srcSummary = Object.entries(bySrc).map(([k,v]) => `${k}: ${v}`).join(' · ') || 'Aucune';

      kpiGrid.innerHTML = `
        <div class="kpi-card">
          <div class="kpi-label">Offres TI 2026 valides</div>
          <div class="kpi-value">${total}</div>
          <div class="kpi-sub">sur ${ALL_OFFERS.length} offres unifiées</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Répartition par source</div>
          <div class="kpi-value" style="font-size:1.15rem;margin-top:0.45rem;">${Object.keys(bySrc).length} sources</div>
          <div class="kpi-sub">${srcSummary}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Stages TI détectés</div>
          <div class="kpi-value">${stages}</div>
          <div class="kpi-sub">champ <code>est_stage: true</code></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Avec salaire indiqué</div>
          <div class="kpi-value">${withSalary}</div>
          <div class="kpi-sub">extraits sans supposition</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Hybride / Télétravail</div>
          <div class="kpi-value">${remoteOrHybrid}</div>
          <div class="kpi-sub">${total - remoteOrHybrid} sur place</div>
        </div>
      `;
    }

    function sourceBadgeClass(src) {
      const s = (src || '').toLowerCase();
      if (s.includes('jobboom')) return 'badge-src-jobboom';
      if (s.includes('guichet')) return 'badge-src-guichet';
      if (s.includes('jobillico')) return 'badge-src-jobillico';
      return 'badge-src-remotive';
    }

    function modeBadgeClass(mode) {
      if (mode === 'Télétravail') return 'badge-remote';
      if (mode === 'Hybride') return 'badge-hybrid';
      return 'badge-onsite';
    }

    function renderJobs() {
      const q = searchInput.value.trim().toLowerCase();
      const src = sourceFilter.value;
      const city = cityFilter.value;
      const mode = modeFilter.value;
      const skill = skillFilter.value;
      const type = typeFilter.value;

      const filtered = ALL_OFFERS.filter(o => {
        if (src && o.source !== src) return false;
        if (city && o.ville !== city) return false;
        if (mode && o.modalite !== mode) return false;
        if (skill && !(o.competences_cles || []).includes(skill)) return false;
        if (type === 'stage' && !o.est_stage) return false;
        if (type === 'salary' && !o.salaire) return false;
        if (q) {
          const hay = `${o.id} ${o.source} ${o.titre} ${o.entreprise} ${o.ville} ${o.description_texte} ${(o.competences_cles || []).join(' ')}`.toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      });

      renderKPIs(filtered);
      resultsCount.textContent = `${filtered.length} offre(s) affichée(s) sur ${ALL_OFFERS.length} (100 % publiées en 2026 et valides)`;

      jobsGrid.innerHTML = filtered.map((o) => {
        const initials = (o.entreprise || 'TI').slice(0, 2).toUpperCase();
        const skillsHtml = (o.competences_cles || []).length
          ? (o.competences_cles || []).slice(0, 10).map(s => `<span class="skill-tag" onclick="filterBySkill('${s}')">${s}</span>`).join('')
          : `<span style="font-size:0.74rem;color:#94a3b8;">Compétences générales TI</span>`;
        const preview = (o.description_texte || '').slice(0, 175) + ((o.description_texte || '').length > 175 ? '…' : '');
        const partnerText = o.partenaire_origine ? ` · via ${o.partenaire_origine}` : '';

        return `
          <article class="job-card">
            <div>
              <div class="card-header">
                <div class="company-placeholder">${initials}</div>
                <div style="flex:1;">
                  <div style="display:flex;justify-content:space-between;gap:0.4rem;align-items:center;flex-wrap:wrap;">
                    <span class="job-id-badge">${o.id}</span>
                    <span class="badge ${sourceBadgeClass(o.source)}">${o.source}${partnerText}</span>
                  </div>
                  <h3 class="job-title" style="margin-top:0.3rem;">${o.titre}</h3>
                  <p class="job-company">${o.entreprise}</p>
                </div>
              </div>

              <div class="badges-row" style="margin-top:0.65rem;">
                <span class="badge badge-location">📍 ${o.ville} (${o.province || 'QC'})</span>
                <span class="badge ${modeBadgeClass(o.modalite)}">${o.modalite || 'Sur place'}</span>
                ${o.est_stage ? '<span class="badge badge-stage">🎓 STAGE</span>' : ''}
              </div>

              <div class="skills-row" style="margin-top:0.6rem;">${skillsHtml}</div>

              <div class="meta-grid" style="margin-top:0.6rem;">
                <div>📅 <b>Publiée :</b> ${o.date_publication || '2026'}</div>
                <div>💰 <b>Salaire :</b> ${o.salaire || 'Non spécifié'}</div>
              </div>

              <p class="desc-preview" style="margin-top:0.6rem;">${preview}</p>
            </div>

            <div class="card-actions">
              <button class="btn-detail" onclick="openModal('${o.id}')">🔍 Inspecter l'offre &amp; JSON</button>
              <a class="btn-link" href="${o.url}" target="_blank" rel="noopener">Voir l'annonce ↗</a>
            </div>
          </article>
        `;
      }).join('');
    }

    window.filterBySkill = function(skill) {
      skillFilter.value = skill;
      renderJobs();
    };

    window.openModal = function(jobId) {
      const offer = ALL_OFFERS.find(o => o.id === jobId);
      if (!offer) return;
      document.getElementById('modalTitle').textContent = `${offer.titre} — ${offer.entreprise}`;
      document.getElementById('modalSub').textContent = `${offer.id} | Source : ${offer.source} | ${offer.ville} (${offer.province}) | Publiée : ${offer.date_publication}`;
      document.getElementById('modalDesc').textContent = offer.description_texte || '(Aucune description)';
      document.getElementById('modalJson').textContent = JSON.stringify(offer, null, 2);
      document.getElementById('modalBackdrop').classList.add('open');
    };

    document.getElementById('closeModalBtn').addEventListener('click', () => {
      document.getElementById('modalBackdrop').classList.remove('open');
    });
    document.getElementById('modalBackdrop').addEventListener('click', (e) => {
      if (e.target.id === 'modalBackdrop') {
        document.getElementById('modalBackdrop').classList.remove('open');
      }
    });

    [searchInput, sourceFilter, cityFilter, modeFilter, skillFilter, typeFilter].forEach(el => {
      el.addEventListener('input', renderJobs);
      el.addEventListener('change', renderJobs);
    });

    resetBtn.addEventListener('click', () => {
      searchInput.value = '';
      sourceFilter.value = '';
      cityFilter.value = '';
      modeFilter.value = '';
      skillFilter.value = '';
      typeFilter.value = '';
      renderJobs();
    });

    fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (evt) => {
        try {
          const parsed = JSON.parse(evt.target.result);
          if (Array.isArray(parsed)) {
            ALL_OFFERS = parsed;
            populateFilters(ALL_OFFERS);
            renderJobs();
          }
        } catch (err) {
          alert("Erreur de lecture du JSON : " + err.message);
        }
      };
      reader.readAsText(file, 'utf-8');
    });

    populateFilters(ALL_OFFERS);
    renderJobs();
  </script>
</body>
</html>
"""


def generate_html_viewer(offers: list[JobOffer], html_path: Path) -> None:
    """Génère le fichier `visualiseur.html` autonome avec toutes les offres unifiées."""
    offers_json = json.dumps([o.to_dict() for o in offers], ensure_ascii=False)
    html_content = HTML_VIEWER_TEMPLATE.replace("__OFFERS_JSON__", offers_json)
    html_path.write_text(html_content, encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Livrable 3 Multi-Sources — Agrégateur d'offres TI 2026 (Jobboom, Guichet-Emplois, Jobillico, Remotive)."
    )
    parser.add_argument("--source", type=str, default=None, help="Filtrer par source (Jobboom, Guichet-Emplois, Jobillico, Remotive).")
    parser.add_argument("--ville", type=str, default=None, help="Filtrer par ville (ex: Québec, Montréal, Laval).")
    parser.add_argument("--modalite", type=str, default=None, help="Filtrer par modalité (Sur place, Hybride, Télétravail).")
    parser.add_argument("--competence", type=str, default=None, help="Filtrer par compétence TI (ex: Python, SQL, Azure, Linux).")
    parser.add_argument("--stage", action="store_true", help="Afficher uniquement les offres de stage.")
    parser.add_argument("--recherche", type=str, default=None, help="Recherche libre dans le titre, l'entreprise ou la description.")
    parser.add_argument("--live", action="store_true", help="Exécuter en plus une collecte HTTP en direct sur Jobboom.")
    parser.add_argument("--max-live", type=int, default=5, help="Nombre maximal d'offres en direct (défaut: 5).")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=HERE / "offres_multi_sources.json",
        help="Fichier JSON de sortie unifié.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=HERE / "offres_multi_sources.csv",
        help="Fichier CSV de sortie pour Excel.",
    )
    parser.add_argument(
        "--output-html",
        type=Path,
        default=HERE / "visualiseur.html",
        help="Fichier HTML du visualiseur interactif.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    print("=" * 78)
    print(" PIPELINE MULTI-SOURCES TI (2026) — JOBBOOM · GUICHET-EMPLOIS · JOBILLICO · REMOTIVE")
    print("=" * 78)

    offers = MultiSourcePipeline.consolidate_workspace_datasets(REPO_ROOT)

    if args.live:
        print(f"[*] Collecte en direct sur Jobboom (max {args.max_live} offres)...")
        live_offers = JobboomCollector().collect_live(max_offers=args.max_live)
        offers = MultiSourcePipeline.deduplicate_and_merge(offers + live_offers)

    filtered = MultiSourcePipeline.filter_offers(
        offers,
        source=args.source,
        ville=args.ville,
        modalite=args.modalite,
        competence=args.competence,
        stages_only=args.stage,
        query=args.recherche,
    )

    by_source = Counter(o.source for o in filtered)
    stages_count = sum(1 for o in filtered if o.est_stage)
    dates = [o.date_publication for o in filtered if o.date_publication]
    min_date = min(dates) if dates else "N/A"
    max_date = max(dates) if dates else "N/A"

    print(f"[1/3] Offres TI 2026 valides et dédupliquées : {len(filtered)} offres")
    for src_name, count in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"      - {src_name:<18} : {count} offres")
    print(f"      - Stages détectés    : {stages_count} offres")
    print(f"      - Période couverte   : {min_date} au {max_date} (0 offre des années passées)")

    MultiSourcePipeline.export_json(filtered, args.output_json)
    # Maintenir aussi offres_jobboom_v2.json avec les offres Jobboom 2026 valides
    jobboom_only = [o for o in offers if o.source == "Jobboom"]
    MultiSourcePipeline.export_json(jobboom_only, HERE / "offres_jobboom_v2.json")

    MultiSourcePipeline.export_csv(filtered, args.output_csv)
    generate_html_viewer(filtered, args.output_html)

    print(f"[2/3] Exports générés :")
    print(f"      - JSON multi-sources : {args.output_json.name} ({len(filtered)} offres)")
    print(f"      - JSON Jobboom (v2)  : offres_jobboom_v2.json ({len(jobboom_only)} offres)")
    print(f"      - CSV (Excel)        : {args.output_csv.name}")
    print(f"      - Visualiseur Web    : {args.output_html.name}")
    print("[3/3] Terminé avec succès !")


if __name__ == "__main__":
    main()
