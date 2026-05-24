# =============================================================================
# dashboard.py — Local web dashboard (Flask)
# =============================================================================
# Opens in your aunt's browser at http://localhost:5000
# Shows sync history, today's status, and a 30-day sales chart.
# Also provides a "Sync Now" button to manually trigger a sync.
#
# Run: python main.py dashboard
# =============================================================================

import logging
import json
from datetime import date, timedelta, datetime
import threading
import webbrowser

from flask import Flask, render_template_string, jsonify, redirect, url_for

import config
import sync_tracker
import crunchtime_client
import retry_handler

logger = logging.getLogger(__name__)
app = Flask(__name__)

# ---------------------------------------------------------------------------
# HTML template — self-contained, no external CSS/JS dependencies
# Simple, large text, color-coded status. Designed for non-technical users.
# ---------------------------------------------------------------------------
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="300">
  <title>Sales Sync Dashboard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: Arial, sans-serif;
      background: #f4f6f9;
      color: #333;
      padding: 24px;
      max-width: 960px;
      margin: 0 auto;
    }
    h1 { font-size: 28px; margin-bottom: 6px; color: #1a1a2e; }
    .subtitle { color: #666; font-size: 14px; margin-bottom: 28px; }
    .cards { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }
    .card {
      flex: 1; min-width: 200px;
      background: white; border-radius: 10px;
      padding: 20px 24px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .card .label { font-size: 13px; color: #888; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 8px; }
    .card .value { font-size: 26px; font-weight: bold; }
    .status-ok   { color: #22a06b; }
    .status-fail { color: #e03e3e; }
    .status-warn { color: #d97706; }
    .btn {
      display: inline-block;
      padding: 12px 28px;
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 8px;
      font-size: 16px;
      cursor: pointer;
      text-decoration: none;
      margin-bottom: 28px;
    }
    .btn:hover { background: #1d4ed8; }
    .btn-danger { background: #dc2626; }
    table { width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    th { background: #1a1a2e; color: white; text-align: left; padding: 12px 16px; font-size: 13px; }
    td { padding: 12px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #f8f9ff; }
    .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }
    .badge-success { background: #dcfce7; color: #166534; }
    .badge-failed  { background: #fee2e2; color: #991b1b; }
    .badge-pending { background: #fef9c3; color: #854d0e; }
    .chart-wrap { background: white; border-radius: 10px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 28px; }
    .chart-wrap h2 { font-size: 18px; margin-bottom: 16px; color: #1a1a2e; }
    .bar-chart { display: flex; align-items: flex-end; gap: 4px; height: 140px; }
    .bar-col { display: flex; flex-direction: column; align-items: center; flex: 1; }
    .bar { background: #2563eb; border-radius: 4px 4px 0 0; width: 100%; min-height: 4px; transition: height .3s; }
    .bar-label { font-size: 9px; color: #aaa; margin-top: 4px; writing-mode: vertical-rl; transform: rotate(180deg); }
    .section-title { font-size: 18px; font-weight: bold; margin-bottom: 14px; color: #1a1a2e; }
    .flash { padding: 12px 18px; border-radius: 8px; margin-bottom: 20px; font-size: 15px; }
    .flash-ok   { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
    .flash-err  { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
  </style>
</head>
<body>

  <h1>&#x1F4CA; Sales Sync Dashboard</h1>
  <p class="subtitle">This page shows whether your sales data is being sent to QuickBooks correctly. It refreshes every 5 minutes.</p>

  {% if flash_msg %}
  <div class="flash {{ flash_class }}">{{ flash_msg }}</div>
  {% endif %}

  <!-- Status cards -->
  <div class="cards">
    <div class="card">
      <div class="label">Today's Sync</div>
      <div class="value {{ today_class }}">{{ today_status }}</div>
    </div>
    <div class="card">
      <div class="label">Last Synced</div>
      <div class="value" style="font-size:18px;">{{ last_synced }}</div>
    </div>
    <div class="card">
      <div class="label">Total Syncs</div>
      <div class="value">{{ total_syncs }}</div>
    </div>
    <div class="card">
      <div class="label">Failed (need attention)</div>
      <div class="value {{ 'status-fail' if failed_count > 0 else 'status-ok' }}">{{ failed_count }}</div>
    </div>
  </div>

  <!-- Manual trigger button -->
  <form method="POST" action="/sync-now" style="margin-bottom:28px;">
    <button type="submit" class="btn">&#x25B6; Run Sync Now</button>
    &nbsp;
    <a href="/retry-now" class="btn btn-danger">&#x21BA; Retry Failed Syncs</a>
  </form>

  <!-- 30-day sales chart -->
  <div class="chart-wrap">
    <h2>Gross Sales — Last 30 Days</h2>
    <div class="bar-chart">
      {% for bar in chart_data %}
      <div class="bar-col">
        <div class="bar" style="height:{{ bar.height_pct }}%; background: {{ bar.color }};"
             title="{{ bar.date }}: ${{ bar.amount }}"></div>
        <div class="bar-label">{{ bar.short_date }}</div>
      </div>
      {% endfor %}
    </div>
    <p style="font-size:12px;color:#aaa;margin-top:10px;">Hover over a bar to see the exact amount.</p>
  </div>

  <!-- Sync history table -->
  <div class="section-title">Sync History</div>
  <table>
    <thead>
      <tr>
        <th>Date</th>
        <th>Status</th>
        <th>Gross Sales</th>
        <th>Error (if any)</th>
        <th>Synced At</th>
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        <td>{{ row.business_date }}</td>
        <td><span class="badge badge-{{ row.status }}">{{ row.status.upper() }}</span></td>
        <td>{{ row.gross_sales }}</td>
        <td style="color:#dc2626;font-size:13px;">{{ row.error_message or '' }}</td>
        <td style="color:#888;font-size:12px;">{{ row.sync_timestamp[:16] }}</td>
      </tr>
      {% endfor %}
      {% if not rows %}
      <tr><td colspan="5" style="text-align:center;color:#aaa;padding:32px;">No sync history yet.</td></tr>
      {% endif %}
    </tbody>
  </table>

  <p style="margin-top:24px;font-size:12px;color:#bbb;">Page auto-refreshes every 5 minutes &bull; Crunchtime QBD Sync</p>
</body>
</html>
'''


def _get_dashboard_data(flash_msg=None, flash_class=None):
    """Gather all data needed to render the dashboard."""
    sync_tracker.initialize_db()
    rows = sync_tracker.get_recent_syncs(limit=60)

    # Enrich rows with parsed gross_sales from qbxml_sent (best effort)
    for r in rows:
        r['gross_sales'] = _extract_gross_sales(r.get('qbxml_sent', ''))

    # Today's status
    today_str = date.today().isoformat()
    today_row = next((r for r in rows if r['business_date'] == today_str), None)
    if today_row:
        s = today_row['status']
        today_status = 'DONE' if s == 'success' else s.upper()
        today_class  = 'status-ok' if s == 'success' else 'status-fail'
    else:
        today_status = 'Not yet'
        today_class  = 'status-warn'

    # Last synced
    success_rows = [r for r in rows if r['status'] == 'success']
    last_synced = success_rows[0]['sync_timestamp'][:16] if success_rows else 'Never'

    failed_count = sum(1 for r in rows if r['status'] == 'failed')
    total_syncs  = len(rows)

    # 30-day chart
    chart_data = _build_chart_data(rows)

    return dict(
        rows=rows[:30],
        today_status=today_status,
        today_class=today_class,
        last_synced=last_synced,
        failed_count=failed_count,
        total_syncs=total_syncs,
        chart_data=chart_data,
        flash_msg=flash_msg,
        flash_class=flash_class,
    )


def _build_chart_data(rows):
    """Build 30-day bar chart data from sync history."""
    # Build a lookup: date → gross_sales
    sales_by_date = {}
    for r in rows:
        if r['status'] == 'success' and r['business_date'] not in sales_by_date:
            sales_by_date[r['business_date']] = _extract_gross_sales(r.get('qbxml_sent', ''))

    bars = []
    today = date.today()
    amounts = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        d_str = d.isoformat()
        amt_str = sales_by_date.get(d_str, '0')
        try:
            amt = float(amt_str.replace('$', '').replace(',', '')) if amt_str != '0' else 0
        except:
            amt = 0
        amounts.append((d_str, amt, d.strftime('%m/%d')))

    max_amt = max((a for _, a, _ in amounts), default=1) or 1
    for d_str, amt, short in amounts:
        height = max(int((amt / max_amt) * 100), 2) if amt > 0 else 2
        bars.append({
            'date': d_str,
            'short_date': short,
            'amount': f'{amt:,.2f}',
            'height_pct': height,
            'color': '#2563eb' if amt > 0 else '#e5e7eb',
        })
    return bars


def _extract_gross_sales(qbxml: str) -> str:
    """Pull gross sales amount out of a stored qbXML payload (best effort)."""
    import re
    if not qbxml:
        return '—'
    # The credit line for gross sales is the second Amount in the XML
    amounts = re.findall(r'<Amount>([\d.]+)</Amount>', qbxml)
    if len(amounts) >= 2:
        try:
            return f"${float(amounts[1]):,.2f}"
        except:
            pass
    return '—'


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    data = _get_dashboard_data()
    return render_template_string(DASHBOARD_HTML, **data)


@app.route('/sync-now', methods=['POST'])
def sync_now():
    target_date = date.today() - timedelta(days=config.DEFAULT_LOOKBACK_DAYS)
    try:
        ok = retry_handler.run_sync_for_date(target_date)
        if ok:
            msg = f"Sync triggered for {target_date}. QuickBooks Web Connector will pick it up on the next poll."
            cls = 'flash-ok'
        else:
            msg = f"Sync for {target_date} encountered an error. Check the history table below."
            cls = 'flash-err'
    except Exception as exc:
        msg = f"Error: {exc}"
        cls = 'flash-err'
    data = _get_dashboard_data(flash_msg=msg, flash_class=cls)
    return render_template_string(DASHBOARD_HTML, **data)


@app.route('/retry-now')
def retry_now():
    try:
        retry_handler.retry_failed_syncs()
        msg = "Retry pass complete. Check the history table for updated statuses."
        cls = 'flash-ok'
    except Exception as exc:
        msg = f"Retry error: {exc}"
        cls = 'flash-err'
    data = _get_dashboard_data(flash_msg=msg, flash_class=cls)
    return render_template_string(DASHBOARD_HTML, **data)


@app.route('/api/status')
def api_status():
    """JSON endpoint for programmatic status checks."""
    rows = sync_tracker.get_recent_syncs(limit=5)
    return jsonify({
        'last_sync': rows[0] if rows else None,
        'failed_count': sum(1 for r in rows if r['status'] == 'failed'),
    })


def run_dashboard():
    """Launch the dashboard and open a browser tab."""
    url = f"http://localhost:{config.DASHBOARD_PORT}"
    # Open browser after a short delay so the server is ready
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"\nDashboard running at {url}")
    print("Press Ctrl+C to stop.\n")
    app.run(host='0.0.0.0', port=config.DASHBOARD_PORT, debug=False, use_reloader=False)
