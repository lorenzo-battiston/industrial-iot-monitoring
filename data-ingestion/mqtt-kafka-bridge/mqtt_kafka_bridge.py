#!/usr/bin/env python3
"""
MQTT-Kafka Bridge - Real-Time Big Data Processing Project
Custom Producer: Transfers MQTT messages to Kafka topics following course specifications
"""

import json
import logging
import signal
import sys
import time
from datetime import datetime
from typing import Dict, Optional

import paho.mqtt.client as mqtt
from kafka import KafkaProducer, KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError, KafkaError

from config import MQTTConfig, KafkaConfig, BridgeConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MQTTKafkaBridge:
    """
    Custom Producer that bridges MQTT messages to Kafka
    Follows course specifications:
    - JSON format (not Avro)
    - Explicit topic creation via Kafka Admin API
    - Producer API usage
    - Proper poll() calls for Python
    """
    
    def __init__(self, mqtt_config: MQTTConfig, kafka_config: KafkaConfig, bridge_config: BridgeConfig):
        self.mqtt_config = mqtt_config
        self.kafka_config = kafka_config
        self.bridge_config = bridge_config
        
        # Clients
        self.mqtt_client: Optional[mqtt.Client] = None
        self.kafka_producer: Optional[KafkaProducer] = None
        self.kafka_admin: Optional[KafkaAdminClient] = None
        
        # Statistics
        self.stats = {
            'messages_received': 0,
            'messages_sent': 0,
            'messages_failed': 0,
            'last_message_time': None,
            'start_time': datetime.now()
        }
        
        # Graceful shutdown
        self.running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle graceful shutdown"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def _setup_kafka_admin(self) -> bool:
        """Setup Kafka Admin client for topic management"""
        try:
            self.kafka_admin = KafkaAdminClient(
                bootstrap_servers=self.kafka_config.bootstrap_servers.split(',')
            )
            logger.info("Kafka Admin client initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Kafka Admin client: {e}")
            return False
    
    def _create_kafka_topic(self) -> bool:
        """
        Create Kafka topic using Admin API (as required by course specifications)
        """
        try:
            # Define topic with retention settings
            topic = NewTopic(
                name=self.kafka_config.topic_telemetry,
                num_partitions=3,  # Multiple partitions for scalability
                replication_factor=1,  # Single broker setup
                topic_configs={
                    'retention.ms': str(self.kafka_config.topic_retention_ms),
                    'cleanup.policy': 'delete',
                    'compression.type': 'gzip'
                }
            )
            
            # Create topic
            future = self.kafka_admin.create_topics([topic])
            
            # Wait for creation to complete
            for topic_name, future_result in future.items():
                try:
                    future_result.result()  # Block until topic is created
                    logger.info(f"Topic '{topic_name}' created successfully")
                except TopicAlreadyExistsError:
                    logger.info(f"Topic '{topic_name}' already exists")
                except Exception as e:
                    logger.error(f"Failed to create topic '{topic_name}': {e}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in topic creation: {e}")
            return False
    
    def _setup_kafka_producer(self) -> bool:
        """Setup Kafka Producer with course-recommended settings"""
        try:
            self.kafka_producer = KafkaProducer(**self.kafka_config.producer_config)
            logger.info(f"Kafka Producer initialized - servers: {self.kafka_config.bootstrap_servers}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Kafka Producer: {e}")
            return False
    
    def _setup_mqtt_client(self) -> bool:
        """Setup MQTT client with callbacks"""
        try:
            self.mqtt_client = mqtt.Client(self.mqtt_config.client_id)
            
            # MQTT Callbacks
            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    logger.info(f"Connected to MQTT broker at {self.mqtt_config.broker_host}:{self.mqtt_config.broker_port}")
                    # Subscribe to telemetry topics
                    for topic in self.mqtt_config.subscribe_topics:
                        client.subscribe(topic)
                        logger.info(f"Subscribed to MQTT topic: {topic}")
                else:
                    logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
            
            def on_disconnect(client, userdata, rc):
                logger.warning(f"Disconnected from MQTT broker. Return code: {rc}")
            
            def on_message(client, userdata, msg):
                """Handle incoming MQTT messages"""
                self._handle_mqtt_message(msg)
            
            def on_subscribe(client, userdata, mid, granted_qos):
                logger.info(f"Successfully subscribed - Message ID: {mid}, QoS: {granted_qos}")
            
            # Assign callbacks
            self.mqtt_client.on_connect = on_connect
            self.mqtt_client.on_disconnect = on_disconnect
            self.mqtt_client.on_message = on_message
            self.mqtt_client.on_subscribe = on_subscribe
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup MQTT client: {e}")
            return False
    
    def _handle_mqtt_message(self, mqtt_msg):
        """
        Process MQTT message and send to Kafka
        Implements the custom producer logic
        """
        try:
            # Update statistics
            self.stats['messages_received'] += 1
            self.stats['last_message_time'] = datetime.now()
            
            # Decode MQTT message
            topic_parts = mqtt_msg.topic.split('/')
            machine_id = topic_parts[-2] if len(topic_parts) >= 2 else 'unknown'
            
            # Parse JSON payload
            try:
                payload = json.loads(mqtt_msg.payload.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in MQTT message from {mqtt_msg.topic}: {e}")
                self.stats['messages_failed'] += 1
                return
            
            # Validate required fields
            required_fields = ['timestamp', 'machine_id', 'temperature', 'speed', 'state']
            missing_fields = [field for field in required_fields if field not in payload]
            if missing_fields:
                logger.error(f"Missing required fields {missing_fields} in message from {machine_id}")
                self.stats['messages_failed'] += 1
                return
            
            # Enrich message with metadata
            enriched_payload = {
                **payload,
                'mqtt_topic': mqtt_msg.topic,
                'bridge_timestamp': datetime.now().isoformat(),
                'bridge_id': 'mqtt-kafka-bridge-01'
            }
            
            if self.bridge_config.dry_run:
                # Dry run mode - print to stdout
                print(f"\n--- DRY RUN: {machine_id} ---")
                print(f"MQTT Topic: {mqtt_msg.topic}")
                print(f"Kafka Topic: {self.kafka_config.topic_telemetry}")
                print(f"Payload: {json.dumps(enriched_payload, indent=2)}")
                self.stats['messages_sent'] += 1
            else:
                # Send to Kafka
                self._send_to_kafka(machine_id, enriched_payload)
            
        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}")
            self.stats['messages_failed'] += 1
    
    def _send_to_kafka(self, machine_id: str, payload: Dict):
        """
        Send message to Kafka using Producer API
        Following course specifications with proper poll() calls
        """
        try:
            # Prepare Kafka message
            kafka_message = json.dumps(payload)
            
            # Send to Kafka with machine_id as key for partitioning
            future = self.kafka_producer.send(
                topic=self.kafka_config.topic_telemetry,
                key=machine_id,
                value=kafka_message
            )
            
            # Important: call poll() after produce() for Python (course requirement)
            self.kafka_producer.poll(timeout=0)
            
            # Add callback for delivery confirmation
            def on_delivery(record_metadata=None, exception=None):
                if exception:
                    logger.error(f"Failed to deliver message to Kafka: {exception}")
                    self.stats['messages_failed'] += 1
                else:
                    logger.debug(f"Message delivered to {record_metadata.topic}[{record_metadata.partition}] at offset {record_metadata.offset}")
                    self.stats['messages_sent'] += 1
            
            future.add_callback(on_delivery)
            
        except KafkaError as e:
            logger.error(f"Kafka error: {e}")
            self.stats['messages_failed'] += 1
        except Exception as e:
            logger.error(f"Unexpected error sending to Kafka: {e}")
            self.stats['messages_failed'] += 1
    
    def _print_statistics(self):
        """Print operational statistics"""
        uptime = datetime.now() - self.stats['start_time']
        
        logger.info("=== BRIDGE STATISTICS ===")
        logger.info(f"Uptime: {uptime}")
        logger.info(f"Messages received (MQTT): {self.stats['messages_received']}")
        logger.info(f"Messages sent (Kafka): {self.stats['messages_sent']}")
        logger.info(f"Messages failed: {self.stats['messages_failed']}")
        logger.info(f"Success rate: {(self.stats['messages_sent'] / max(1, self.stats['messages_received'])) * 100:.1f}%")
        logger.info(f"Last message: {self.stats['last_message_time']}")
        logger.info("========================")
    
    def connect(self) -> bool:
        """Connect to both MQTT and Kafka"""
        logger.info("Initializing MQTT-Kafka Bridge...")
        
        # Setup Kafka Admin and create topic
        if not self._setup_kafka_admin():
            return False
        
        if not self._create_kafka_topic():
            return False
        
        # Setup Kafka Producer
        if not self._setup_kafka_producer():
            return False
        
        # Setup MQTT
        if not self._setup_mqtt_client():
            return False
        
        # Connect to MQTT broker
        try:
            self.mqtt_client.connect(
                self.mqtt_config.broker_host,
                self.mqtt_config.broker_port,
                self.mqtt_config.keepalive
            )
            
            # Start MQTT loop
            self.mqtt_client.loop_start()
            
            logger.info("Bridge initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from both services"""
        logger.info("Disconnecting bridge...")
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        if self.kafka_producer:
            # Flush remaining messages
            self.kafka_producer.flush(timeout=10)
            self.kafka_producer.close()
        
        if self.kafka_admin:
            self.kafka_admin.close()
        
        logger.info("Bridge disconnected")
    
    def run(self):
        """Run the bridge service"""
        logger.info("Starting MQTT-Kafka Bridge")
        logger.info(f"Dry run mode: {self.bridge_config.dry_run}")
        
        if not self.connect():
            logger.error("Failed to initialize bridge connections")
            return False
        
        try:
            # Main loop
            stats_counter = 0
            while self.running:
                time.sleep(1)
                
                # Print statistics every 30 seconds
                stats_counter += 1
                if stats_counter % 30 == 0:
                    self._print_statistics()
                    stats_counter = 0
                
                # Flush Kafka producer periodically
                if self.kafka_producer and not self.bridge_config.dry_run:
                    self.kafka_producer.poll(timeout=0)
        
        except KeyboardInterrupt:
            logger.info("Bridge stopped by user")
        except Exception as e:
            logger.error(f"Bridge error: {e}")
        finally:
            self.disconnect()
            self._print_statistics()
        
        return True

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MQTT-Kafka Bridge")
    parser.add_argument('--dry-run', action='store_true',
                       help='Print messages to stdout instead of sending to Kafka')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Set logging level')
    
    args = parser.parse_args()
    
    # Setup logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Load configurations
    mqtt_config = MQTTConfig()
    kafka_config = KafkaConfig()
    bridge_config = BridgeConfig()
    
    # Override with command line arguments
    if args.dry_run:
        bridge_config.dry_run = True
    
    # Create and run bridge
    bridge = MQTTKafkaBridge(mqtt_config, kafka_config, bridge_config)
    success = bridge.run()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()