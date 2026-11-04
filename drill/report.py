import html

from drill.logo import svg
from pathlib import Path


def dashboard(campaign):
    status = campaign.status()
    objective = status['objective']
    reference = status['incumbent']
    escape = lambda value: html.escape(str(value), quote=True)
    scored = [row for row in status['attempts'] if row['score'] is not None]
    chart = ''
    if scored:
        values = [row['score'] for row in scored]
        low, high = min(values), max(values)
        span = high - low or max(abs(high) * .1, 1)
        points = []
        markers = []
        for index, row in enumerate(scored):
            x = 48 + index * 850 / max(len(scored) - 1, 1)
            y = 180 - (row['score'] - low) / span * 140
            points.append(f'{x:.2f},{y:.2f}')
            markers.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5"><title>{escape(row["attempt_id"])} · {escape(row["score"])} {escape(objective["unit"])}</title></circle>')
        chart = f'<svg viewBox="0 0 960 220" role="img" aria-label="Objective measurements"><text x="8" y="24">{escape(high)}</text><text x="8" y="202">{escape(low)}</text><path d="M48 16V194H930"/><polyline points="{" ".join(points)}"/>{"".join(markers)}</svg>'
    rows = []
    for row in reversed(status['attempts']):
        score = '·' if row['score'] is None else f'{row["score"]:g}'
        rows.append(f'<tr><td>{escape(row["attempt_id"])}</td><td><span class="badge {escape(row["verdict"].lower())}">{escape(row["verdict"])}</span></td><td>{escape(score)}</td><td class="hypothesis">{escape(row["hypothesis"])}</td><td><code>{escape(row["source_commit"][:10])}</code></td><td><a href="attempts/{escape(row["attempt_id"])}/record.json">JSON ↗</a></td></tr>')
    current_score = '·' if reference is None else f'{reference["score"]:g}'
    content = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(status['name'])}</title>
<style>
:root{{color-scheme:light;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#18364b;background:#F5FBFF}}
*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:1200px;margin:auto;padding:48px 32px}}header{{display:flex;gap:24px;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #4AAEED;padding-bottom:24px}}h1{{font-size:clamp(24px,4vw,38px);font-weight:500;letter-spacing:-1.5px;margin:4px 0 12px}}.eyebrow{{font-size:12px;text-transform:uppercase;letter-spacing:2px;color:#46677c}}.mark{{font-size:28px;line-height:1;letter-spacing:3px;color:#4AAEED;white-space:pre}}.mark svg{{width:64px;height:64px}}.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:28px 0}}.stat{{background:white;border:1px solid #d7e8f2;padding:20px}}.value{{font-size:32px;margin-top:12px}}.unit{{font-size:13px;color:#46677c}}.chart{{background:white;border:1px solid #d7e8f2;padding:20px;margin-bottom:28px;overflow:hidden}}.chart svg{{display:block;width:100%;max-height:280px}}.chart svg text{{font-size:11px;fill:#46677c}}.chart svg path{{fill:none;stroke:#d7e8f2}}.chart svg polyline{{fill:none;stroke:#4AAEED;stroke-width:2}}.chart svg circle{{fill:white;stroke:#4AAEED;stroke-width:2}}.table-wrap{{overflow-x:auto;border:1px solid #d7e8f2;background:white}}table{{width:100%;border-collapse:collapse;font-size:13px;text-align:left}}th{{font-size:11px;letter-spacing:1px;text-transform:uppercase;background:#edf7fd;color:#46677c}}td,th{{padding:16px;border-bottom:1px solid #e4eef5;white-space:nowrap}}td.hypothesis{{white-space:normal;min-width:220px;line-height:1.6;overflow-wrap:anywhere}}tr:last-child td{{border-bottom:0}}.badge{{display:inline-block;padding:5px 8px;font-size:10px;border:1px solid #d7e8f2}}.accepted,.baseline{{border-color:#4AAEED;background:#edf7fd}}.invalid,.failed{{border-style:dashed}}a{{color:#176b9d;text-underline-offset:4px}}.empty{{padding:32px}}footer{{font-size:11px;color:#46677c;margin-top:20px}}@media(max-width:650px){{main{{padding:28px 16px}}.stats{{gap:8px}}.stat{{padding:12px}}.value{{font-size:25px}}.eyebrow{{font-size:10px;letter-spacing:1px}}.mark{{font-size:20px}}}}
</style></head><body><main><header><div><div class="eyebrow">Research hub / {escape(status['campaign'])}</div><h1>{escape(status['name'])}</h1><div class="unit">{escape(objective['metric'])} · {escape(objective['direction'])}</div></div><div class="mark">{svg()}</div></header>
<div class="stats"><div class="stat"><div class="eyebrow">Incumbent</div><div class="value">{escape(current_score)} <span class="unit">{escape(objective['unit'])}</span></div></div><div class="stat"><div class="eyebrow">Experiments</div><div class="value">{status['attempt_count']}</div></div><div class="stat"><div class="eyebrow">Accepted</div><div class="value">{sum(row['verdict'] == 'ACCEPTED' for row in status['attempts'])}</div></div></div>
{'<div class="chart">' + chart + '</div>' if chart else ''}<div class="table-wrap"><table><thead><tr><th>Attempt</th><th>Decision</th><th>{escape(objective['unit'])}</th><th>Hypothesis</th><th>Revision</th><th>Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table>{'<div class="empty">No experiments yet.</div>' if not rows else ''}</div><footer>Acceptance follows this campaign’s configured checks.</footer></main></body></html>
'''
    path = campaign.path / 'report.html'
    path.write_text(content)
    return {'path': str(path)}
