/**
 * Agents Module — FRA agents dashboard.
 *
 * Shows the real Feather Research Agent processes (research supervisor,
 * math agent, Nachweis pipeline, Telegram bridge, ...) with live status.
 * One-shot actions run to completion; watch actions run until stopped.
 * Backed by /api/fra/agents (routes/agents_routes.py).
 */

import { makeWindowDraggable } from './windowDrag.js';

const API_BASE = window.location.origin;
let _open = false;
let _agents = [];
let _fraDir = '';
let _fraDirExists = true;
let _pollTimer = null;
let _escHandler = null;
let _expandedOutput = null; // agent_id whose output panel is open

// ---- API ----

async function _fetchAgents() {
  try {
    const res = await fetch(`${API_BASE}/api/fra/agents`, { credentials: 'same-origin' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _agents = data.agents || [];
    _fraDir = data.fra_dir || '';
    _fraDirExists = data.fra_dir_exists !== false;
  } catch (e) {
    console.error('Failed to fetch FRA agents:', e);
    _agents = [];
  }
}

async function _runAction(agentId, actionId) {
  const res = await fetch(`${API_BASE}/api/fra/agents/${agentId}/run`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: actionId }),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return await res.json();
}

async function _stopAgent(agentId) {
  const res = await fetch(`${API_BASE}/api/fra/agents/${agentId}/stop`, {
    method: 'POST', credentials: 'same-origin',
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
}

async function _fetchOutput(agentId) {
  const res = await fetch(`${API_BASE}/api/fra/agents/${agentId}/output`, {
    credentials: 'same-origin',
  });
  if (!res.ok) return { output: `(failed to load output: HTTP ${res.status})` };
  return await res.json();
}

// ---- Styles (injected once) ----

function _ensureStyles() {
  if (document.getElementById('agents-panel-styles')) return;
  const style = document.createElement('style');
  style.id = 'agents-panel-styles';
  style.textContent = `
    .agents-modal-content { width: min(860px, 94vw); max-height: 86vh; display: flex; flex-direction: column; }
    .agents-body { overflow-y: auto; padding: 4px 2px 10px; }
    .agents-category { margin: 14px 4px 6px; font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.55; }
    .agent-card { border: 1px solid var(--border, #333); border-radius: 10px; padding: 12px 14px; margin: 8px 4px; background: var(--panel, rgba(255,255,255,0.03)); }
    .agent-card-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .agent-card-name { font-weight: 600; font-size: 0.95rem; }
    .agent-card-desc { font-size: 0.8rem; opacity: 0.7; margin-top: 4px; line-height: 1.45; }
    .agent-status-badge { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.08em; padding: 2px 9px; border-radius: 999px; border: 1px solid transparent; }
    .agent-status-badge.idle { color: var(--fg, #ddd); opacity: 0.55; border-color: var(--border, #444); }
    .agent-status-badge.running { color: #fff; background: var(--green, #2e9e5b); animation: agentPulse 1.6s ease-in-out infinite; }
    .agent-status-badge.failed { color: #fff; background: var(--red, #b33); }
    @keyframes agentPulse { 0%,100% { opacity: 1; } 50% { opacity: 0.55; } }
    .agent-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
    .agent-btn { font-size: 0.78rem; padding: 5px 12px; border-radius: 7px; border: 1px solid var(--border, #444); background: transparent; color: var(--fg, #ddd); cursor: pointer; }
    .agent-btn:hover { background: var(--border, #444); }
    .agent-btn.primary { background: var(--send-btn-bg, var(--green, #2e9e5b)); border-color: transparent; color: #fff; }
    .agent-btn.danger { background: var(--red, #b33); border-color: transparent; color: #fff; }
    .agent-btn:disabled { opacity: 0.4; cursor: default; }
    .agent-meta { font-size: 0.72rem; opacity: 0.55; margin-top: 8px; }
    .agent-output { margin-top: 10px; background: var(--code-bg, rgba(0,0,0,0.35)); color: var(--code-fg, #cdd); border: 1px solid var(--border, #333); border-radius: 8px; padding: 10px; font-family: ui-monospace, Consolas, monospace; font-size: 0.72rem; max-height: 260px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; }
    .agents-warn { margin: 8px 4px; padding: 10px 12px; border: 1px solid var(--red, #b33); border-radius: 8px; font-size: 0.8rem; }
    .agents-toast { font-size: 0.78rem; margin: 0 4px 4px; min-height: 1.2em; opacity: 0.8; }
  `;
  document.head.appendChild(style);
}

// ---- Rendering ----

function _esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function _toast(msg, isError) {
  const t = document.getElementById('agents-toast');
  if (!t) return;
  t.textContent = msg;
  t.style.color = isError ? 'var(--red, #b33)' : '';
  setTimeout(() => { if (t.textContent === msg) t.textContent = ''; }, 6000);
}

function _renderList() {
  const body = document.getElementById('agents-body');
  if (!body) return;

  if (!_agents.length) {
    body.innerHTML = `<div style="opacity:0.6;padding:30px;text-align:center;">Loading agents…</div>`;
    return;
  }

  let html = '';
  if (!_fraDirExists) {
    html += `<div class="agents-warn">FRA directory not found: <code>${_esc(_fraDir)}</code> — check FRA_DIR in .env</div>`;
  }

  const categories = [...new Set(_agents.map(a => a.category))];
  for (const cat of categories) {
    html += `<div class="agents-category">${_esc(cat)}</div>`;
    for (const a of _agents.filter(x => x.category === cat)) {
      const st = a.status || { state: 'idle' };
      const running = st.state === 'running';
      const last = st.last_run;
      const failed = !running && last && last.returncode !== 0 && last.returncode != null;

      let badge;
      if (running) {
        badge = `<span class="agent-status-badge running">RUNNING · ${_esc(st.action_label || st.action)}</span>`;
      } else if (failed) {
        badge = `<span class="agent-status-badge failed">EXIT ${_esc(last.returncode)}</span>`;
      } else {
        badge = `<span class="agent-status-badge idle">IDLE</span>`;
      }

      let buttons = '';
      if (running) {
        buttons += `<button class="agent-btn danger" data-stop="${_esc(a.id)}">■ Stop</button>`;
      } else {
        for (const act of a.actions) {
          const cls = act.kind === 'watch' ? 'agent-btn primary' : 'agent-btn';
          const icon = act.kind === 'watch' ? '▶ ' : '';
          buttons += `<button class="${cls}" data-run="${_esc(a.id)}" data-action="${_esc(act.id)}">${icon}${_esc(act.label)}</button>`;
        }
      }
      buttons += `<button class="agent-btn" data-output="${_esc(a.id)}">${_expandedOutput === a.id ? 'Hide output' : 'Output'}</button>`;

      let meta = '';
      if (running) {
        meta = `Started ${_esc(_fmtTime(st.started_at))} · PID ${_esc(st.pid)}`;
      } else if (last) {
        meta = `Last run: ${_esc(last.action)} · finished ${_esc(_fmtTime(last.finished_at))} · exit ${_esc(last.returncode)}`;
      }

      html += `
        <div class="agent-card" data-agent="${_esc(a.id)}">
          <div class="agent-card-head">
            <span class="agent-card-name">${_esc(a.name)}</span>
            ${badge}
          </div>
          <div class="agent-card-desc">${_esc(a.description)}</div>
          <div class="agent-actions">${buttons}</div>
          ${meta ? `<div class="agent-meta">${meta}</div>` : ''}
          ${_expandedOutput === a.id ? `<div class="agent-output" id="agent-output-${_esc(a.id)}">Loading output…</div>` : ''}
        </div>`;
    }
  }
  body.innerHTML = html;

  // Wire buttons
  body.querySelectorAll('[data-run]').forEach(btn => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await _runAction(btn.dataset.run, btn.dataset.action);
        _toast(`Started ${btn.dataset.run} / ${btn.dataset.action}`);
        _expandedOutput = btn.dataset.run;
      } catch (e) {
        _toast(`Start failed: ${e.message}`, true);
      }
      await _refresh();
    });
  });
  body.querySelectorAll('[data-stop]').forEach(btn => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await _stopAgent(btn.dataset.stop);
        _toast(`Stopped ${btn.dataset.stop}`);
      } catch (e) {
        _toast(`Stop failed: ${e.message}`, true);
      }
      await _refresh();
    });
  });
  body.querySelectorAll('[data-output]').forEach(btn => {
    btn.addEventListener('click', async () => {
      _expandedOutput = _expandedOutput === btn.dataset.output ? null : btn.dataset.output;
      _renderList();
      await _loadExpandedOutput();
    });
  });

  _loadExpandedOutput();
}

function _fmtTime(iso) {
  if (!iso) return '?';
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  catch (_) { return iso; }
}

async function _loadExpandedOutput() {
  if (!_expandedOutput) return;
  const el = document.getElementById(`agent-output-${_expandedOutput}`);
  if (!el) return;
  const data = await _fetchOutput(_expandedOutput);
  // Don't clobber scroll position if user scrolled up
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
  el.textContent = data.output || '(empty)';
  if (atBottom) el.scrollTop = el.scrollHeight;
}

async function _refresh() {
  await _fetchAgents();
  if (_open) _renderList();
}

// ---- Modal ----

export function openAgents() {
  if (_open) return;
  _open = true;
  _ensureStyles();

  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.id = 'agents-modal';
  modal.innerHTML = `
    <div class="modal-content agents-modal-content">
      <div class="modal-header">
        <h4 style="position:relative;top:-2px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:6px"><rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 8V4"/><circle cx="12" cy="3" r="1"/><circle cx="9" cy="13" r="1"/><circle cx="15" cy="13" r="1"/><path d="M9 17h6"/></svg>
          FRA Agents
        </h4>
        <span style="flex:1"></span>
        <button class="close-btn" id="agents-close">✖</button>
      </div>
      <div class="agents-toast" id="agents-toast"></div>
      <div class="modal-body agents-body" id="agents-body"></div>
    </div>
  `;
  document.body.appendChild(modal);

  // Draggable like the other panels
  {
    const content = modal.querySelector('.modal-content');
    const header = modal.querySelector('.modal-header');
    if (content && header) makeWindowDraggable(modal, { content, header });
  }

  document.getElementById('agents-close').addEventListener('click', closeAgents);
  modal.addEventListener('click', (e) => { if (e.target === modal) closeAgents(); });
  _escHandler = (e) => { if (e.key === 'Escape') closeAgents(); };
  document.addEventListener('keydown', _escHandler);

  _renderList();
  _refresh();
  _pollTimer = setInterval(_refresh, 3000);
}

export function closeAgents() {
  if (!_open) return;
  _open = false;
  if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
  if (_escHandler) { document.removeEventListener('keydown', _escHandler); _escHandler = null; }
  const modal = document.getElementById('agents-modal');
  if (modal) {
    const content = modal.querySelector('.modal-content');
    if (content) {
      content.classList.add('modal-closing');
      content.addEventListener('animationend', () => modal.remove(), { once: true });
      setTimeout(() => { if (modal.parentElement) modal.remove(); }, 250);
    } else {
      modal.remove();
    }
  }
}

export function isAgentsOpen() {
  return _open;
}

const agentsModule = { openAgents, closeAgents, isAgentsOpen };
export default agentsModule;
window.agentsModule = agentsModule;
