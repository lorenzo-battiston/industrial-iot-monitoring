import json, sys, pathlib

dashboard_path = pathlib.Path("monitoring/grafana/dashboards/iot-monitoring-dashboard.json")

data = json.loads(dashboard_path.read_text())

panels = data.get("panels", [])

# helper to update rawSql by id
def update_sql(panel_id: int, new_sql: str):
    for p in panels:
        if p.get("id") == panel_id:
            if p.get("targets") and isinstance(p["targets"], list):
                p["targets"][0]["rawSql"] = new_sql
            break

# Panel 13 scrap rate scaling
scrap_sql = (
    "SELECT \n"
    "    window_start as time, \n"
    "    CASE WHEN scrap_rate > 1 THEN scrap_rate/100 ELSE scrap_rate END as value, \n"
    "    machine_id as metric \n"
    "FROM machine_metrics_5min \n"
    "WHERE window_start >= NOW() - INTERVAL '4 hours'\n"
    "ORDER BY window_start"
)
update_sql(13, scrap_sql)

# convert panel type to table and set new sql for panel 15
for p in panels:
    if p.get("id") == 15:
        p["type"] = "table"
        p["title"] = "DAILY PRODUCTION DASHBOARD - Product Completion"
        p["targets"][0]["rawSql"] = (
            "WITH latest_metrics AS (\n"
            "    SELECT DISTINCT ON (machine_id) machine_id, target_units, produced_units\n"
            "    FROM machine_metrics_5min WHERE job_id LIKE 'JOB_%' ORDER BY machine_id, window_start DESC\n"
            "),\n"
            "pipeline_kpis AS (\n"
            "    SELECT\n"
            "        MAX(CASE WHEN machine_id = 'MACHINE_001' THEN target_units END) AS products_planned,\n"
            "        MIN(produced_units) AS products_completed\n"
            "    FROM latest_metrics\n"
            ")\n"
            "SELECT 'Products Planned' AS \"Metric\", products_planned AS \"Value\" FROM pipeline_kpis\n"
            "UNION ALL\n"
            "SELECT 'Products Completed', products_completed FROM pipeline_kpis\n"
            "UNION ALL\n"
            "SELECT 'Completion Rate', ROUND(products_completed * 100.0 / NULLIF(products_planned, 0), 1) FROM pipeline_kpis;"
        )

# convert panel 16 to table
for p in panels:
    if p.get("id") == 16:
        p["targets"][0]["rawSql"] = (
            "WITH latest_metrics AS (\n"
            "    SELECT DISTINCT ON (machine_id) machine_id, job_id, target_units, produced_units, job_progress\n"
            "    FROM machine_metrics_5min WHERE job_id LIKE 'JOB_%' ORDER BY machine_id, window_start DESC\n"
            "),\n"
            "agg AS (\n"
            "    SELECT\n"
            "        SUM(target_units)    AS products_started,\n"
            "        SUM(produced_units)  AS products_completed,\n"
            "        ROUND(AVG(job_progress*100)::numeric,1) AS avg_machine_utilization\n"
            "    FROM latest_metrics\n"
            ")\n"
            "SELECT \n"
            "  'Products Started'        AS \"Metric\", products_started   AS \"Value\" FROM agg\n"
            "UNION ALL\n"
            "SELECT 'Products Completed', products_completed FROM agg\n"
            "UNION ALL\n"
            "SELECT 'Completion Rate', ROUND((products_completed*100.0/NULLIF(products_started,0))::numeric,1) FROM agg;"
        )

# convert panel 17 to table
for p in panels:
    if p.get("id") == 17:
        p["type"] = "table"
        p["pluginVersion"] = "8.4.3"
        if "defaults" in p.get("fieldConfig", {}):
            if "unit" in p["fieldConfig"]["defaults"]:
                del p["fieldConfig"]["defaults"]["unit"]
        p["title"] = "PRODUCTION PIPELINE STATUS - Overall Efficiency"
        p["targets"][0]["rawSql"] = (
            "WITH latest AS (\n"
            "  SELECT DISTINCT ON (machine_id) machine_id, target_units, produced_units, job_progress\n"
            "  FROM machine_metrics_5min\n"
            "  WHERE job_id LIKE 'JOB_%'\n"
            "  ORDER BY machine_id, window_start DESC\n"
            "), agg AS (\n"
            "  SELECT SUM(produced_units) AS processed, SUM(target_units) AS target,\n"
            "         ROUND(AVG(job_progress*100)::numeric,1) AS avg_util\n"
            "  FROM latest\n"
            ")\n"
            "SELECT 'Pipeline Efficiency' AS \"Metric\", ROUND((processed*100.0/NULLIF(target,0))::numeric,1) AS \"Value\" FROM agg\n"
            "UNION ALL\n"
            "SELECT 'Average Machine Utilisation', avg_util FROM agg;"
        )

# Add Stage Breakdown table panel if not exists
stage_panel_id = 18
exists = any(p.get("id") == stage_panel_id for p in panels)
if not exists:
    stage_sql = (
        "WITH latest AS (\n"
        "  SELECT DISTINCT ON (machine_id) machine_id, target_units, produced_units\n        FROM machine_metrics_5min\n        WHERE job_id LIKE 'JOB_%'\n        ORDER BY machine_id, window_start DESC\n        )\n"
        "SELECT CASE machine_id\n"
        "         WHEN 'MACHINE_001' THEN 'Stage 1 (Processing)'\n"
        "         WHEN 'MACHINE_002' THEN 'Stage 2 (Assembly)'\n"
        "         WHEN 'MACHINE_003' THEN 'Stage 3 (Quality)'\n"
        "         WHEN 'MACHINE_004' THEN 'Stage 4 (Packaging)'\n"
        "         WHEN 'MACHINE_005' THEN 'Stage 5 (Shipping)'\n"
        "       END AS stage,\n"
        "       produced_units AS processed,\n"
        "       target_units   AS capacity,\n"
        "       ROUND(produced_units*100.0/NULLIF(target_units,0),1) AS pct\n"
        "FROM latest\nORDER BY stage;"
    )
    stage_panel = {
        "id": stage_panel_id,
        "title": "Pipeline Stage Breakdown",
        "type": "table",
        "datasource": "PostgreSQL IoT Analytics",
        "gridPos": {"h": 6, "w": 24, "x": 0, "y": 40},
        "targets": [
            {
                "format": "table",
                "rawQuery": True,
                "group": [],
                "metricColumn": "none",
                "rawSql": stage_sql,
                "refId": "A"
            }
        ]
    }
    panels.append(stage_panel)

# --- NEW: OEE PANEL (ID 3) - scale to percentage and adjust thresholds ---
def update_oee_panel():
    for p in panels:
        if p.get("id") == 3:
            # update query (multiply by 100)
            if p.get("targets") and isinstance(p["targets"], list):
                oee_sql = (
                    "SELECT \n"
                    "    window_start as time, \n"
                    "    (avg_oee * 100) as value, \n"
                    "    machine_id as metric \n"
                    "FROM machine_metrics_5min \n"
                    "WHERE window_start >= NOW() - INTERVAL '4 hours'\n"
                    "    AND avg_oee IS NOT NULL\n"
                    "ORDER BY window_start"
                )
                p["targets"][0]["rawSql"] = oee_sql
            # update y-axis limits & default thresholds to the 0-100 scale
            defaults = p.setdefault("fieldConfig", {}).setdefault("defaults", {})
            defaults["min"] = 0
            defaults["max"] = 100
            # update thresholds steps (green >=85, yellow >=70)
            th_steps = [
                {"color": "red", "value": None},
                {"color": "yellow", "value": 70},
                {"color": "green", "value": 85},
            ]
            defaults.setdefault("thresholds", {})["steps"] = th_steps
            break

update_oee_panel()

# --- NEW: MACHINE STATUS OVERVIEW TABLE (ID 5) ---
def update_machine_status_table():
    for p in panels:
        if p.get("id") == 5:
            if p.get("targets") and isinstance(p["targets"], list):
                status_sql = (
                    "SELECT\n"
                    "    DISTINCT ON (machine_id)\n"
                    "    machine_id,\n"
                    "    window_start as \"Last Update\",\n"
                    "    ROUND(avg_temperature::numeric, 1)          as avg_temperature,\n"
                    "    ROUND(avg_speed::numeric, 1)                as avg_speed,\n"
                    "    ROUND(avg_oee::numeric * 100, 1)            as avg_oee,\n"
                    "    alarm_count,\n"
                    "    operator_name,\n"
                    "    shift,\n"
                    "    location\n"
                    "FROM machine_metrics_5min\n"
                    "ORDER BY machine_id, window_start DESC;"
                )
                p["targets"][0]["rawSql"] = status_sql
            # ensure percent unit & thresholds for avg_oee override
            for ov in p.get("fieldConfig", {}).get("overrides", []):
                if ov.get("matcher", {}).get("options") == "avg_oee":
                    # unit percent
                    for prop in ov.get("properties", []):
                        if prop.get("id") == "unit":
                            prop["value"] = "percent"
                        if prop.get("id") == "thresholds":
                            prop["value"]["steps"] = [
                                {"color": "red", "value": None},
                                {"color": "yellow", "value": 70},
                                {"color": "green", "value": 85},
                            ]
            break

update_machine_status_table()

# remove options from converted tables
for p in panels:
    if p.get("id") in [15, 17]:
        if "options" in p:
            del p["options"]

# save
dashboard_path.write_text(json.dumps(data, indent=2))
print("Dashboard updated - step2") 