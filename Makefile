# Industrial IoT Monitoring Platform - Management Makefile
# Provides easy commands for system administrators and users

.PHONY: help setup start stop restart status logs clean build test health dashboard-start

# Default target
help:
	@echo "Industrial IoT Monitoring Platform Management"
	@echo "=================================================="
	@echo ""
	@echo "Setup Commands:"
	@echo "  make setup       - Initial setup: create venv and install dependencies"
	@echo "  make build       - Build all Docker images"
	@echo ""
	@echo "Operation Commands:"
	@echo "  make start       - Start the complete IoT pipeline"
	@echo "  make stop        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make status      - Show status of all services"
	@echo ""
	@echo "Monitoring Commands:"
	@echo "  make logs        - Show logs from all services"
	@echo "  make health      - Check system health and connectivity"
	@echo "  make dashboard   - Open monitoring dashboards in browser"
	@echo "  make web-dash    - Start web management dashboard (Terminal 3)"
	@echo ""
	@echo "Development Commands:"
	@echo "  make test        - Run data pipeline tests"
	@echo "  make clean       - Clean up containers and volumes"
	@echo "  make reset       - Complete reset (clean + setup)"

# Virtual environment setup
setup:
	@echo "Setting up Industrial IoT Platform..."
	@if [ ! -d "venv" ]; then \
		echo "Creating Python virtual environment..."; \
		python3 -m venv venv; \
	fi
	@echo "Installing Python dependencies..."
	@. venv/bin/activate && pip install --upgrade pip
	@. venv/bin/activate && pip install -r data_ingestion/machine_simulator/requirements.txt
	@. venv/bin/activate && pip install -r data_ingestion/mqtt_kafka_bridge/requirements.txt
	@. venv/bin/activate && pip install -r web_dashboard/requirements.txt
	@echo "Setup complete!"

# Build Docker images
build:
	@echo "Building Docker images..."
	@docker compose build --no-cache
	@echo "Build complete!"

# Start the infrastructure
start:
	@echo "Starting Industrial IoT Platform..."
	@echo "Starting infrastructure services..."
	@docker compose --profile spark-processing up -d
	@echo "Waiting for services to be ready..."
	@sleep 15
	@$(MAKE) _wait_for_services
	@echo ""
	@echo "Infrastructure is ready! Now starting data pipeline..."
	@echo ""
	@echo "Starting MQTT-Kafka Bridge (Terminal 1):"
	@echo "   make start-bridge"
	@echo ""
	@echo "Starting Machine Simulator (Terminal 2):"
	@echo "   make start-simulator"
	@echo ""
	@echo "Starting Web Dashboard (Terminal 3):"
	@echo "   make web-dash"
	@echo ""
	@echo "Access Points:"
	@echo "   Web Dashboard:     http://localhost:5001"
	@echo "   Grafana Dashboard: http://localhost:3000 (admin/admin)"
	@echo "   Kafka UI:          http://localhost:8080"
	@echo "   Spark Master:      http://localhost:7080"

# Start individual components (for separate terminals)
start-bridge:
	@echo "Starting MQTT-Kafka Bridge..."
	@. venv/bin/activate && python -m data_ingestion.mqtt_kafka_bridge.mqtt_kafka_bridge

start-simulator:
	@echo "Starting Machine Simulator..."
	@. venv/bin/activate && python -m data_ingestion.machine_simulator.machine_simulator

# Start web dashboard
web-dash:
	@echo "Starting Web Management Dashboard..."
	@echo "Dashboard will be available at: http://localhost:5001"
	@. venv/bin/activate && cd web_dashboard && python app.py

# Stop all services
stop:
	@echo "Stopping Industrial IoT Platform..."
	@docker compose --profile spark-processing down
	@echo "All services stopped!"

# Restart services
restart:
	@$(MAKE) stop
	@sleep 5
	@$(MAKE) start

# Show service status
status:
	@echo "Industrial IoT Platform Status"
	@echo "=================================="
	@docker compose ps
	@echo ""
	@echo "Service Health:"
	@$(MAKE) _check_service_health

# View logs
logs:
	@echo "Service Logs (last 50 lines each)"
	@echo "====================================="
	@docker compose logs --tail=50

# System health check
health:
	@echo "System Health Check"
	@echo "======================"
	@$(MAKE) _check_service_health
	@$(MAKE) _check_connectivity
	@$(MAKE) _check_data_flow

# Open dashboards in browser
dashboard:
	@echo "Opening monitoring dashboards..."
	@if command -v open >/dev/null 2>&1; then \
		open http://localhost:5000; \
		open http://localhost:3000; \
		open http://localhost:8080; \
		open http://localhost:7080; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://localhost:5000; \
		xdg-open http://localhost:3000; \
		xdg-open http://localhost:8080; \
		xdg-open http://localhost:7080; \
	else \
		echo "Please manually open:"; \
		echo "  Web Dashboard: http://localhost:5001"; \
		echo "  Grafana: http://localhost:3000"; \
		echo "  Kafka UI: http://localhost:8080"; \
		echo "  Spark Master: http://localhost:7080"; \
	fi

# Run tests
test:
	@echo "Running Data Pipeline Tests..."
	@echo "Testing machine simulator (dry run)..."
	@. venv/bin/activate && python -m data_ingestion.machine_simulator.machine_simulator --dry-run --machines 2 --interval 1 | head -10
	@echo "Simulator test passed!"
	@echo "Testing MQTT-Kafka bridge (dry run)..."
	@. venv/bin/activate && timeout 5 python -m data_ingestion.mqtt_kafka_bridge.mqtt_kafka_bridge --dry-run || true
	@echo "Bridge test passed!"

# Clean up
clean:
	@echo "Cleaning up..."
	@docker compose --profile spark-processing down -v
	@docker system prune -f
	@echo "Cleanup complete!"

# Complete reset
reset:
	@$(MAKE) clean
	@rm -rf venv/
	@$(MAKE) setup

# Internal helper functions
_wait_for_services:
	@echo "Waiting for Kafka to be ready..."
	@timeout 60 bash -c 'until docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list >/dev/null 2>&1; do sleep 2; done' || (echo "Kafka failed to start" && exit 1)
	@echo "Waiting for PostgreSQL to be ready..."
	@timeout 60 bash -c 'until docker exec postgres pg_isready -U iot_user >/dev/null 2>&1; do sleep 2; done' || (echo "PostgreSQL failed to start" && exit 1)
	@echo "Core services are ready!"

_check_service_health:
	@printf "%-20s" "Kafka:"; \
	if docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list >/dev/null 2>&1; then \
		echo "Healthy"; \
	else \
		echo "Unhealthy"; \
	fi
	@printf "%-20s" "PostgreSQL:"; \
	if docker exec postgres pg_isready -U iot_user >/dev/null 2>&1; then \
		echo "Healthy"; \
	else \
		echo "Unhealthy"; \
	fi
	@printf "%-20s" "MQTT Broker:"; \
	if docker exec mqtt-broker mosquitto_pub -h localhost -t test -m "health_check" >/dev/null 2>&1; then \
		echo "Healthy"; \
	else \
		echo "Unhealthy"; \
	fi
	@printf "%-20s" "Grafana:"; \
	if curl -s http://localhost:3000/api/health >/dev/null 2>&1; then \
		echo "Healthy"; \
	else \
		echo "Unhealthy"; \
	fi

_check_connectivity:
	@echo ""
	@echo "Connectivity Tests:"
	@printf "%-30s" "Kafka Topics:"; \
	if docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list | grep -q telemetry; then \
		echo "Topics created"; \
	else \
		echo "Missing topics"; \
	fi
	@printf "%-30s" "Database Schema:"; \
	if docker exec postgres psql -U iot_user -d iot_analytics -c "\dt" | grep -q machine_metrics_5min; then \
		echo "Schema ready"; \
	else \
		echo "Schema missing"; \
	fi

_check_data_flow:
	@echo ""
	@echo "Data Flow Check:"
	@printf "%-30s" "Recent Data:"; \
	if [ $$(docker exec postgres psql -U iot_user -d iot_analytics -t -c "SELECT COUNT(*) FROM machine_metrics_5min WHERE window_start >= NOW() - INTERVAL '10 minutes';" 2>/dev/null | tr -d ' ') -gt 0 ] 2>/dev/null; then \
		echo "Data flowing"; \
	else \
		echo "No recent data"; \
	fi 