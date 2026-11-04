STYLE = '''
:root{color-scheme:light dark;--bg:#f6f6f6;--panel:#fff;--sidebar:#fff;--ink:#171717;--muted:#707070;--line:#e3e3e3;--hover:#f1f1f1;--soft:#fafafa;--button:#171717;--button-ink:#fff;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
*{box-sizing:border-box}body{margin:0}button,input,select,textarea{font:inherit}button,a,input,select,textarea{-webkit-tap-highlight-color:transparent}button{cursor:pointer}button:disabled{cursor:not-allowed;opacity:.45}a{color:inherit;text-underline-offset:3px}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid var(--ink);outline-offset:3px}[hidden]{display:none!important}.shell{min-height:100vh;display:grid;grid-template-columns:264px minmax(0,1fr)}.sidebar{position:sticky;top:0;height:100vh;display:flex;flex-direction:column;padding:28px 18px 18px;background:var(--sidebar);border-right:1px solid var(--line);min-width:0}.brand{display:flex;align-items:center;gap:11px;margin:0 12px 32px;text-decoration:none;font-size:18px;font-weight:650;letter-spacing:2px}.brand svg{display:block;width:42px;height:42px}.logo-dark{display:none}.nav-button{border:0;background:transparent;color:var(--muted);padding:11px 13px;text-align:left;border-radius:7px;width:100%;display:flex;align-items:center;gap:11px;font-size:13px}.nav-button:hover,.nav-button.active{background:var(--hover);color:var(--ink)}.nav-icon{width:17px;text-align:center;font-family:ui-monospace,monospace}.side-label{font-size:10px;font-weight:600;letter-spacing:1.7px;text-transform:uppercase;color:var(--muted);margin:32px 13px 12px}.goal-list{overflow:auto;min-height:48px;flex:1;display:flex;flex-direction:column;gap:4px}.goal-item{display:block;border:0;background:transparent;color:var(--muted);text-align:left;padding:11px 13px;border-radius:7px;width:100%;line-height:1.5;font-size:12px;overflow-wrap:anywhere}.goal-item:hover,.goal-item.active{background:var(--hover);color:var(--ink)}.goal-item small{display:block;margin-top:5px;font-size:10px;opacity:.75}.goal-compose{margin-top:14px;border-top:1px solid var(--line);padding-top:16px}.goal-compose textarea{min-height:72px;font-size:12px;resize:vertical}.goal-compose button{margin-top:8px;width:100%}.sidebar-bottom{margin-top:16px}.sidebar-note{font-size:11px;color:var(--muted);padding:8px 13px 0}.main{min-width:0;padding:38px 44px 52px;max-width:1500px;width:100%;margin:0 auto}.topbar{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:34px}.breadcrumb{font-size:12px;color:var(--muted);display:flex;gap:12px;align-items:center}.breadcrumb span:last-child{color:var(--ink)}.top-actions{display:flex;gap:10px;align-items:center}.top-actions select{min-width:160px;max-width:300px}.icon-button,.secondary{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:6px;padding:9px 12px;font-size:12px}.icon-button:hover,.secondary:hover{background:var(--hover)}.page-heading{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:26px}h1{margin:0;font-weight:550;font-size:30px;letter-spacing:-1px;line-height:1.2}h2{font-size:14px;font-weight:550;margin:0}.eyebrow{font-size:11px;color:var(--muted);margin-top:10px}.direction{text-transform:capitalize}.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:20px}.stat{border:1px solid var(--line);border-radius:9px;background:var(--panel);padding:22px}.stat-label{font-size:11px;color:var(--muted);margin-bottom:17px}.stat-value{font-size:31px;letter-spacing:-1px;font-variant-numeric:tabular-nums;line-height:1.1}.unit{font-size:12px;color:var(--muted);letter-spacing:0;margin-left:7px}.card{background:var(--panel);border:1px solid var(--line);border-radius:9px;margin-bottom:20px;overflow:hidden}.card-heading{display:flex;justify-content:space-between;align-items:center;padding:20px 23px;border-bottom:1px solid var(--line)}.card-heading small{font-size:11px;color:var(--muted)}.chart{padding:22px 22px 8px;min-height:245px}.chart svg{display:block;width:100%;height:auto;max-height:280px;overflow:visible}.chart .grid{stroke:var(--line);stroke-width:1}.chart .trace{stroke:var(--ink);stroke-width:2;fill:none}.chart .point{fill:var(--panel);stroke:var(--ink);stroke-width:2}.chart text{fill:var(--muted);font:11px ui-monospace,SFMono-Regular,monospace}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;text-align:left;font-size:12px}th{font-size:10px;text-transform:uppercase;font-weight:500;letter-spacing:1px;color:var(--muted);background:var(--soft)}th,td{padding:16px 22px;border-bottom:1px solid var(--line);white-space:nowrap}tbody tr:last-child td{border-bottom:0}tbody tr:hover{background:var(--soft)}td.hypothesis{white-space:normal;min-width:220px;max-width:430px;line-height:1.6;overflow-wrap:anywhere}.mono,code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px}.badge{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:4px;padding:4px 6px;font-size:9px;text-transform:lowercase;letter-spacing:.2px}.badge:before{content:"";width:4px;height:4px;border-radius:50%;background:var(--muted)}.badge.accepted:before,.badge.baseline:before{background:var(--ink)}.badge.failed,.badge.invalid{border-style:dashed}.muted{color:var(--muted)}.empty{padding:42px 22px;text-align:center;font-size:12px;color:var(--muted);line-height:1.7}.status{font-size:12px;color:var(--muted);min-height:18px;line-height:1.6;overflow-wrap:anywhere}.status.error{color:var(--ink)}.settings-wrap{max-width:760px}.settings-card{padding:25px}.settings-card h2{margin-bottom:23px}.field{display:flex;flex-direction:column;gap:8px;margin-bottom:20px}.field:last-child{margin-bottom:0}label,.field-label{font-size:12px}input,select,textarea{width:100%;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink);padding:10px 11px;min-width:0}input::placeholder,textarea::placeholder{color:var(--muted);opacity:.75}.field-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.field-hint{font-size:11px;color:var(--muted);line-height:1.5}.check-row{display:flex;gap:10px;align-items:center;font-size:12px;margin:14px 0}.check-row input{width:15px;height:15px;accent-color:var(--ink)}.primary{border:1px solid var(--button);border-radius:6px;background:var(--button);color:var(--button-ink);padding:10px 15px;font-size:12px}.form-actions{display:flex;gap:14px;align-items:center;margin-top:22px}.model-output{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.7 ui-monospace,SFMono-Regular,monospace;background:var(--soft);padding:15px;border:1px solid var(--line);border-radius:6px;max-height:340px;overflow:auto}.page-footer{display:flex;justify-content:space-between;gap:18px;font-size:10px;color:var(--muted);margin-top:28px}.mobile-brand{display:none}.goal-selected{font-size:13px;line-height:1.7;color:var(--muted);margin:16px 0 0;max-width:850px;overflow-wrap:anywhere}
@media(prefers-color-scheme:dark){:root{--bg:#111;--panel:#181818;--sidebar:#000;--ink:#ededed;--muted:#929292;--line:#2c2c2c;--hover:#202020;--soft:#151515;--button:#ededed;--button-ink:#101010}.logo-light{display:none}.logo-dark{display:block}}
@media(max-width:1100px){.main{padding:32px 26px}.shell{grid-template-columns:230px minmax(0,1fr)}.sidebar{padding-left:12px;padding-right:12px}.stat{padding:19px}.top-actions select{max-width:220px;min-width:120px}}
@media(max-width:760px){.shell{display:block}.sidebar{position:relative;height:auto;padding:16px;border-right:0;border-bottom:1px solid var(--line)}.brand{margin:0 2px 16px}.brand svg{width:34px;height:34px}.sidebar-nav{display:flex;gap:5px}.sidebar-nav .nav-button{width:auto;flex:1;justify-content:center}.side-label{margin:20px 0 8px}.goal-list{max-height:135px;flex-direction:row;min-height:0}.goal-item{min-width:180px;max-width:260px;border:1px solid var(--line)}.goal-compose{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:start;margin-top:12px;padding-top:12px}.goal-compose textarea{min-height:42px;height:42px;resize:vertical}.goal-compose button{width:auto;margin:0;height:42px}.sidebar-bottom{margin-top:4px}.main{padding:26px 16px 36px}.topbar{margin-bottom:27px;gap:10px;flex-wrap:wrap}.top-actions{margin-left:auto}.top-actions select{max-width:200px;min-width:100px}.breadcrumb{font-size:11px}h1{font-size:26px}.stats{gap:8px}.stat{padding:16px 12px}.stat-label{font-size:10px;margin-bottom:12px;min-height:26px}.stat-value{font-size:25px}.unit{display:block;margin:8px 0 0;font-size:10px}.card-heading{padding:17px 15px}.chart{padding:18px 13px 3px;min-height:150px}.field-grid{grid-template-columns:1fr;gap:0}.settings-card{padding:20px 16px}.page-footer{line-height:1.6;flex-direction:column;gap:4px}.form-actions{align-items:flex-start;flex-direction:column}.goal-selected{font-size:12px}.page-heading{margin-bottom:22px}.status{font-size:11px}}
@media(prefers-reduced-motion:no-preference){button,a,input,select,textarea{transition:background-color .14s,border-color .14s}}
'''

SCRIPT = '''
const state = JSON.parse(document.getElementById('drill-state').textContent);
const live = document.body.dataset.live === 'true';
let selectedCampaign = state.campaigns[0]?.campaign || '';
let selectedGoal = null;
let setupDirty = false;
const byId = id => document.getElementById(id);
const text = (tag, value, className) => { const element = document.createElement(tag); element.textContent = value; if (className) element.className = className; return element; };
const format = (value, precision = 6) => {
    if (value === null || value === undefined) return '·';
    const number = Number(value), magnitude = Math.abs(number);
    return magnitude && (magnitude < .0001 || magnitude >= 1e8) ? number.toExponential(precision - 1) : number.toLocaleString(undefined, {maximumSignificantDigits: precision});
};
function notice(id, value, error = false) { const element = byId(id); element.textContent = value; element.classList.toggle('error', error); }
async function request(path, value) {
    const response = await fetch(path, {method: value === undefined ? 'GET' : 'POST', headers: {'Content-Type': 'application/json'}, body: value === undefined ? undefined : JSON.stringify(value)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'The request could not be completed.');
    return result;
}
function campaign() { return state.campaigns.find(item => item.campaign === selectedCampaign) || state.campaigns[0]; }
function page(name) {
    byId('research-page').hidden = name !== 'research';
    byId('setup-page').hidden = name !== 'setup';
    document.querySelectorAll('[data-page]').forEach(button => { button.classList.toggle('active', button.dataset.page === name); button.setAttribute('aria-current', button.dataset.page === name ? 'page' : 'false'); });
    byId('breadcrumb-page').textContent = name === 'setup' ? 'Setup' : 'Research';
    history.replaceState(null, '', name === 'setup' ? '#setup' : '#research');
    if (name === 'research') renderChart(campaign()?.attempts || []);
}
function renderGoals() {
    const list = byId('goal-list');
    list.replaceChildren();
    for (const goal of [...state.goals].reverse()) {
        const button = text('button', goal.text, 'goal-item');
        button.type = 'button';
        button.title = goal.text;
        button.classList.toggle('active', selectedGoal?.id === goal.id);
        if (goal.campaign) button.append(text('small', goal.campaign));
        button.addEventListener('click', () => { selectedGoal = goal; if (state.campaigns.some(item => item.campaign === goal.campaign)) selectedCampaign = goal.campaign; renderResearch(); renderGoals(); page('research'); });
        list.append(button);
    }
    if (!state.goals.length) list.append(text('div', 'No saved goals', 'goal-item muted'));
}
function renderChart(attempts) {
    const chart = byId('chart');
    chart.replaceChildren();
    const scored = attempts.filter(row => typeof row.score === 'number' && Number.isFinite(row.score));
    if (!scored.length) { chart.append(text('div', 'No measurements yet.', 'empty')); return; }
    const ns = 'http://www.w3.org/2000/svg';
    const element = (name, attrs) => { const node = document.createElementNS(ns, name); for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value); return node; };
    const width = Math.max(chart.clientWidth - 44, 300), start = 56, end = width - 18;
    const svg = element('svg', {viewBox: `0 0 ${width} 242`, role: 'img', 'aria-label': 'Objective measurements'});
    const values = scored.map(row => row.score);
    const min = Math.min(...values), max = Math.max(...values), span = max - min || Math.max(Math.abs(max) * .1, 1);
    const low = max === min ? min - span / 2 : min, high = low + span;
    for (let index = 0; index < 4; index++) {
        const y = 20 + index * 55;
        svg.append(element('line', {x1: start, y1: y, x2: end, y2: y, class: 'grid'}));
        const label = element('text', {x: start - 12, y: y + 4, 'text-anchor': 'end'});
        label.textContent = format(high - index / 3 * span, 3);
        svg.append(label);
    }
    const points = scored.map((row, index) => [start + index * (end - start) / Math.max(scored.length - 1, 1), 185 - (row.score - low) / span * 165]);
    svg.append(element('polyline', {points: points.map(point => point.join(',')).join(' '), class: 'trace'}));
    points.forEach(([x, y], index) => {
        const marker = element('circle', {cx: x, cy: y, r: 4, class: 'point'});
        const title = element('title', {}); title.textContent = `Attempt ${scored[index].attempt_id}: ${format(scored[index].score)}`; marker.append(title); svg.append(marker);
    });
    for (const index of [...new Set([0, scored.length - 1])]) {
        const label = element('text', {x: points[index][0], y: 219, 'text-anchor': index ? 'end' : 'start'});
        label.textContent = scored[index].attempt_id;
        svg.append(label);
    }
    chart.append(svg);
}
function renderResearch() {
    const current = campaign();
    const selector = byId('campaign-select');
    selector.replaceChildren();
    for (const item of state.campaigns) { const option = text('option', item.name || item.campaign); option.value = item.campaign; selector.append(option); }
    selector.value = current?.campaign || '';
    selector.disabled = !state.campaigns.length;
    byId('campaign-title').textContent = current?.name || 'Research';
    byId('campaign-meta').textContent = current ? `${current.objective.metric} · ${current.objective.direction === 'minimize' ? 'Lower is better' : 'Higher is better'}` : 'No campaign selected';
    byId('current-score').textContent = format(current?.incumbent?.score);
    byId('score-unit').textContent = current?.objective.unit || '';
    byId('attempt-count').textContent = current?.attempt_count || 0;
    byId('accepted-count').textContent = current?.attempts.filter(row => row.verdict === 'ACCEPTED').length || 0;
    byId('measurement-count').textContent = current ? current.campaign : '';
    byId('goal-selected').textContent = selectedGoal?.text || '';
    byId('goal-selected').hidden = !selectedGoal;
    byId('metric-heading').textContent = current?.objective.unit || 'Score';
    const body = byId('attempt-rows');
    body.replaceChildren();
    for (const row of [...(current?.attempts || [])].reverse()) {
        const tr = document.createElement('tr');
        tr.append(text('td', row.attempt_id, 'mono muted'));
        const decision = document.createElement('td'); decision.append(text('span', row.verdict.toLowerCase().replaceAll('_', ' '), `badge ${row.verdict.toLowerCase()}`)); tr.append(decision);
        tr.append(text('td', format(row.score), 'mono'));
        tr.append(text('td', row.hypothesis, 'hypothesis'));
        tr.append(text('td', row.source_commit.slice(0, 10), 'mono muted'));
        const evidence = document.createElement('td');
        const link = text('a', 'Receipt ↗');
        link.href = live ? `/campaigns/${encodeURIComponent(current.campaign)}/attempts/${encodeURIComponent(row.attempt_id)}/record.json` : `attempts/${encodeURIComponent(row.attempt_id)}/record.json`;
        evidence.append(link); tr.append(evidence); body.append(tr);
    }
    byId('attempt-empty').hidden = !!current?.attempts.length;
    renderChart(current?.attempts || []);
    if (state.errors?.length) notice('research-status', state.errors.map(item => `${item.campaign}: ${item.error}`).join('; '), true);
}
function modelFields() {
    const enabled = byId('driver').value === 'model_api';
    byId('api-fields').hidden = !enabled;
    byId('model-card').hidden = !enabled;
    byId('model-call').disabled = !live || !enabled || setupDirty;
    if (setupDirty && enabled) notice('model-status', 'Save setup before calling the model.');
    else if (byId('model-status').textContent === 'Save setup before calling the model.') notice('model-status', '');
}
function renderSettings() {
    setupDirty = false;
    const settings = state.settings || {};
    byId('driver').value = settings.driver || 'current_agent';
    for (const field of ['endpoint', 'model', 'api_key_env']) byId(field).value = settings[field] || '';
    for (const field of ['submodules', 'lfs', 'allow_network']) byId(field).checked = !!settings.materialization?.[field];
    modelFields();
}
async function refresh() {
    const next = await request('/api/state');
    state.campaigns = next.campaigns || [];
    state.goals = next.goals || [];
    state.settings = next.settings || {};
    state.errors = next.errors || [];
    renderResearch(); renderGoals(); renderSettings();
}
byId('campaign-select').addEventListener('change', event => { selectedCampaign = event.target.value; selectedGoal = null; renderResearch(); renderGoals(); });
for (const button of document.querySelectorAll('[data-page]')) button.addEventListener('click', () => page(button.dataset.page));
byId('setup-form').addEventListener('input', () => { setupDirty = true; modelFields(); });
byId('driver').addEventListener('change', () => { setupDirty = true; modelFields(); });
byId('refresh').addEventListener('click', async () => { try { await refresh(); if (!state.errors?.length) notice('research-status', 'Updated.'); } catch (error) { notice('research-status', error.message, true); } });
byId('goal-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (!live) return;
    const input = byId('goal-input');
    const value = input.value.trim();
    if (!value) return;
    const button = byId('goal-save'); button.disabled = true;
    try { await request('/api/goals', {text: value, campaign: selectedCampaign || null}); input.value = ''; await refresh(); if (!state.errors?.length) notice('research-status', 'Goal saved.'); }
    catch (error) { notice('research-status', error.message, true); }
    finally { button.disabled = false; }
});
byId('setup-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (!live) return;
    const button = byId('setup-save'); button.disabled = true;
    const settings = {driver: byId('driver').value, endpoint: byId('endpoint').value.trim(), model: byId('model').value.trim(), api_key_env: byId('api_key_env').value.trim(), materialization: {submodules: byId('submodules').checked, lfs: byId('lfs').checked, allow_network: byId('allow_network').checked}};
    try { await request('/api/settings', settings); await refresh(); notice('setup-status', 'Setup saved.'); }
    catch (error) { notice('setup-status', error.message, true); }
    finally { button.disabled = false; }
});
byId('model-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (!live) return;
    const prompt = byId('model-prompt').value.trim();
    if (!prompt) return;
    const button = byId('model-call'); button.disabled = true;
    notice('model-status', 'Calling model...');
    try { const result = await request('/api/model', {prompt}); byId('model-output').textContent = result.text || ''; byId('model-output').hidden = false; notice('model-status', 'Response received.'); }
    catch (error) { notice('model-status', error.message, true); }
    finally { modelFields(); }
});
if (!live) {
    for (const id of ['goal-input', 'goal-save', 'setup-save', 'driver', 'endpoint', 'model', 'api_key_env', 'submodules', 'lfs', 'allow_network', 'model-prompt', 'model-call', 'refresh']) byId(id).disabled = true;
    byId('offline-note').hidden = false;
}
window.addEventListener('resize', () => { if (!byId('research-page').hidden) renderChart(campaign()?.attempts || []); });
renderResearch(); renderGoals(); renderSettings();
page(location.hash === '#setup' ? 'setup' : 'research');
'''
