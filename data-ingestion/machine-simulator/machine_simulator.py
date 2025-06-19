#!/usr/bin/env python3
"""
IoT Machine Simulator - Real-Time Big Data Processing Project
Simulates industrial machine telemetry data and publishes to MQTT broker
"""

import json
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List
# import numpy as np  # Removed - using built-in random instead
import paho.mqtt.client as mqtt
from dataclasses import asdict

import yaml
import os
from dataclasses import dataclass

from config import MQTTConfig, SimulationConfig, MachineState


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MachineSimulator:
    """Simulates industrial machine telemetry data"""
    
    def __init__(self, mqtt_config: MQTTConfig, sim_config: SimulationConfig):
        self.mqtt_config = mqtt_config
        self.sim_config = sim_config
        self.machines: Dict[str, MachineState] = {}
        self.mqtt_client = None
        
        # Initialize machines
        self._initialize_machines()
        
        # Setup MQTT client
        self._setup_mqtt()
    
    def _initialize_machines(self):
        """Initialize machine states"""
        operators = ["Alice Johnson", "Bob Smith", "Carol Davis", "David Wilson", "Eva Brown"]
        shifts = ["Morning", "Afternoon", "Night"]
        
        for i in range(1, self.sim_config.machine_count + 1):
            machine_id = f"{self.sim_config.machine_id_prefix}_{i:03d}"
            
            self.machines[machine_id] = MachineState(
                machine_id=machine_id,
                temperature=random.uniform(
                    self.sim_config.temperature_min, 
                    self.sim_config.temperature_max
                ),
                speed=random.randint(
                    self.sim_config.speed_min, 
                    self.sim_config.speed_max
                ),
                state="RUNNING",
                alarm=False,
                oee=random.uniform(0.7, 0.95),
                last_maintenance=(datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
                operator_name=random.choice(operators),
                shift=random.choice(shifts),
                production_count=random.randint(100, 1000)
            )
        
        logger.info(f"Initialized {len(self.machines)} machines")
    
    def _setup_mqtt(self):
        """Setup MQTT client connection"""
        self.mqtt_client = mqtt.Client(self.mqtt_config.client_id)
        
        # MQTT callbacks
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logger.info(f"Connected to MQTT broker at {self.mqtt_config.broker_host}:{self.mqtt_config.broker_port}")
            else:
                logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
        
        def on_disconnect(client, userdata, rc):
            logger.warning("Disconnected from MQTT broker")
        
        def on_publish(client, userdata, mid):
            logger.debug(f"Message {mid} published successfully")
        
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_disconnect = on_disconnect
        self.mqtt_client.on_publish = on_publish
    
    def _update_machine_state(self, machine: MachineState) -> MachineState:
        """Update machine state with realistic variations"""
        
        # Temperature simulation (with some correlation to machine state)
        if machine.state == "RUNNING":
            # Running machines tend to heat up
            temp_change = random.normalvariate(0.2, 1.0)
        elif machine.state == "IDLE":
            # Idle machines cool down slightly
            temp_change = random.normalvariate(-0.1, 0.5)
        else:  # MAINTENANCE
            # Maintenance might involve cooling
            temp_change = random.normalvariate(-0.5, 0.8)
        
        new_temp = machine.temperature + temp_change
        new_temp = max(self.sim_config.temperature_min, 
                      min(self.sim_config.temperature_max, new_temp))
        
        # Speed simulation (with noise)
        if machine.state == "RUNNING":
            speed_target = self.sim_config.speed_optimal
            speed_noise = random.normalvariate(0, 50)
            new_speed = int(speed_target + speed_noise)
            new_speed = max(self.sim_config.speed_min, 
                           min(self.sim_config.speed_max, new_speed))
        else:
            new_speed = 0
        
        # State transitions (simple Markov chain)
        state_rand = random.random()
        if machine.state == "RUNNING":
            if state_rand < 0.05:  # 5% chance to go idle
                new_state = "IDLE"
            elif state_rand < 0.07:  # 2% chance to go maintenance
                new_state = "MAINTENANCE"
            else:
                new_state = "RUNNING"
        elif machine.state == "IDLE":
            if state_rand < 0.3:  # 30% chance to start running
                new_state = "RUNNING"
            elif state_rand < 0.05:  # 5% chance to go maintenance
                new_state = "MAINTENANCE"
            else:
                new_state = "IDLE"
        else:  # MAINTENANCE
            if state_rand < 0.1:  # 10% chance to finish maintenance
                new_state = "RUNNING"
            else:
                new_state = "MAINTENANCE"
        
        # Alarm logic (temperature-based + random)
        alarm_prob = self.sim_config.alarm_base_probability
        if new_temp > self.sim_config.temperature_critical:
            alarm_prob = self.sim_config.alarm_critical_probability
        
        new_alarm = random.random() < alarm_prob
        
        # OEE calculation (simplified)
        if new_state == "RUNNING" and not new_alarm:
            oee_change = random.normalvariate(0.01, 0.05)
        else:
            oee_change = random.normalvariate(-0.02, 0.03)
        
        new_oee = max(0.0, min(1.0, machine.oee + oee_change))
        
        # Production count (only increases when running)
        new_production_count = machine.production_count
        if new_state == "RUNNING" and not new_alarm:
            # Simulate production based on speed
            production_increment = max(0, int(new_speed / 100) + random.randint(-2, 3))
            new_production_count += production_increment
        
        # Update machine state
        return MachineState(
            machine_id=machine.machine_id,
            temperature=round(new_temp, 2),
            speed=new_speed,
            state=new_state,
            alarm=new_alarm,
            oee=round(new_oee, 3),
            last_maintenance=machine.last_maintenance,
            operator_name=machine.operator_name,
            shift=machine.shift,
            production_count=new_production_count
        )
    
    def _create_telemetry_message(self, machine: MachineState) -> dict:
        """Create telemetry message in JSON format"""
        return {
            "timestamp": datetime.now().isoformat(),
            "machine_id": machine.machine_id,
            "temperature": machine.temperature,
            "speed": machine.speed,
            "state": machine.state,
            "alarm": machine.alarm,
            "oee": machine.oee,
            "last_maintenance": machine.last_maintenance,
            "operator_name": machine.operator_name,
            "shift": machine.shift,
            "production_count": machine.production_count,
            "location": f"Factory Floor A - Line {machine.machine_id[-1]}",
            "firmware_version": "v2.1.3"
        }
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.mqtt_client.connect(
                self.mqtt_config.broker_host,
                self.mqtt_config.broker_port,
                self.mqtt_config.keepalive
            )
            self.mqtt_client.loop_start()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
    
    def run_simulation(self, dry_run: bool = False):
        """Run the simulation loop"""
        logger.info(f"Starting simulation with {len(self.machines)} machines")
        logger.info(f"Publishing interval: {self.sim_config.interval_seconds} seconds")
        logger.info(f"Dry run mode: {dry_run}")
        
        if not dry_run and not self.connect():
            logger.error("Failed to connect to MQTT broker. Exiting.")
            return
        
        try:
            iteration = 0
            while True:
                iteration += 1
                logger.info(f"Simulation iteration {iteration}")
                
                for machine_id, machine in self.machines.items():
                    # Update machine state
                    updated_machine = self._update_machine_state(machine)
                    self.machines[machine_id] = updated_machine
                    
                    # Create telemetry message
                    telemetry = self._create_telemetry_message(updated_machine)
                    message = json.dumps(telemetry, indent=2 if dry_run else None)
                    
                    if dry_run:
                        # Print to stdout for testing
                        print(f"\n--- {machine_id} ---")
                        print(message)
                    else:
                        # Publish to MQTT
                        topic = f"{self.mqtt_config.topic_prefix}/{machine_id}/telemetry"
                        result = self.mqtt_client.publish(topic, message)
                        
                        if result.rc != mqtt.MQTT_ERR_SUCCESS:
                            logger.error(f"Failed to publish message for {machine_id}")
                        else:
                            logger.debug(f"Published telemetry for {machine_id}")
                
                # Wait for next iteration
                time.sleep(self.sim_config.interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("Simulation stopped by user")
        except Exception as e:
            logger.error(f"Simulation error: {e}")
        finally:
            if not dry_run:
                self.disconnect()

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="IoT Machine Simulator")
    parser.add_argument('--dry-run', action='store_true', 
                       help='Print messages to stdout instead of publishing to MQTT')
    parser.add_argument('--machines', type=int, default=None,
                       help='Number of machines to simulate')
    parser.add_argument('--interval', type=int, default=None,
                       help='Interval between messages in seconds')
    
    args = parser.parse_args()
    
    # Load configurations
    mqtt_config = MQTTConfig()
    sim_config = SimulationConfig()
    
    # Override with command line arguments
    if args.machines:
        sim_config.machine_count = args.machines
    if args.interval:
        sim_config.interval_seconds = args.interval
    
    # Create and run simulator
    simulator = MachineSimulator(mqtt_config, sim_config)
    simulator.run_simulation(dry_run=args.dry_run)

if __name__ == "__main__":
    main()