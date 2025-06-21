-- Industrial IoT Monitoring System
-- PostgreSQL Database Schema Initialization with Timezone Support

-- Create database and user (if needed)
-- CREATE DATABASE iot_analytics;
-- CREATE USER iot_user WITH PASSWORD 'iot_password';
-- GRANT ALL PRIVILEGES ON DATABASE iot_analytics TO iot_user;

-- Use the database
\c iot_analytics;

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO iot_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO iot_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO iot_user;

-- Clear all existing data to start fresh
DROP TABLE IF EXISTS machine_alerts CASCADE;
DROP TABLE IF EXISTS machine_metrics_5min CASCADE; 
DROP TABLE IF EXISTS factory_kpis CASCADE;
DROP TABLE IF EXISTS production_scrap CASCADE;

-- Table: Production Scrap/Waste Tracking
CREATE TABLE IF NOT EXISTS production_scrap (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    job_id VARCHAR(50),
    scrap_units INTEGER NOT NULL DEFAULT 0,
    scrap_reason VARCHAR(100),
    scrap_category VARCHAR(50), -- QUALITY, MACHINE_ERROR, MATERIAL, OPERATOR
    total_produced_units INTEGER NOT NULL DEFAULT 0,
    good_units INTEGER NOT NULL DEFAULT 0,
    scrap_rate FLOAT DEFAULT 0,
    quality_score FLOAT, -- 0-1 score based on defect severity
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Table: Machine Metrics (5-minute aggregations) - Enhanced
CREATE TABLE IF NOT EXISTS machine_metrics_5min (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(50) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    avg_temperature FLOAT,
    max_temperature FLOAT,
    min_temperature FLOAT,
    avg_speed FLOAT,
    max_speed FLOAT,
    avg_oee FLOAT,
    min_oee FLOAT,
    production_delta INTEGER,
    alarm_count INTEGER,
    running_seconds INTEGER,
    maintenance_seconds INTEGER,
    idle_seconds INTEGER,
    error_seconds INTEGER DEFAULT 0, -- New ERROR state tracking
    total_readings INTEGER,
    operator_name VARCHAR(100),
    shift VARCHAR(20),
    location VARCHAR(200),
    firmware_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    job_id VARCHAR(50),
    job_progress DOUBLE PRECISION,
    target_units INTEGER,
    produced_units INTEGER,
    good_units INTEGER DEFAULT 0,
    scrap_units INTEGER DEFAULT 0,
    scrap_rate FLOAT DEFAULT 0,
    order_start_time TIMESTAMP,
    elapsed_time_sec INTEGER,
    -- Quality metrics
    avg_quality_score FLOAT,
    defect_count INTEGER DEFAULT 0,
    downtime_incidents INTEGER DEFAULT 0
);

-- Table: Real-time Machine Alerts
CREATE TABLE IF NOT EXISTS machine_alerts (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(50) NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    alert_level VARCHAR(20) NOT NULL, -- INFO, WARNING, CRITICAL
    alert_message TEXT NOT NULL,
    machine_state VARCHAR(20),
    temperature FLOAT,
    speed FLOAT,
    oee FLOAT,
    timestamp TIMESTAMPTZ NOT NULL,  -- Changed to TIMESTAMPTZ
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- Changed to TIMESTAMPTZ
);

-- Table: Factory-wide KPIs
CREATE TABLE IF NOT EXISTS factory_kpis (
    id SERIAL PRIMARY KEY,
    scope VARCHAR(50) DEFAULT 'factory_overall',
    window_start TIMESTAMPTZ NOT NULL,  -- Changed to TIMESTAMPTZ
    window_end TIMESTAMPTZ NOT NULL,    -- Changed to TIMESTAMPTZ
    active_machines INTEGER,
    avg_temperature_all FLOAT,
    avg_speed_all FLOAT,
    avg_oee_all FLOAT,
    total_alarms INTEGER,
    availability_percentage FLOAT,
    total_production_estimate BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- Changed to TIMESTAMPTZ
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_machine_metrics_machine_time 
    ON machine_metrics_5min(machine_id, window_start DESC);

CREATE INDEX IF NOT EXISTS idx_machine_metrics_time 
    ON machine_metrics_5min(window_start DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_machine_time 
    ON machine_alerts(machine_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_level_time 
    ON machine_alerts(alert_level, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_factory_kpis_time 
    ON factory_kpis(window_start DESC);

-- New indexes for scrap tracking
CREATE INDEX IF NOT EXISTS idx_production_scrap_machine_time 
    ON production_scrap(machine_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_production_scrap_job 
    ON production_scrap(job_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_production_scrap_category 
    ON production_scrap(scrap_category, timestamp DESC);

-- Real-time machine status (last 5 minutes) - Enhanced
CREATE OR REPLACE VIEW current_machine_status AS
SELECT 
    m.machine_id,
    m.avg_temperature,
    m.max_temperature,
    m.avg_speed,
    m.avg_oee,
    m.alarm_count,
    ROUND(CAST((m.running_seconds::FLOAT / GREATEST(m.running_seconds + m.maintenance_seconds + m.idle_seconds + m.error_seconds, 1)) * 100 AS NUMERIC), 2) as availability_pct,
    ROUND(CAST((m.error_seconds::FLOAT / GREATEST(m.running_seconds + m.maintenance_seconds + m.idle_seconds + m.error_seconds, 1)) * 100 AS NUMERIC), 2) as error_pct,
    m.scrap_rate,
    m.good_units,
    m.scrap_units,
    m.produced_units,
    m.avg_quality_score,
    m.defect_count,
    m.downtime_incidents,
    m.operator_name,
    m.shift,
    m.location,
    m.window_start,
    m.window_end,
    -- Overall health score (combines OEE, scrap rate, error rate)
    ROUND(CAST((m.avg_oee * (1 - COALESCE(m.scrap_rate, 0)) * (1 - (m.error_seconds::FLOAT / GREATEST(m.running_seconds + m.maintenance_seconds + m.idle_seconds + m.error_seconds, 1)))) AS NUMERIC), 3) as health_score
FROM machine_metrics_5min m
WHERE m.window_start >= NOW() - INTERVAL '5 minutes'
ORDER BY m.machine_id, m.window_start DESC;

-- Recent alerts summary
CREATE OR REPLACE VIEW recent_alerts_summary AS
SELECT 
    machine_id,
    alert_level,
    COUNT(*) as alert_count,
    MAX(timestamp) as last_alert,
    array_agg(DISTINCT alert_type) as alert_types
FROM machine_alerts 
WHERE timestamp >= NOW() - INTERVAL '1 hour'
GROUP BY machine_id, alert_level
ORDER BY machine_id, 
    CASE alert_level 
        WHEN 'CRITICAL' THEN 1
        WHEN 'WARNING' THEN 2
        ELSE 3
    END;

-- Factory performance trends (last 24 hours)
CREATE OR REPLACE VIEW factory_performance_trends AS
SELECT 
    DATE_TRUNC('hour', window_start) as hour,
    AVG(avg_temperature_all) as avg_temp,
    AVG(avg_speed_all) as avg_speed,
    AVG(avg_oee_all) as avg_oee,
    AVG(availability_percentage) as avg_availability,
    SUM(total_alarms) as total_alarms
FROM factory_kpis 
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', window_start)
ORDER BY hour;

-- Quality and scrap monitoring views
CREATE OR REPLACE VIEW quality_metrics_summary AS
SELECT 
    machine_id,
    DATE_TRUNC('hour', timestamp) as hour,
    SUM(scrap_units) as total_scrap,
    SUM(good_units) as total_good,
    SUM(total_produced_units) as total_produced,
    ROUND(AVG(scrap_rate), 4) as avg_scrap_rate,
    ROUND(AVG(quality_score), 3) as avg_quality_score,
    COUNT(*) as scrap_incidents,
    array_agg(DISTINCT scrap_category) as scrap_categories,
    array_agg(DISTINCT scrap_reason) as scrap_reasons
FROM production_scrap 
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY machine_id, DATE_TRUNC('hour', timestamp)
ORDER BY machine_id, hour DESC;

-- Real-time scrap tracking (last hour)
CREATE OR REPLACE VIEW real_time_scrap_tracking AS
SELECT 
    s.machine_id,
    s.job_id,
    s.scrap_units,
    s.scrap_reason,
    s.scrap_category,
    s.scrap_rate,
    s.quality_score,
    s.timestamp,
    m.operator_name,
    m.shift
FROM production_scrap s
LEFT JOIN (
    SELECT DISTINCT ON (machine_id) 
        machine_id, operator_name, shift, window_start
    FROM machine_metrics_5min 
    ORDER BY machine_id, window_start DESC
) m ON s.machine_id = m.machine_id
WHERE s.timestamp >= NOW() - INTERVAL '1 hour'
ORDER BY s.timestamp DESC;

-- Machine state transitions (including ERROR state)
CREATE OR REPLACE VIEW machine_state_analysis AS
SELECT 
    machine_id,
    window_start,
    running_seconds,
    idle_seconds,
    maintenance_seconds,
    error_seconds,
    ROUND(CAST((running_seconds::FLOAT / GREATEST(running_seconds + idle_seconds + maintenance_seconds + error_seconds, 1)) * 100 AS NUMERIC), 2) as running_pct,
    ROUND(CAST((idle_seconds::FLOAT / GREATEST(running_seconds + idle_seconds + maintenance_seconds + error_seconds, 1)) * 100 AS NUMERIC), 2) as idle_pct,
    ROUND(CAST((maintenance_seconds::FLOAT / GREATEST(running_seconds + idle_seconds + maintenance_seconds + error_seconds, 1)) * 100 AS NUMERIC), 2) as maintenance_pct,
    ROUND(CAST((error_seconds::FLOAT / GREATEST(running_seconds + idle_seconds + maintenance_seconds + error_seconds, 1)) * 100 AS NUMERIC), 2) as error_pct,
    downtime_incidents,
    defect_count
FROM machine_metrics_5min
WHERE window_start >= NOW() - INTERVAL '24 hours'
ORDER BY machine_id, window_start DESC;

-- Grant permissions on views
GRANT SELECT ON current_machine_status TO iot_user;
GRANT SELECT ON recent_alerts_summary TO iot_user;
GRANT SELECT ON factory_performance_trends TO iot_user;
GRANT SELECT ON quality_metrics_summary TO iot_user;
GRANT SELECT ON real_time_scrap_tracking TO iot_user;
GRANT SELECT ON machine_state_analysis TO iot_user;

-- Set timezone for this session
SET timezone = 'UTC';

-- Sample data insertion (for testing with proper timezone)
-- INSERT INTO machine_metrics_5min (machine_id, window_start, window_end, avg_temperature, avg_speed, avg_oee, alarm_count)
-- VALUES ('MACHINE_001', NOW() - INTERVAL '5 minutes', NOW(), 45.2, 1000, 0.85, 0);

COMMENT ON TABLE machine_metrics_5min IS 'Aggregated machine metrics calculated every 5 minutes - all timestamps with timezone support';
COMMENT ON TABLE machine_alerts IS 'Real-time alerts generated by Spark streaming - timezone aware';
COMMENT ON TABLE factory_kpis IS 'Factory-wide KPIs and performance metrics - timezone aware';

-- Success message
SELECT 'Industrial IoT Database Schema with Timezone Support Created Successfully!' as status;