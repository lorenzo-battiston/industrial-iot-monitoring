# Industrial IoT Monitoring System

Real-Time Big Data Processing Project - University of Bozen-Bolzano  
**Author**: Lorenzo Battiston  
**Course**: Real-Time Big Data Processing

## 📋 Project Overview

Enterprise-grade industrial IoT monitoring system that processes real-time telemetry data from manufacturing machines using modern big data technologies. The system simulates a factory environment with multiple machines, streams telemetry data through Apache Kafka, and provides real-time analytics and visualization.

## 🏗️ System Architecture

```
┌─────────────────┐    ┌──────────┐    ┌─────────────┐    ┌─────────────┐
│ Machine         │───▶│   MQTT   │───▶│ Custom      │───▶│   Apache    │
│ Simulator       │    │  Broker  │    │ Bridge      │    │   Kafka     │
│ (IoT Devices)   │    │(Eclipse) │    │ (Producer)  │    │ (Streaming) │
└─────────────────┘    └──────────┘    └─────────────┘    └─────────────┘
         │                                                        │
         ▼                                                        ▼
┌─────────────────┐    ┌──────────┐    ┌─────────────┐    ┌─────────────┐
│ Temperature:    │    │ Topics:  │    │ Stream      │    │ PostgreSQL  │
│ 20-80°C         │    │telemetry │    │ Processing  │    │ Database    │
│ Speed: 800-1200 │    │ (3 part.)│    │(Apache Spark│    │ (Analytics) │
│ States: RUN/IDLE│    │          │    │             │    │             │
└─────────────────┘    └──────────┘    └─────────────┘    └─────────────┘
                                                                  │
                                                                  ▼
                                                          ┌─────────────┐
                                                          │   Grafana   │
                                                          │ Dashboard   │
                                                          │(Visualization│
                                                          └─────────────┘
```

### Core Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Machine Simulator** | Python 3.10 | Simulates industrial IoT devices with realistic telemetry |
| **MQTT Broker** | Eclipse Mosquitto | IoT-standard messaging protocol |
| **Custom Bridge** | Python + kafka-python-ng | MQTT to Kafka message transfer |
| **Message Broker** | Apache Kafka | Distributed event streaming platform |
| **Stream Processor** | Apache Spark | Real-time data processing and analytics |
| **Database** | PostgreSQL | Persistent storage for processed data |
| **Visualization** | Grafana | Real-time dashboards and monitoring |

## 🚀 Quick Start

### Prerequisites
- **Docker** & **Docker Compose** (latest version)
- **Python 3.10+** with pip
- **Git** for cloning the repository

### 1. Clone and Setup
```bash
git clone https://github.com/yourusername/industrial-iot-monitoring
cd industrial-iot-monitoring
```

### 2. Start Infrastructure Services
```bash
# Start all Docker containers
docker compose up -d

# Verify services are running
docker compose ps

# Check logs if needed
docker compose logs
```

### 3. Setup Python Environment and Run Data Ingestion

**Terminal 1: MQTT-Kafka Bridge**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

cd data-ingestion/mqtt-kafka-bridge
pip install -r requirements.txt
python mqtt_kafka_bridge.py
```

**Terminal 2: Machine Simulator**
```bash
# In new terminal, same venv
source venv/bin/activate

cd data-ingestion/machine-simulator
pip install -r requirements.txt
python machine_simulator.py --machines 5 --interval 3
```

### 4. Monitor Data Flow

**Terminal 3: MQTT Messages**
```bash
docker exec mqtt-broker mosquitto_sub -h localhost -p 1883 -t "factory/machines/+/telemetry"
```

**Terminal 4: Kafka Messages**
```bash
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic telemetry --from-beginning
```

**Terminal 5: Spark**
```bash
docker-compose logs -f iot-processor | grep -A 20 -B 5 "Batch:"
```

## 📊 Data Flow & Message Format

### Message Journey
1. **Machine Simulator** → Generates telemetry every 3-5 seconds
2. **MQTT Broker** → Receives via `factory/machines/{MACHINE_ID}/telemetry`
3. **Bridge** → Consumes MQTT and produces to Kafka `telemetry` topic
4. **Kafka** → Distributes across 3 partitions for scalability
5. **Spark** → Processes streams for real-time analytics *(planned)*
6. **PostgreSQL** → Stores aggregated KPIs *(planned)*
7. **Grafana** → Visualizes dashboards *(planned)*

### Sample Telemetry Message
```json
{
  "timestamp": "2025-06-18T10:47:25.054588",
  "machine_id": "MACHINE_001",
  "temperature": 45.2,
  "speed": 1050,
  "state": "RUNNING",
  "alarm": false,
  "oee": 0.875,
  "last_maintenance": "2025-06-10T08:00:00",
  "operator_name": "Alice Johnson",
  "shift": "Morning",
  "production_count": 1247,
  "location": "Factory Floor A - Line 1",
  "firmware_version": "v2.1.3",
  "mqtt_topic": "factory/machines/MACHINE_001/telemetry",
  "bridge_timestamp": "2025-06-18T10:47:25.058071",
  "bridge_id": "mqtt-kafka-bridge-01"
}
```

## 🛠️ Development & Configuration

### Project Structure
```
.
├── .env
├── .env.example
├── .gitignore
├── config
│   ├── init.sql
│   └── mosquitto.conf
├── connectors
├── data-ingestion
│   ├── machine-simulator
│   │   ├── __pycache__
│   │   │   └── config.cpython-313.pyc
│   │   ├── config.py
│   │   ├── config.yaml
│   │   ├── machine_simulator.py
│   │   └── requirements.txt
│   ├── mqtt-kafka-bridge
│   │   ├── __pycache__
│   │   │   └── config.cpython-313.pyc
│   │   ├── config.py
│   │   ├── config.yaml
│   │   ├── mqtt_kafka_bridge.py
│   │   └── requirements.txt
│   └── README.md
├── database
│   └── init-scripts
├── docker-compose.yml
├── monitoring
│   └── grafana
│       ├── dashboards
│       └── provisioning
├── mosquitto
│   ├── config
│   │   └── mosquitto.conf
│   ├── data
│   └── log
├── processing
│   ├── DockerFile
│   ├── pom.xml
│   ├── src
│   │   └── main
│   │       ├── java
│   │       │   └── it
│   │       │       └── elena
│   │       │           └── inf
│   │       │               └── spark
│   │       │                   ├── IoTProcessor.java
│   │       │                   └── KafkaUtils.java
│   │       └── resources
│   │           └── log4j.properties
│   └── target
│       ├── classes
│       │   ├── it
│       │   │   └── elena
│       │   │       └── inf
│       │   │           └── spark
│       │   │               ├── IoTProcessor.class
│       │   │               ├── IoTProcessor$Configuration.class
│       │   │               └── KafkaUtils.class
│       │   └── log4j.properties
│       ├── generated-sources
│       │   └── annotations
│       ├── generated-test-sources
│       │   └── test-annotations
│       └── test-classes
└── README.md
```

### Environment Configuration
Key configuration via environment variables and YAML files:

**Machine Simulator (`config.py`)**
```python
machine_count: 5                    # Number of machines to simulate
interval_seconds: 3                 # Message frequency
temperature_min/max: 20.0/80.0     # Temperature range
speed_optimal: 1000                 # Target RPM
alarm_probability: 0.02             # Base alarm rate
```

**MQTT-Kafka Bridge (`config.py`)**
```python
mqtt_broker_host: localhost:1883    # MQTT connection
kafka_bootstrap_servers: localhost:29092  # Kafka connection
topic_telemetry: telemetry          # Kafka topic name
```

### Machine Simulation Logic

The simulator implements realistic industrial behavior:

**Temperature Simulation:**
- Correlation with machine state (running machines heat up)
- Gaussian noise for realistic variations
- Critical temperature thresholds for alarms

**State Transitions (Markov Chain):**
```
RUNNING ──5%──→ IDLE ──30%──→ RUNNING
   │                            ▲
   2%                          10%
   ▼                            │
MAINTENANCE ─────────────────────┘
```

**OEE Calculation:**
- Overall Equipment Effectiveness
- Decreases during alarms and maintenance
- Realistic industrial KPI tracking

## 📈 Key Performance Indicators (KPIs)

The system tracks industrial-standard metrics:

| Metric | Description | Range |
|--------|-------------|-------|
| **OEE** | Overall Equipment Effectiveness | 0.0 - 1.0 |
| **Temperature** | Machine operating temperature | 20°C - 80°C |
| **Speed** | Machine RPM | 800 - 1200 |
| **Availability** | Uptime percentage | Calculated |
| **Alarm Rate** | Fault frequency | Events/hour |
| **Production Count** | Parts produced | Cumulative |

## 🔧 System Operations

### Monitoring Commands

**Service Health:**
```bash
# Check all services
docker compose ps

# View logs
docker compose logs [service_name]

# Resource usage
docker stats
```

**MQTT Operations:**
```bash
# Subscribe to all telemetry
docker exec mqtt-broker mosquitto_sub -h localhost -p 1883 -t "factory/machines/+/telemetry"

# Publish test message
docker exec mqtt-broker mosquitto_pub -h localhost -p 1883 -t "factory/machines/TEST/telemetry" -m '{"test": "message"}'
```

**Kafka Operations:**
```bash
# List topics
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Describe topic
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic telemetry

# Consumer from beginning
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic telemetry --from-beginning
```

### Troubleshooting

**Common Issues:**

1. **Port Conflicts:** Ensure ports 1883, 9092, 29092, 8080, 5433 are available
2. **Docker Memory:** Kafka requires sufficient Docker memory (recommend 4GB+)
3. **Python Dependencies:** Use virtual environment for clean package management

**Debug Mode:**
```bash
# Run components in dry-run mode
python machine_simulator.py --dry-run --machines 2 --interval 2
python mqtt_kafka_bridge.py --dry-run --log-level DEBUG
```

## 📝 Academic Requirements Compliance

This project fulfills the **Real-Time Big Data Processing** course requirements:

### ✅ Core Requirements
- **Message Broker**: Apache Kafka with custom topic configuration
- **Custom Producer**: Python-based MQTT-Kafka bridge (not Kafka Connect)
- **JSON Format**: Human-readable message format (not Avro)
- **Real-time Processing**: Sub-second message latency
- **Stream Processing**: Apache Spark integration (architecture ready)
- **Web Frontend**: Grafana dashboards (architecture ready)

### ✅ Technical Implementation
- **Kafka Admin API**: Programmatic topic creation and management
- **Producer API**: Direct Kafka message publishing with delivery callbacks
- **Partitioning**: Machine ID-based partitioning for scalability
- **Error Handling**: Comprehensive error handling and statistics
- **Docker Deployment**: Production-ready containerized architecture

### 🎯 Learning Outcomes Demonstrated
1. **Event-Driven Architecture**: Asynchronous message flow
2. **Stream Processing**: Real-time data pipelines
3. **Microservices**: Decoupled, containerized components
4. **Industrial IoT**: Realistic manufacturing telemetry simulation
5. **Big Data Technologies**: Kafka, Spark ecosystem integration

## 🚀 Future Enhancements

### Phase 2: Stream Processing
- [ ] Apache Spark Structured Streaming
- [ ] Real-time KPI aggregation
- [ ] Anomaly detection algorithms
- [ ] Window-based analytics

### Phase 3: Visualization
- [ ] Grafana dashboard development
- [ ] Real-time alerting system
- [ ] Historical data analysis
- [ ] Machine learning insights

### Phase 4: Production Features
- [ ] Authentication and authorization
- [ ] SSL/TLS encryption
- [ ] High availability setup
- [ ] Performance optimization

## 📚 References and Technologies

### Core Technologies
- [Apache Kafka](https://kafka.apache.org/) - Distributed event streaming
- [Eclipse Mosquitto](https://mosquitto.org/) - MQTT broker
- [Apache Spark](https://spark.apache.org/) - Unified analytics engine
- [PostgreSQL](https://www.postgresql.org/) - Advanced open source database
- [Grafana](https://grafana.com/) - Observability platform

### Python Libraries
- `kafka-python-ng` - Kafka client for Python
- `paho-mqtt` - MQTT client library
- `dataclasses-json` - JSON serialization
- `python-dotenv` - Environment variable management

---

version: '3.8'

services:
  # Zookeeper (richiesto per Kafka)
  zookeeper:
    image: confluentinc/cp-zookeeper:6.0.0
    container_name: zookeeper
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    networks:
      - iot-network

  # Apache Kafka (configurazione testata e funzionante)
  kafka:
    image: confluentinc/cp-kafka:6.0.0
    container_name: kafka
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
      - "29092:29092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:29092
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 100
    command:
      - bash
      - -c 
      - |
        echo '127.0.0.1 kafka' >> /etc/hosts
        /etc/confluent/docker/run
    networks:
      - iot-network

  # Kafka UI for monitoring
  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    container_name: kafka-ui
    depends_on:
      - kafka
    ports:
      - "8080:8080"
    environment:
      KAFKA_CLUSTERS_0_NAME: local
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
    networks:
      - iot-network

  # MQTT Broker
  mosquitto:
    image: eclipse-mosquitto:2.0
    container_name: mqtt-broker
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto/config/mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mosquitto_data:/mosquitto/data
      - mosquitto_logs:/mosquitto/log
    command: mosquitto -c /mosquitto/config/mosquitto.conf
    networks:
      - iot-network

  # PostgreSQL Database
  postgres:
    image: postgres:15
    container_name: postgres
    ports:
      - "5433:5432"
    environment:
      POSTGRES_DB: iot_analytics
      POSTGRES_USER: iot_user
      POSTGRES_PASSWORD: iot_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./config/init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - iot-network

  # Apache Spark Master
  spark-master:
    image: bitnami/spark:3.5.1
    container_name: iot-spark-master
    ports:
      - '7080:8080'  # Spark Master Web UI (changed port to avoid conflict with Kafka UI)
      - '7077:7077'  # Spark Master Port
    profiles:
      - spark-processing
    environment:
      SPARK_MODE: 'master'
      SPARK_MASTER_HOST: 'spark-master'
      SPARK_RPC_AUTHENTICATION_ENABLED: 'no'
      SPARK_RPC_ENCRYPTION_ENABLED: 'no'
      SPARK_LOCAL_STORAGE_ENCRYPTION_ENABLED: 'no'
      SPARK_SSL_ENABLED: 'no'
    networks:
      - iot-network

  # Apache Spark Worker
  spark-worker:
    image: bitnami/spark:3.5.1
    container_name: iot-spark-worker
    depends_on:
      - spark-master
    ports:
      - '8081:8081'  # Spark Worker Web UI
    profiles:
      - spark-processing
    environment:
      SPARK_MODE: 'worker'
      SPARK_MASTER_URL: 'spark://spark-master:7077'
      SPARK_WORKER_MEMORY: '2g'
      SPARK_WORKER_CORES: '2'
      SPARK_RPC_AUTHENTICATION_ENABLED: 'no'
      SPARK_RPC_ENCRYPTION_ENABLED: 'no'
      SPARK_LOCAL_STORAGE_ENCRYPTION_ENABLED: 'no'
      SPARK_SSL_ENABLED: 'no'
    networks:
      - iot-network

  # IoT Data Processor (Spark Application)
  iot-processor:
    build: 
      context: ./processing          # Cambiato da ./processing/spark-processor
      dockerfile: DockerFile         # Cambiato da Dockerfile (nota la maiuscola)
    container_name: iot-spark-processor
    depends_on:
      - spark-master
      - kafka
      - postgres
    ports:
      - '4040:4040'
    profiles:
      - spark-processing
    environment:
      PROCESSOR_MASTER: 'spark://spark-master:7077'
      PROCESSOR_IMPLEMENTATION: 'it.elena.inf.spark.IoTProcessor'  # Usa il package esistente
      PROCESSOR_ARGS: '--bootstrap-servers kafka:9092 --postgres-host postgres --postgres-db iot_analytics --postgres-user iot_user --postgres-password iot_password --dry-run'
    volumes:
      - spark-checkpoints:/tmp/spark-checkpoint-iot
    networks:
      - iot-network
    restart: unless-stopped

# Networks
networks:
  iot-network:
    driver: bridge

# Volumes
volumes:
  kafka_data:
  mosquitto_data:
  mosquitto_logs:
  postgres_data:
  spark-checkpoints:
    driver: local