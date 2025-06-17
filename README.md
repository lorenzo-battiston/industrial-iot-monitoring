# IoT Real-Time Monitoring System

Real-Time Big Data Processing project - University of Bozen-Bolzano

## 📋 Project Overview

Industrial IoT monitoring system that processes real-time telemetry data from manufacturing machines using Apache Kafka and Apache Spark for stream processing, with Grafana visualization.

## 🏗️ Architecture

```
Machine Simulator → MQTT → Bridge → Kafka → Spark → PostgreSQL → Grafana
```

### Components:
- **Machine Simulator**: Python application simulating industrial machine telemetry
- **MQTT-Kafka Bridge**: Custom producer transferring MQTT messages to Kafka
- **Kafka**: Message broker for stream processing
- **Spark**: Stream processor for real-time analytics
- **PostgreSQL**: Database for processed data
- **Grafana**: Web frontend for data visualization

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.10+

### 1. Clone and Setup
```bash
git clone <repository-url>
cd iot-monitoring
cp .env.example .env
```

### 2. Start Infrastructure
```bash
docker compose up -d
```

### 3. Run Data Ingestion
```bash
# Terminal 1: Start machine simulator
cd data-ingestion/machine-simulator
pip install -r requirements.txt
python machine_simulator.py

# Terminal 2: Start MQTT-Kafka bridge
cd data-ingestion/mqtt-kafka-bridge
pip install -r requirements.txt
python mqtt_kafka_bridge.py
```

## 📊 Data Flow

1. **Machine Simulator** generates telemetry data every 5 seconds
2. **MQTT Broker** receives telemetry via MQTT protocol
3. **Bridge** consumes MQTT messages and produces to Kafka
4. **Kafka** stores messages in `telemetry` topic
5. **Spark** processes streams for analytics
6. **PostgreSQL** stores aggregated KPIs
7. **Grafana** visualizes real-time dashboards

## 🛠️ Development

### Project Structure
```
├── data-ingestion/          # Data ingestion components
│   ├── machine-simulator/   # IoT device simulator
│   └── mqtt-kafka-bridge/   # MQTT to Kafka bridge
├── processing/             # Stream processing (Spark)
├── frontend/              # Web interface (Grafana)
└── docker-compose.yml     # Infrastructure setup
```

### Technologies Used
- **Python 3.10**: Data ingestion and simulation
- **Apache Kafka**: Message streaming platform
- **Apache Spark**: Stream processing engine
- **PostgreSQL**: Relational database
- **Grafana**: Data visualization
- **MQTT**: IoT messaging protocol
- **Docker**: Containerization

## 📈 Metrics & KPIs

- **OEE (Overall Equipment Effectiveness)**
- **Machine availability and downtime**
- **Temperature and speed monitoring**
- **Alarm detection and alerts**
- **Production throughput analysis**

## 🔧 Configuration

See `.env` file for configuration options:
- Kafka brokers
- Database connections
- MQTT broker settings
- Simulation parameters

## 📝 Project Requirements

This project fulfills the Real-Time Big Data Processing course requirements:
- ✅ Kafka message broker
- ✅ Custom producer (Python)
- ✅ Stream processor (Spark)
- ✅ Web frontend (Grafana)
- ✅ Real-time data processing
- ✅ JSON message format