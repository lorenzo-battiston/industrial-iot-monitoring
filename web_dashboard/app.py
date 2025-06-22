#!/usr/bin/env python3
"""
Industrial IoT Monitoring Platform - Web Dashboard
Provides system status monitoring and control interface
"""

from flask import Flask, render_template, jsonify, request
import subprocess
import json
import time
import psycopg2
from datetime import datetime, timedelta
import os
import socket
import requests

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5433)),
    'database': os.getenv('DB_DATABASE', 'iot_analytics'),
    'user': os.getenv('DB_USER', 'iot_user'),
    'password': os.getenv('DB_PASSWORD', 'iot_password')
}

def execute_command(command):
    """Execute shell command and return result"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return {
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'output': '',
            'error': 'Command timed out'
        }
    except Exception as e:
        return {
            'success': False,
            'output': '',
            'error': str(e)
        }

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        return None

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/system/status')
def system_status():
    """Get system status"""
    services = {
        'kafka': check_kafka_health(),
        'postgres': check_postgres_health(),
        'mqtt': check_mqtt_health(),
        'grafana': check_grafana_health(),
        'spark': check_spark_health()
    }
    
    overall_health = all(service['healthy'] for service in services.values())
    
    return jsonify({
        'overall_health': overall_health,
        'services': services,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/system/metrics')
def system_metrics():
    """Get system metrics"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Get recent machine data
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT machine_id) as active_machines,
                AVG(avg_temperature) as avg_temp,
                AVG(avg_oee) as avg_oee,
                SUM(alarm_count) as total_alarms,
                AVG(scrap_rate) as avg_scrap_rate,
                SUM(error_seconds) as total_error_seconds
            FROM machine_metrics_5min 
            WHERE window_start >= NOW() - INTERVAL '1 hour'
        """)
        
        metrics = cursor.fetchone()
        
        # Get scrap summary
        cursor.execute("""
            SELECT 
                scrap_category,
                COUNT(*) as incidents,
                SUM(scrap_units) as total_scrap
            FROM production_scrap 
            WHERE timestamp >= NOW() - INTERVAL '24 hours'
            GROUP BY scrap_category
        """)
        
        scrap_data = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'active_machines': metrics[0] or 0,
            'avg_temperature': round(metrics[1] or 0, 1),
            'avg_oee': round(metrics[2] or 0, 3),
            'total_alarms': metrics[3] or 0,
            'avg_scrap_rate': round(metrics[4] or 0, 4),
            'total_error_seconds': metrics[5] or 0,
            'scrap_breakdown': [
                {
                    'category': row[0],
                    'incidents': row[1],
                    'total_scrap': row[2]
                } for row in scrap_data
            ],
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/control/<action>', methods=['POST'])
def system_control(action):
    """Control system operations"""
    if action == 'start':
        result = execute_command('make start')
    elif action == 'stop':
        result = execute_command('make stop')
    elif action == 'restart':
        result = execute_command('make restart')
    elif action == 'health':
        result = execute_command('make health')
    else:
        return jsonify({'error': 'Invalid action'}), 400
    
    return jsonify(result)

@app.route('/api/data/recent')
def recent_data():
    """Get recent telemetry data for charts"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Get recent machine metrics
        cursor.execute("""
            SELECT 
                machine_id,
                window_start,
                avg_temperature,
                avg_oee,
                scrap_rate,
                error_seconds
            FROM machine_metrics_5min 
            WHERE window_start >= NOW() - INTERVAL '2 hours'
            ORDER BY window_start DESC
            LIMIT 50
        """)
        
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        formatted_data = []
        for row in data:
            formatted_data.append({
                'machine_id': row[0],
                'timestamp': row[1].isoformat(),
                'temperature': row[2],
                'oee': row[3],
                'scrap_rate': row[4],
                'error_seconds': row[5]
            })
        
        return jsonify(formatted_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _tcp_ping(host: str, port: int, timeout: float = 3.0):
    """Return True if a TCP connection can be established."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def check_kafka_health():
    """Basic Kafka broker reachability check (TCP)."""
    healthy = _tcp_ping(os.getenv('KAFKA_HOST', 'kafka'), int(os.getenv('KAFKA_PORT', 9092)))
    return {
        'healthy': healthy,
        'details': 'Broker reachable' if healthy else 'TCP connection failed'
    }

def check_postgres_health():
    """Attempt to open a short DB connection."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.close()
        return {'healthy': True, 'details': 'Ready'}
    except Exception as exc:
        return {'healthy': False, 'details': str(exc)}

def check_mqtt_health():
    """Basic MQTT broker reachability check (TCP)."""
    healthy = _tcp_ping(os.getenv('MQTT_HOST', 'mosquitto'), int(os.getenv('MQTT_PORT', 1883)))
    return {
        'healthy': healthy,
        'details': 'Broker reachable' if healthy else 'TCP connection failed'
    }

def check_grafana_health():
    """HTTP GET /api/health on Grafana service."""
    url = os.getenv('GRAFANA_URL', 'http://grafana:3000/api/health')
    try:
        r = requests.get(url, timeout=3)
        return {'healthy': r.status_code == 200, 'details': f'Status {r.status_code}'}
    except Exception as exc:
        return {'healthy': False, 'details': str(exc)}

def check_spark_health():
    """HTTP HEAD on Spark master UI."""
    url = os.getenv('SPARK_MASTER_URL', 'http://spark-master:8080')
    try:
        r = requests.head(url, timeout=3)
        return {'healthy': r.status_code == 200, 'details': f'Status {r.status_code}'}
    except Exception as exc:
        return {'healthy': False, 'details': str(exc)}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 