"""Generates the CALARO Grafana dashboards (JSON) from readable Python.

Edit this file, then run:  python deploy/grafana/build_dashboards.py
Grafana picks up the files in deploy/grafana/dashboards/ on start (and every 30 s).
"""
import json
from pathlib import Path

OUT = Path(__file__).parent / "dashboards"
PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "loki"}

LEAF, TURMERIC, CHILLI, GREEN, STEEL = "#1f6a4f", "#e8a317", "#c8372d", "#3e7d4f", "#66746d"

_id = 0


def nid():
    global _id
    _id += 1
    return _id


def target(expr, legend="", ds=PROM, instant=False, ref="A"):
    t = {"datasource": ds, "expr": expr, "refId": ref, "legendFormat": legend}
    if ds is PROM:
        t.update({"instant": instant, "range": not instant})
    else:
        t.update({"queryType": "instant" if instant else "range"})
    return t


def stat(title, expr, x, y, w=4, h=4, unit="short", decimals=None, thresholds=None, desc="", color_mode="value"):
    steps = thresholds or [{"color": LEAF, "value": None}]
    p = {
        "id": nid(), "type": "stat", "title": title, "description": desc, "datasource": PROM,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [target(expr, instant=True)],
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "thresholds"},
                                     "thresholds": {"mode": "absolute", "steps": steps}}, "overrides": []},
        "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                    "colorMode": color_mode, "graphMode": "none", "justifyMode": "auto", "textMode": "value",
                    "orientation": "auto"},
    }
    if decimals is not None:
        p["fieldConfig"]["defaults"]["decimals"] = decimals
    return p


def ts(title, targets, x, y, w=12, h=8, unit="short", stack=False, bars=False, desc="", ds=PROM, overrides=None):
    return {
        "id": nid(), "type": "timeseries", "title": title, "description": desc, "datasource": ds,
        "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets,
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "palette-classic"},
                                     "custom": {"drawStyle": "bars" if bars else "line", "lineWidth": 2,
                                                "fillOpacity": 70 if bars else 12, "showPoints": "never",
                                                "stacking": {"mode": "normal" if stack else "none", "group": "A"},
                                                "spanNulls": True}},
                        "overrides": overrides or []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
    }


def bars(title, expr, legend, x, y, w=8, h=8, unit="short", desc="", ds=PROM):
    return {
        "id": nid(), "type": "bargauge", "title": title, "description": desc, "datasource": ds,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [target(expr, legend, ds=ds, instant=True)],
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "fixed", "fixedColor": LEAF}, "min": 0}, "overrides": []},
        "options": {"orientation": "horizontal", "displayMode": "basic", "showUnfilled": True, "valueMode": "text",
                    "namePlacement": "left", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
    }


def pie(title, expr, legend, x, y, w=8, h=8, desc=""):
    return {
        "id": nid(), "type": "piechart", "title": title, "description": desc, "datasource": PROM,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [target(expr, legend, instant=True)],
        "fieldConfig": {"defaults": {"color": {"mode": "palette-classic"}}, "overrides": []},
        "options": {"pieType": "donut", "legend": {"displayMode": "table", "placement": "right", "values": ["value", "percent"], "showLegend": True},
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "tooltip": {"mode": "single"}},
    }


def logs(title, expr, x, y, w=24, h=12, desc=""):
    return {
        "id": nid(), "type": "logs", "title": title, "description": desc, "datasource": LOKI,
        "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": [target(expr, ds=LOKI)],
        "options": {"showTime": True, "wrapLogMessage": True, "prettifyLogMessage": False, "enableLogDetails": True,
                    "sortOrder": "Descending", "dedupStrategy": "none"},
    }


def row(title, y):
    return {"id": nid(), "type": "row", "title": title, "collapsed": False, "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []}


def color(name, hex_):
    return {"matcher": {"id": "byName", "options": name}, "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": hex_}}]}


def dashboard(uid, title, panels, desc, variables=None, time_from="now-24h"):
    return {
        "uid": uid, "title": title, "description": desc, "tags": ["calaro"], "timezone": "Asia/Kolkata",
        "schemaVersion": 39, "version": 1, "editable": False, "graphTooltip": 1, "refresh": "30s",
        "time": {"from": time_from, "to": "now"}, "fiscalYearStartMonth": 0, "liveNow": False,
        "templating": {"list": variables or []}, "annotations": {"list": []}, "links": [], "panels": panels,
    }


OK_WARN_BAD = lambda warn, bad: [{"color": GREEN, "value": None}, {"color": TURMERIC, "value": warn}, {"color": CHILLI, "value": bad}]


# ======================================================================= Overview
def overview():
    global _id
    _id = 0
    p = []
    y = 0
    p += [
        stat("API requests / min", "sum(rate(http_requests_total[5m])) * 60", 0, y, unit="reqpm", decimals=1,
             desc="Calls to the CALARO API in the last 5 minutes."),
        stat("Server errors", '100 * sum(rate(http_requests_total{status="5xx"}[5m])) / clamp_min(sum(rate(http_requests_total[5m])), 0.0001)',
             4, y, unit="percent", decimals=2, thresholds=OK_WARN_BAD(1, 5), color_mode="background",
             desc="Share of API calls that failed with a 5xx error, last 5 minutes."),
        stat("API speed (p95)", "histogram_quantile(0.95, sum by (le) (rate(http_request_duration_highr_seconds_bucket[5m])))",
             8, y, unit="s", decimals=2, thresholds=OK_WARN_BAD(0.8, 2), color_mode="background",
             desc="95% of API calls finished faster than this."),
        stat("People who logged today", 'calaro_active_users{window="24h"}', 12, y, desc="People who saved at least one meal in the last 24 hours."),
        stat("Meals today", "calaro_meals_today", 16, y, desc="Meals saved since midnight IST."),
        stat("New sign-ups (24 h)", 'calaro_new_users{window="24h"}', 20, y),
    ]
    y += 4
    p.append(row("Traffic", y)); y += 1
    p += [
        ts("Site traffic: every request through Caddy", [target("sum by (code) (rate(caddy_http_request_duration_seconds_count[$__rate_interval])) * 60", "{{code}}")],
           0, y, unit="reqpm", stack=True, desc="Pages, files and API calls hitting calaro.online, per minute, by HTTP status."),
        ts("API calls by result", [target("sum by (status) (rate(http_requests_total[$__rate_interval])) * 60", "{{status}}")],
           12, y, unit="reqpm", stack=True, overrides=[color("2xx", LEAF), color("4xx", TURMERIC), color("5xx", CHILLI), color("3xx", STEEL)]),
    ]
    y += 8
    p += [
        ts("API speed", [
            target("histogram_quantile(0.50, sum by (le) (rate(http_request_duration_highr_seconds_bucket[$__rate_interval])))", "p50", ref="A"),
            target("histogram_quantile(0.95, sum by (le) (rate(http_request_duration_highr_seconds_bucket[$__rate_interval])))", "p95", ref="B"),
            target("histogram_quantile(0.99, sum by (le) (rate(http_request_duration_highr_seconds_bucket[$__rate_interval])))", "p99", ref="C"),
        ], 0, y, unit="s", overrides=[color("p50", LEAF), color("p95", TURMERIC), color("p99", CHILLI)]),
        bars("Slowest endpoints (p95)", 'topk(8, histogram_quantile(0.95, sum by (le, handler) (rate(http_request_duration_seconds_bucket{handler!="none"}[$__range]))))',
             "{{handler}}", 12, y, w=12, unit="s"),
    ]
    y += 8
    p += [
        bars("Busiest endpoints", 'topk(10, sum by (handler) (increase(http_requests_total{handler!="none"}[$__range])))', "{{handler}}", 0, y),
        bars("Endpoints with server errors", 'topk(10, sum by (handler) (increase(http_requests_total{status="5xx"}[$__range])) > 0)', "{{handler}}", 8, y,
             desc="Empty is good."),
        ts("Sign-ins", [target("sum by (result) (increase(calaro_logins_total[$__rate_interval]))", "{{result}}")], 16, y, w=8, bars=True,
           overrides=[color("success", LEAF), color("failure", CHILLI)], desc="A spike in failures can mean someone is guessing passwords."),
    ]
    y += 8
    p.append(row("Product", y)); y += 1
    p += [
        stat("Members", 'calaro_users{role="user"}', 0, y),
        stat("Finished setup", '100 * calaro_users_onboarded / clamp_min(calaro_users{role="user"}, 1)', 4, y, unit="percent", decimals=0),
        stat("Active this week", 'calaro_active_users{window="7d"}', 8, y),
        stat("Active this month", 'calaro_active_users{window="30d"}', 12, y),
        stat("Meals stored", "calaro_meals_stored", 16, y),
        stat("Average meal", "sum(increase(calaro_meal_calories_sum[$__range])) / clamp_min(sum(increase(calaro_meal_calories_count[$__range])), 1)",
             20, y, unit="none", decimals=0, desc="Average kcal per saved meal in the selected time range."),
    ]
    y += 4
    p += [
        ts("Meals saved, by language", [target("sum by (language) (increase(calaro_meals_logged_total[$__interval]))", "{{language}}")],
           0, y, bars=True, stack=True),
        ts("Did CALARO understand the meal?", [target("sum by (outcome) (increase(calaro_vaani_requests_total[$__interval]))", "{{outcome}}")],
           12, y, bars=True, stack=True,
           overrides=[color("matched", LEAF), color("ai_estimate", TURMERIC), color("no_match", CHILLI), color("speech_error", CHILLI)],
           desc="matched = found in the Indian food database; no_match = nothing recognised; speech_error = Bhashini could not transcribe."),
    ]
    y += 8
    p += [
        pie("Member goals", "calaro_member_goals", "{{goal}}", 0, y),
        pie("Voice or typed", "sum by (mode) (increase(calaro_vaani_requests_total[$__range]))", "{{mode}}", 8, y),
        ts("Bhashini response time (p95)", [
            target("histogram_quantile(0.95, sum by (le, task) (rate(calaro_bhashini_request_seconds_bucket[$__rate_interval])))", "{{task}}", ref="A"),
        ], 16, y, w=8, unit="s", desc="How long India's Bhashini speech and translation service takes to answer."),
    ]
    return dashboard("calaro-overview", "CALARO overview", p, "Traffic, errors, speed and how people use CALARO.")


# ======================================================================= Server
def server():
    global _id
    _id = 0
    p = []
    y = 0
    p += [
        stat("Services up", "sum(up)", 0, y, desc="Monitored services answering right now."),
        stat("Services down", "count(up == 0) or vector(0)", 4, y, thresholds=[{"color": GREEN, "value": None}, {"color": CHILLI, "value": 1}], color_mode="background"),
        stat("CPU", '100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])))', 8, y, unit="percent", decimals=0, thresholds=OK_WARN_BAD(70, 90)),
        stat("Memory", "100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)", 12, y, unit="percent", decimals=0, thresholds=OK_WARN_BAD(75, 90)),
        stat("Disk", '100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})', 16, y,
             unit="percent", decimals=0, thresholds=OK_WARN_BAD(75, 90)),
        stat("Server uptime", "time() - node_boot_time_seconds", 20, y, unit="s", decimals=0),
    ]
    y += 4
    p += [
        ts("CPU", [target('100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[$__rate_interval])))', "used %")], 0, y, unit="percent"),
        ts("Memory", [
            target("node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes", "used", ref="A"),
            target("node_memory_MemTotal_bytes", "total", ref="B"),
        ], 12, y, unit="bytes"),
    ]
    y += 8
    p += [
        ts("Network", [
            target('sum(rate(node_network_receive_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[$__rate_interval]))', "in", ref="A"),
            target('sum(rate(node_network_transmit_bytes_total{device!~"lo|veth.*|docker.*|br-.*"}[$__rate_interval]))', "out", ref="B"),
        ], 0, y, unit="Bps"),
        ts("Disk space left", [target('node_filesystem_avail_bytes{mountpoint="/"}', "free")], 12, y, unit="bytes"),
    ]
    y += 8
    p += [
        ts("API process memory", [target('process_resident_memory_bytes{job="backend"}', "backend")], 0, y, w=8, unit="bytes"),
        ts("API process CPU", [target('rate(process_cpu_seconds_total{job="backend"}[$__rate_interval])', "backend")], 8, y, w=8, unit="percentunit"),
        bars("Service status (1 = up)", "up", "{{job}}", 16, y, w=8),
    ]
    return dashboard("calaro-server", "CALARO server", p, "Health of the machine and the services running CALARO.", time_from="now-6h")


# ======================================================================= Logs
def logs_dash():
    global _id
    _id = 0
    variables = [
        {"name": "service", "label": "Service", "type": "query", "datasource": LOKI,
         "query": {"label": "service", "stream": "", "type": 1, "refId": "LokiVariableQueryEditor-VariableQuery"},
         "definition": "label_values(service)", "includeAll": True, "multi": True, "allValue": ".+",
         "current": {"selected": True, "text": ["All"], "value": ["$__all"]}, "refresh": 2, "sort": 1},
        {"name": "search", "label": "Search text", "type": "textbox", "query": "", "current": {"value": "", "text": ""}},
    ]
    p = []
    y = 0
    p += [
        ts("Log lines by service", [target('sum by (service) (count_over_time({service=~"$service"} |~ "(?i)$search" [$__interval]))', "{{service}}", ds=LOKI)],
           0, y, bars=True, stack=True, ds=LOKI),
        ts("Warnings and errors", [target('sum by (service, level) (count_over_time({service=~"$service", level=~"(?i)warn|warning|error|critical|fatal"} [$__interval]))',
                                          "{{service}} {{level}}", ds=LOKI)], 12, y, bars=True, stack=True, ds=LOKI),
    ]
    y += 8
    p += [
        ts("API responses by status (from request logs)",
           [target('sum by (status) (count_over_time({service="backend"} | json | msg="request" [$__interval]))', "{{status}}", ds=LOKI)],
           0, y, bars=True, stack=True, ds=LOKI),
        bars("Most visited pages", 'topk(10, sum by (uri) (count_over_time({service="caddy"} | json uri="request.uri", status="status" | uri!~"/(api|grafana|assets)/.*" | status="200" [$__range])))',
             "{{uri}}", 12, y, w=6, ds=LOKI),
        stat_unique := {
            "id": nid(), "type": "stat", "title": "Unique visitors (by IP)", "datasource": LOKI,
            "description": "Distinct visitor IP addresses in the selected range, from Caddy's access log. People on the same network count once.",
            "gridPos": {"x": 18, "y": y, "w": 6, "h": 8},
            "targets": [target('count(sum by (ip) (count_over_time({service="caddy"} | json ip="request.client_ip" [$__range])))', ds=LOKI, instant=True)],
            "fieldConfig": {"defaults": {"unit": "short", "color": {"mode": "fixed", "fixedColor": LEAF}}, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}, "colorMode": "value", "graphMode": "none", "textMode": "value"},
        },
    ]
    y += 8
    p.append(logs("Errors", '{service=~"$service", level=~"(?i)error|critical|fatal"}', 0, y, h=9))
    y += 9
    p.append(logs("Slow API calls (over 1 second)", '{service="backend"} | json | msg="request" | duration_ms > 1000', 0, y, h=8))
    y += 8
    p.append(logs("All logs", '{service=~"$service"} |~ "(?i)$search"', 0, y, h=16))
    return dashboard("calaro-logs", "CALARO logs", p, "Every container's logs, searchable. Kept for 14 days.", variables=variables, time_from="now-6h")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, dash in (("calaro-overview", overview()), ("calaro-server", server()), ("calaro-logs", logs_dash())):
        (OUT / f"{name}.json").write_text(json.dumps(dash, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {name}.json ({len(dash['panels'])} panels)")
