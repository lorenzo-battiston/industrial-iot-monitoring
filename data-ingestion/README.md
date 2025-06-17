# Data Ingestion Components

This directory contains the data ingestion layer of the IoT Real-Time Monitoring System, implementing a **Custom Producer** approach as recommended by the course specifications.

## 🏗️ Architecture

```
Machine Simulator → MQTT Broker → MQTT-Kafka Bridge → Kafka
```

## 📁 Components

### 1. Machine Simulator (`machine-simulator/`)

Simulates industrial IoT devices generating realistic telemetry data:

- **Temperature**: 20-80°C with realistic variations
- **Speed**: 800-1200 RPM with operational states
- **States**: RUNNING, IDLE, MAINTENANCE
- **Alarms**: Temperature-based and random events
- **OEE**: Overall Equipment Effectiveness calculation
- **Metadata**: Operator names, shifts, production counts

**Key Features:**
- Realistic state transitions using Markov chains
- Temperature correlation with machine states
- Production count tracking
- MQTT publishing with QoS support

### 2. MQTT-Kafka Bridge (`mqtt-kafka-bridge/`)

Custom Producer implementation following course specifications:

- **JSON Format**: Avoids Confluent Schema Registry complexity
- **Admin API**: Explicit topic creation and configuration
- **Producer API**: Direct Kafka message publishing
- **Python Compatibility**: Proper `poll()` calls after `produce()`

**Key Features:**
- Message validation and enrichment
- Delivery confirmation callbacks
- Error handling and statistics
- Dry-run mode for testing
- Graceful shutdown handling

## 🚀 Quick Start

### Prerequisites

```bash
# Start infrastructure
docker compose up -d

# Verify services
docker compose ps
```

### 1. Install Dependencies

```bash
# Machine Simulator
cd machine-simulator
pip install -r requirements.txt

# MQTT-Kafka Bridge
cd ../mqtt-kafka-bridge
pip install -r requirements.txt
```

### 2. Test with Dry Run

```bash
# Test machine simulator (prints to stdout)
python machine_simulator.py --dry-run --machines 3 --interval 2

# Test bridge (prints to stdout)
python mqtt_kafka_bridge.py --dry-run
```

### 3. Run Full Pipeline

```bash
# Terminal 1: Start machine simulator
cd machine-simulator
python machine_simulator.py

# Terminal 2: Start bridge
cd ../mqtt-kafka-bridge
python mqtt_kafka_bridge.py
```

## 📊 Message Format

### MQTT Topic Structure
```
factory/machines/{MACHINE_ID}/telemetry
```

### JSON Message Schema
```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "machine_id": "MACHINE_001",
  "temperature": 45.67,
  "speed": 1050,
  "state": "RUNNING",
  "alarm": false,
  "oee": 0.875,
  "last_maintenance": "2024-01-10T08:00:00",
  "operator_name": "Alice Johnson",
  "shift": "Morning",
  "production_count": 1247,
  "location": "Factory Floor A - Line 1",
  "firmware_version": "v2.1.3",
  "mqtt_topic": "factory/machines/MACHINE_001/telemetry",
  "bridge_timestamp": "2024-01-15T10:30:45.567890",
  "bridge_id": "mqtt-kafka-bridge-01"
}
```

## 🔧 Configuration

### Environment Variables (.env)

```bash
# MQTT Configuration
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_TOPIC_PREFIX=factory/machines

# Kafka Configuration  
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_TELEMETRY=telemetry
KAFKA_TOPIC_RETENTION_MS=86400000

# Simulation Parameters
SIMULATION_INTERVAL_SECONDS=5
MACHINE_COUNT=5
MACHINE_ID_PREFIX=MACHINE
```

### Command Line Options

**Machine Simulator:**
```bash
python machine_simulator.py [options]
  --dry-run          Print to stdout instead of MQTT
  --machines N       Number of machines to simulate
  --interval N       Seconds between messages
```

**MQTT-Kafka Bridge:**
```bash
python mqtt_kafka_bridge.py [options]
  --dry-run          Print to stdout instead of Kafka
  --log-level LEVEL  Set logging level (DEBUG, INFO, WARNING, ERROR)
```

## 📈 Monitoring

### MQTT Monitoring
- **Broker**: http://localhost:8080 (Kafka UI also shows consumer groups)
- **Topics**: `factory/machines/+/telemetry`

### Kafka Monitoring
- **Kafka UI**: http://localhost:8080
- **Topic**: `telemetry`
- **Partitions**: 3 (for load distribution)
- **Retention**: 24 hours

### Bridge Statistics
The bridge logs operational statistics every 30 seconds:
- Messages received from MQTT
- Messages sent to Kafka  
- Success rate and error counts
- Uptime and last message timestamp

## 🐛 Troubleshooting

### Common Issues

1. **MQTT Connection Failed**
   ```bash
   # Check MQTT broker
   docker compose logs mosquitto
   
   # Test MQTT connectivity
   mosquitto_pub -h localhost -t test -m "hello"
   ```

2. **Kafka Connection Failed**
   ```bash
   # Check Kafka broker
   docker compose logs kafka
   
   # List topics
   docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list
   ```

3. **Topic Creation Failed**
   ```bash
   # Manually create topic
   docker exec kafka kafka-topics --bootstrap-server localhost:9092 \
     --create --topic telemetry --partitions 3 --replication-factor 1
   ```

4. **Python Dependencies**
   ```bash
   # Reinstall requirements
   pip install --upgrade -r requirements.txt
   ```

### Debug Mode

Enable detailed logging:
```bash
python mqtt_kafka_bridge.py --log-level DEBUG
```

## ✅ Validation

### Check Data Flow

1. **MQTT Messages**: Use MQTT client to verify publishing
   ```bash
   mosquitto_sub -h localhost -t "factory/machines/+/telemetry"
   ```

2. **Kafka Messages**: Use Kafka console consumer
   ```bash
   docker exec kafka kafka-console-consumer \
     --bootstrap-server localhost:9092 \
     --topic telemetry \
     --from-beginning
   ```

3. **Message Count**: Compare MQTT vs Kafka message counts

## 🎯 Course Specifications Compliance

- ✅ **Custom Producer**: Implemented instead of Kafka Connect
- ✅ **JSON Format**: Avoids Avro and Schema Registry complexity  
- ✅ **Admin API**: Explicit topic creation and configuration
- ✅ **Producer API**: Direct Kafka publishing with proper error handling
- ✅ **Python poll()**: Correct usage after produce() calls
- ✅ **Dry Run**: Testing capability as recommended
- ✅ **Client Libraries**: Reuse of MQTT and Kafka client libraries

This implementation follows all course recommendations and provides a solid foundation for the stream processing components.