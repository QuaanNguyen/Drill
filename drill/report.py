import html
import json

from drill.dashboard_ui import SCRIPT, STYLE
from drill.logo import svg
from drill.settings import load_goals, load_settings


def render(state, live=False):
    state = {'campaigns': state.get('campaigns', []), 'goals': state.get('goals', []), 'settings': state.get('settings', {}), 'errors': state.get('errors', [])}
    selected = state['campaigns'][0] if state['campaigns'] else None
    escape = lambda value: html.escape(str(value), quote=True)
    title = selected['name'] if selected else 'Drill'
    reference = selected.get('incumbent') if selected else None
    score = reference['score'] if reference else None
    objective = selected['objective'] if selected else {}
    attempts = selected['attempts'] if selected else []
    rows = []
    for row in reversed(attempts):
        value = '·' if row['score'] is None else f'{row["score"]:g}'
        evidence = f'/campaigns/{selected["campaign"]}/attempts/{row["attempt_id"]}/record.json' if live else f'attempts/{row["attempt_id"]}/record.json'
        rows.append(f'<tr><td class="mono muted">{escape(row["attempt_id"])}</td><td><span class="badge {escape(row["verdict"].lower())}">{escape(row["verdict"].lower())}</span></td><td class="mono">{escape(value)}</td><td class="hypothesis">{escape(row["hypothesis"])}</td><td class="mono muted">{escape(row["source_commit"][:10])}</td><td><a href="{escape(evidence)}">Receipt ↗</a></td></tr>')
    serialized = json.dumps(state, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><title>{escape(title)} · Drill</title><style>{STYLE}</style></head>
<body data-live="{str(live).lower()}"><div class="shell">
<aside class="sidebar" aria-label="Research sidebar">
<a href="#research" class="brand" aria-label="Drill home"><span class="logo-light">{svg()}</span><span class="logo-dark">{svg(True)}</span><span>DRILL</span></a>
<nav class="sidebar-nav" aria-label="Main navigation"><button class="nav-button active" type="button" data-page="research" aria-current="page"><span class="nav-icon" aria-hidden="true">▦</span>Research</button><button class="nav-button" type="button" data-page="setup"><span class="nav-icon" aria-hidden="true">⌘</span>Setup</button></nav>
<div class="side-label">Saved goals</div><div class="goal-list" id="goal-list"></div>
<form class="goal-compose" id="goal-form"><label class="field-label" for="goal-input" hidden>New goal</label><textarea id="goal-input" placeholder="What do you want to improve?" aria-label="New goal" maxlength="4000" required></textarea><button class="primary" id="goal-save" type="submit">Save goal</button></form>
<div class="sidebar-bottom"><div class="sidebar-note" id="offline-note" hidden>Offline report · changes disabled</div></div>
</aside>
<main class="main"><div class="topbar"><div class="breadcrumb"><span>Workspace</span><span aria-hidden="true">/</span><span id="breadcrumb-page">Research</span></div><div class="top-actions"><label for="campaign-select" hidden>Campaign</label><select id="campaign-select" aria-label="Campaign"></select><button type="button" id="refresh" class="icon-button" aria-label="Refresh campaign data">↻</button></div></div>
<section id="research-page" aria-labelledby="campaign-title"><div class="page-heading"><div><h1 id="campaign-title">{escape(title)}</h1><div class="eyebrow" id="campaign-meta">{escape(objective.get('metric', ''))}</div><p class="goal-selected" id="goal-selected" hidden></p></div></div>
<div class="stats"><div class="stat"><div class="stat-label">Best accepted result</div><div class="stat-value"><span id="current-score">{escape('·' if score is None else f'{score:g}')}</span><span class="unit" id="score-unit">{escape(objective.get('unit', ''))}</span></div></div><div class="stat"><div class="stat-label">Experiments</div><div class="stat-value" id="attempt-count">{len(attempts)}</div></div><div class="stat"><div class="stat-label">Accepted changes</div><div class="stat-value" id="accepted-count">{sum(row['verdict'] == 'ACCEPTED' for row in attempts)}</div></div></div>
<div class="card"><div class="card-heading"><h2>Measurements</h2><small id="measurement-count">{escape(selected['campaign'] if selected else '')}</small></div><div class="chart" id="chart"></div></div>
<div class="card"><div class="card-heading"><h2>Experiments</h2></div><div class="table-wrap"><table><thead><tr><th>Attempt</th><th>Decision</th><th id="metric-heading">{escape(objective.get('unit', 'Score'))}</th><th>Hypothesis</th><th>Revision</th><th>Evidence</th></tr></thead><tbody id="attempt-rows">{''.join(rows)}</tbody></table></div><div class="empty" id="attempt-empty" {'hidden' if attempts else ''}>No experiments yet.</div></div>
<div id="research-status" class="status" role="status" aria-live="polite"></div><div class="page-footer"><span>Acceptance follows the campaign's configured checks.</span><span>Drill</span></div></section>
<section id="setup-page" class="settings-wrap" aria-labelledby="setup-title" hidden><div class="page-heading"><h1 id="setup-title">Setup</h1></div>
<form id="setup-form"><div class="card settings-card"><h2>Research driver</h2><div class="field"><label for="driver">Driver</label><select id="driver"><option value="current_agent">Current repository agent</option><option value="model_api">Custom model API</option></select></div><div id="api-fields" hidden><div class="field"><label for="endpoint">API endpoint</label><input id="endpoint" type="url" placeholder="https://api.example.com/v1/chat/completions" autocomplete="off"></div><div class="field-grid"><div class="field"><label for="model">Model</label><input id="model" type="text" placeholder="Model name" autocomplete="off"></div><div class="field"><label for="api_key_env">API key environment variable</label><input id="api_key_env" type="text" placeholder="MODEL_API_KEY" autocomplete="off" spellcheck="false"><span class="field-hint">Environment variable name only.</span></div></div></div></div>
<div class="card settings-card"><h2>New campaign inputs</h2><label class="check-row"><input type="checkbox" id="submodules">Materialize submodules</label><label class="check-row"><input type="checkbox" id="lfs">Materialize Git LFS files</label><label class="check-row"><input type="checkbox" id="allow_network">Allow fetching missing source inputs</label></div><div class="form-actions"><button id="setup-save" type="submit" class="primary">Save setup</button><div id="setup-status" class="status" role="status" aria-live="polite"></div></div></form>
<div class="card settings-card" id="model-card" hidden style="margin-top:24px"><h2>Model connection</h2><form id="model-form"><div class="field"><label for="model-prompt">Prompt</label><textarea id="model-prompt" rows="3" placeholder="Enter a prompt" required maxlength="12000"></textarea></div><div class="form-actions"><button type="submit" id="model-call" class="secondary">Call model</button><div id="model-status" class="status" role="status" aria-live="polite"></div></div><pre id="model-output" class="model-output" hidden></pre></form></div>
</section></main></div><script id="drill-state" type="application/json">{serialized}</script><script>{SCRIPT}</script></body></html>
'''


def dashboard(campaign):
    path = campaign.path / 'report.html'
    path.write_text(render({'campaigns': [campaign.status()], 'goals': load_goals(campaign.repo), 'settings': load_settings(campaign.repo)}))
    return {'path': str(path)}
