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
    client_id: str = 'mqtt-kafka-bridge'
    keepalive: int = 60
    
    @property
    def subscribe_topics(self) -> List[str]:
        """MQTT topics to subscribe to"""
        return [f"{self.topic_prefix}/+/telemetry"]

@dataclass  
class KafkaConfig:
    """Kafka configuration"""
    bootstrap_servers: str = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:29092')
    topic_telemetry: str = os.getenv('KAFKA_TOPIC_TELEMETRY', 'telemetry')
    topic_retention_ms: int = int(os.getenv('KAFKA_TOPIC_RETENTION_MS', '86400000'))  # 24 hours
    
    # Producer settings (as suggested in course specs)
    producer_config: dict = None
    
    def __post_init__(self):
        """Setup producer configuration"""
        self.producer_config = {
            'bootstrap_servers': self.bootstrap_servers.split(','),
            'value_serializer': lambda v: v.encode('utf-8'),
            'key_serializer': lambda k: k.encode('utf-8') if k else None,
            'acks': 'all',  # Wait for all replicas
            'retries': 3,
            'retry_backoff_ms': 1000,
            'request_timeout_ms': 30000,
            # Removed 'enable_idempotence': True - not supported
        }

@dataclass
class BridgeConfig:
    """Bridge operation configuration"""
    log_level: str = os.getenv('LOG_LEVEL', 'INFO')
    dry_run: bool = os.getenv('DRY_RUN', 'false').lower() == 'true'
    
    # Message processing
    max_message_size: int = 1048576  # 1MB
    batch_size: int = 100
    flush_interval_seconds: int = 5
