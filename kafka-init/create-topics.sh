#!/bin/bash
# This script waits for Kafka to be ready and then creates the required topics.

set -e

# Wait for Kafka to be ready
echo "Waiting for Kafka to be available..."
while ! nc -z kafka 9092; do
  sleep 1
done
echo "Kafka is up!"

# Create topics
echo "Creating Kafka topics..."
kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic telemetry --partitions 3 --replication-factor 1
kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic alerts --partitions 1 --replication-factor 1

echo "Topics successfully created." 