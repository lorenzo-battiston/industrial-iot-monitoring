import os
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import List

load_dotenv()

@dataclass
class MQTTConfig:
    """MQTT Broker configuration"""
    broker_host: str = os.getenv('MQTT_BROKER_HOST', 'localhost')
    broker_port: int = int(os.getenv('MQTT_BROKER_PORT', '1883'))
    topic_prefix: str = os.getenv('MQTT_TOPIC_PREFIX', 'factory/machines')
    client_id: str = os.getenv('MQTT_CLIENT_ID', 'iot-simulator')
    keepalive: int = 60

@dataclass
class SimulationConfig:
    """Simulation parameters"""
    interval_seconds: int = int(os.getenv('SIMULATION_INTERVAL_SECONDS', '5'))
    machine_count: int = int(os.getenv('MACHINE_COUNT', '5'))
    machine_id_prefix: str = os.getenv('MACHINE_ID_PREFIX', 'MACHINE')
    
    # Machine operational parameters
    temperature_min: float = 20.0
    temperature_max: float = 80.0
    temperature_critical: float = 75.0
    
    speed_min: int = 800
    speed_max: int = 1200
    speed_optimal: int = 1000
    
    # State probabilities
    running_probability: float = 0.8
    idle_probability: float = 0.15
    maintenance_probability: float = 0.05
    
    # Alarm probability (higher when temperature is critical)
    alarm_base_probability: float = 0.1
    alarm_critical_probability: float = 0.6

@dataclass
class MachineState:
    """Represents the current state of a machine"""
    machine_id: str
    temperature: float
    speed: int
    state: str  # RUNNING, IDLE, MAINTENANCE, ERROR
    alarm: bool
    oee: float
    last_maintenance: str
    operator_name: str
    shift: str
    production_count: int
    good_units: int = 0
    scrap_units: int = 0
    scrap_rate: float = 0.0
    quality_score: float = 1.0
    error_count: int = 0
    downtime_incidents: int = 0
    last_error_time: str = ""
