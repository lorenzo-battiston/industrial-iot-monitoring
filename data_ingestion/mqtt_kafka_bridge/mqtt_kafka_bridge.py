import os
import sys
import time
import json
import logging
import threading
import signal
from queue import Queue, Empty

import paho.mqtt.client as mqtt
from confluent_kafka import Producer

from .config import Config

# --- START OF LOGGING SETUP ---
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)
# --- END OF LOGGING SETUP ---

def delivery_report(err, msg):
    """ Called once for each message produced to indicate delivery result. """
    if err is not None:
        logging.error(f'Message delivery failed: {err}')
    else:
        logging.debug(f'Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}')

class MQTTKafkaBridge:
    """A bridge to forward messages from an MQTT topic to a Kafka topic."""

    def __init__(self, config):
        self.config = config
        self.shutdown_flag = threading.Event()
        
        logging.info("Initializing Kafka Producer...")
        self.kafka_producer = self._init_kafka_producer()
        
        logging.info("Initializing MQTT Client...")
        self.mqtt_client = self._init_mqtt_client()
        
        self.message_queue = Queue()

    def _init_kafka_producer(self):
        """Initializes and returns a Kafka producer instance."""
        kafka_conf = self.config['kafka']
        logging.info(f"Attempting to connect to Kafka at {kafka_conf['bootstrap_servers']}...")
        try:
            producer = Producer({
                'bootstrap.servers': kafka_conf['bootstrap_servers'],
                'client.id': kafka_conf.get('client_id', 'mqtt-kafka-bridge-producer'),
                'retries': 5,
                'message.timeout.ms': 30000
            })
            logging.info("Successfully connected to Kafka.")
            return producer
        except Exception as e:
            logging.error(f"FATAL: Could not connect to Kafka. Error: {e}", exc_info=True)
            sys.exit(1)  # Exit if we can't connect to Kafka

    def _init_mqtt_client(self):
        """Initializes and returns an MQTT client instance."""
        mqtt_conf = self.config['mqtt']
        client_id = mqtt_conf.get('client_id', 'mqtt-kafka-bridge')
        client = mqtt.Client(client_id=client_id, clean_session=True)
        client.on_connect = self._on_mqtt_connect
        client.on_message = self._on_mqtt_message
        return client

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """The callback for when the client receives a CONNACK response from the server."""
        if rc == 0:
            logging.info("Successfully connected to MQTT Broker.")
            mqtt_topic = self.config['mqtt']['topic']
            logging.info(f"Subscribing to MQTT topic: {mqtt_topic}")
            client.subscribe(mqtt_topic)
        else:
            logging.error(f"Failed to connect to MQTT Broker, return code {rc}\n")
            self.shutdown_flag.set()

    def _on_mqtt_message(self, client, userdata, msg):
        """The callback for when a PUBLISH message is received from the server."""
        try:
            logging.info(f"Received message from MQTT topic {msg.topic}")
            self.message_queue.put(msg.payload)
        except Exception as e:
            logging.error(f"Error processing MQTT message: {e}")

    def _kafka_producer_thread(self):
        """Thread function to produce messages from the queue to Kafka."""
        kafka_topic = self.config['kafka']['topic']
        while not self.shutdown_flag.is_set():
            try:
                payload = self.message_queue.get(timeout=1)
                logging.info(f"Sending message to Kafka topic: {kafka_topic}")
                self.kafka_producer.produce(kafka_topic, payload, callback=delivery_report)
                self.kafka_producer.poll(0)
            except Empty:
                continue
            except Exception as e:
                logging.error(f"Error producing message to Kafka: {e}")
        
        logging.info("Flushing final messages to Kafka...")
        self.kafka_producer.flush()

    def run(self):
        """Starts the bridge."""
        # Start Kafka producer thread
        producer_thread = threading.Thread(target=self._kafka_producer_thread)
        producer_thread.daemon = True
        producer_thread.start()

        # Connect to MQTT Broker
        mqtt_conf = self.config['mqtt']
        try:
            logging.info(f"Connecting to MQTT broker at {mqtt_conf['broker']}:{mqtt_conf['port']}...")
            self.mqtt_client.connect(mqtt_conf['broker'], mqtt_conf['port'], 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            logging.error(f"Could not connect to MQTT Broker: {e}")
            self.shutdown_flag.set()
            return

        logging.info("Bridge is running. Press Ctrl+C to exit.")
        try:
            while not self.shutdown_flag.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Shutdown signal received.")
        
        self.shutdown()
        producer_thread.join()

    def shutdown(self):
        """Shuts down the bridge gracefully."""
        logging.info("Shutting down the bridge...")
        self.shutdown_flag.set()
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        logging.info("MQTT client disconnected.")

def main():
    """Main function to start the bridge."""
    logging.info("--- Starting MQTT to Kafka Bridge ---")
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    config = Config(config_path)
    
    bridge = MQTTKafkaBridge(config)
    
    def signal_handler(sig, frame):
        bridge.shutdown()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    bridge.run()
    logging.info("Bridge has shut down.")

if __name__ == '__main__':
    main() 