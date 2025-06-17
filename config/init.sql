-- IoT Monitoring Database Initialization
-- PostgreSQL database setup for processed data

-- Create database extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Raw telemetry table (for debugging/backup)
CREATE TABLE IF NOT EXISTS raw_telemetry (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    machine_id VARCHAR(50) NOT NULL,
    temperature DECIMAL(5,2),
    speed INTEGER,
    state VARCHAR(20),
    alarm BOOLEAN,
    oee DECIMAL(4,3),
    operator_name VARCHAR(100),
    shift VARCHAR(20),
    production_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Processed KPI table (for Grafana)
CREATE TABLE IF NOT EXISTS machine_kpi (
    id SERIAL PRIMARY KEY,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    machine_id VARCHAR(50) NOT NULL,
    avg_temperature DECIMAL(5,2),
    max_temperature DECIMAL(5,2),
    min_temperature DECIMAL(5,2),
    avg_speed INTEGER,
    max_speed INTEGER,
    avg_oee DECIMAL(4,3),
    alarm_count INTEGER,
    state_running_time INTEGER, -- seconds
    state_idle_time INTEGER,    -- seconds
    state_maintenance_time INTEGER, -- seconds
    production_count_delta INTEGER,
    uptime_percentage DECIMAL(5,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(window_start, machine_id)
);

-- Alarms table
CREATE TABLE IF NOT EXISTS machine_alarms (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    machine_id VARCHAR(50) NOT NULL,
    alarm_type VARCHAR(50),
    severity VARCHAR(20) DEFAULT 'MEDIUM',
    temperature DECIMAL(5,2),
    speed INTEGER,
    message TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_raw_telemetry_timestamp ON raw_telemetry(timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_telemetry_machine ON raw_telemetry(machine_id);
CREATE INDEX IF NOT EXISTS idx_machine_kpi_window ON machine_kpi(window_start, window_end);
CREATE INDEX IF NOT EXISTS idx_machine_kpi_machine ON machine_kpi(machine_id);
CREATE INDEX IF NOT EXISTS idx_machine_alarms_timestamp ON machine_alarms(timestamp);
CREATE INDEX IF NOT EXISTS idx_machine_alarms_machine ON machine_alarms(machine_id);
CREATE INDEX IF NOT EXISTS idx_machine_alarms_unack ON machine_alarms(acknowledged) WHERE acknowledged = FALSE;

-- Create materialized view for dashboard summary
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_summary AS
SELECT 
    machine_id,
    COUNT(*) as total_records,
    AVG(avg_temperature) as overall_avg_temp,
    MAX(max_temperature) as highest_temp,
    AVG(avg_oee) as overall_oee,
    SUM(alarm_count) as total_alarms,
    AVG(uptime_percentage) as avg_uptime,
    MAX(window_end) as last_updated
FROM machine_kpi 
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY machine_id;

-- Create unique index on materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_summary_machine 
ON dashboard_summary(machine_id);

-- Function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_dashboard_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_summary;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions for application user
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'iot_app') THEN
        CREATE ROLE iot_app WITH LOGIN PASSWORD 'iot_password';
    END IF;
END
$$;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO iot_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO iot_app;
GRANT SELECT ON dashboard_summary TO iot_app;

-- Insert sample data for testing (optional)
INSERT INTO machine_kpi (
    window_start, window_end, machine_id, 
    avg_temperature, max_temperature, min_temperature,
    avg_speed, max_speed, avg_oee, alarm_count,
    state_running_time, state_idle_time, state_maintenance_time,
    production_count_delta, uptime_percentage
) VALUES 
(NOW() - INTERVAL '1 hour', NOW() - INTERVAL '59 minutes', 'MACHINE_001', 
 45.5, 48.2, 42.1, 1050, 1100, 0.875, 0, 3540, 120, 0, 85, 98.5),
(NOW() - INTERVAL '1 hour', NOW() - INTERVAL '59 minutes', 'MACHINE_002', 
 52.3, 55.8, 49.7, 980, 1050, 0.792, 1, 3420, 180, 0, 78, 95.2),
(NOW() - INTERVAL '1 hour', NOW() - INTERVAL '59 minutes', 'MACHINE_003', 
 38.9, 42.1, 35.6, 1120, 1180, 0.923, 0, 3600, 0, 0, 92, 100.0)
ON CONFLICT (window_start, machine_id) DO NOTHING;