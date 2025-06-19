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

-- Table: Machine Metrics (5-minute aggregations)
CREATE TABLE IF NOT EXISTS machine_metrics_5min (
    id SERIAL PRIMARY KEY,
    machine_id VARCHAR(50) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,  -- Changed to TIMESTAMPTZ
    window_end TIMESTAMPTZ NOT NULL,    -- Changed to TIMESTAMPTZ
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
    total_readings INTEGER,
    operator_name VARCHAR(100),
    shift VARCHAR(20),
    location VARCHAR(200),
    firmware_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP  -- Changed to TIMESTAMPTZ
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

-- Real-time machine status (last 5 minutes)
CREATE OR REPLACE VIEW current_machine_status AS
SELECT 
    m.machine_id,
    m.avg_temperature,
    m.max_temperature,
    m.avg_speed,
    m.avg_oee,
    m.alarm_count,
    ROUND(CAST((m.running_seconds::FLOAT / (m.running_seconds + m.maintenance_seconds + m.idle_seconds)) * 100 AS NUMERIC), 2) as availability_pct,
    m.operator_name,
    m.shift,
    m.location,
    m.window_start,
    m.window_end
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

-- Grant permissions on views
GRANT SELECT ON current_machine_status TO iot_user;
GRANT SELECT ON recent_alerts_summary TO iot_user;
GRANT SELECT ON factory_performance_trends TO iot_user;

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