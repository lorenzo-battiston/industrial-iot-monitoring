#!/usr/bin/env python3
"""
IoT Machine Simulator - Real-Time Big Data Processing Project
Simulates industrial machine telemetry data and publishes to MQTT broker
"""

import json
import time
import random
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List
from dataclasses import asdict, dataclass
import paho.mqtt.client as mqtt
from zoneinfo import ZoneInfo  # Python 3.9+

from .config import MQTTConfig, SimulationConfig, MachineState


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
            
            good_units = random.randint(80, 200)
            scrap_units = random.randint(5, 20)
            total_units = good_units + scrap_units
            scrap_rate = scrap_units / total_units if total_units > 0 else 0.0
            
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
                production_count=random.randint(100, 1000),
                good_units=good_units,
                scrap_units=scrap_units,
                scrap_rate=round(scrap_rate, 4),
                quality_score=random.uniform(0.8, 0.95),
                error_count=0,
                downtime_incidents=0,
                last_error_time=""
            )
        
        logger.info(f"Initialized {len(self.machines)} machines")
    
    def _setup_mqtt(self):
        """Setup MQTT client connection"""
        # Use unique client ID with timestamp to avoid conflicts
        unique_client_id = f"{self.mqtt_config.client_id}-{int(time.time())}"
        self.mqtt_client = mqtt.Client(unique_client_id)
        
        # Set more robust connection parameters
        self.mqtt_client.reconnect_delay_set(min_delay=1, max_delay=60)
        
        # MQTT callbacks
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logger.info(f"Connected to MQTT broker at {self.mqtt_config.broker_host}:{self.mqtt_config.broker_port}")
            else:
                logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
        
        def on_disconnect(client, userdata, rc):
            if rc != 0:
                logger.warning(f"Unexpected disconnection from MQTT broker (rc={rc})")
        
        def on_publish(client, userdata, mid):
            logger.debug(f"Message {mid} published successfully")
        
        def on_log(client, userdata, level, buf):
            if level == mqtt.MQTT_LOG_ERR:
                logger.error(f"MQTT Error: {buf}")
        
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_disconnect = on_disconnect
        self.mqtt_client.on_publish = on_publish
        self.mqtt_client.on_log = on_log
    
    def _update_machine_state(self, machine: MachineState) -> MachineState:
        """Update machine state with realistic variations"""
        
        # Temperature simulation (with some correlation to machine state)
        if machine.state == "RUNNING":
            # Running machines tend to heat up
            temp_change = random.normalvariate(0.2, 1.0)
        elif machine.state == "IDLE":
            # Idle machines cool down slightly
            temp_change = random.normalvariate(-0.1, 0.5)
        elif machine.state == "MAINTENANCE":
            # Maintenance might involve cooling
            temp_change = random.normalvariate(-0.5, 0.8)
        else:  # ERROR
            # Error state machines have unpredictable temperature
            temp_change = random.normalvariate(0.1, 1.5)
        
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
        elif machine.state == "ERROR":
            # Error state has reduced or erratic speed
            new_speed = random.randint(0, self.sim_config.speed_min)
        else:
            # IDLE or MAINTENANCE
            new_speed = 0
        
        # Enhanced state transitions (Markov chain with ERROR state)
        state_rand = random.random()
        if machine.state == "RUNNING":
            if new_temp > self.sim_config.temperature_critical:
                new_state = "ERROR"  # Overheat causes error
            elif state_rand < 0.05:  # 5% chance to go idle
                new_state = "IDLE"
            elif state_rand < 0.07:  # 2% chance to go maintenance
                new_state = "MAINTENANCE"
            elif state_rand < 0.02:  # 2% chance for random error
                new_state = "ERROR"
            else:
                new_state = "RUNNING"
        elif machine.state == "IDLE":
            if state_rand < 0.3:  # 30% chance to start running
                new_state = "RUNNING"
            elif state_rand < 0.05:  # 5% chance to go maintenance
                new_state = "MAINTENANCE"
            elif state_rand < 0.01:  # 1% chance for error during idle
                new_state = "ERROR"
            else:
                new_state = "IDLE"
        elif machine.state == "MAINTENANCE":
            if state_rand < 0.1:  # 10% chance to finish maintenance
                new_state = "RUNNING"
            elif state_rand < 0.12:  # 2% chance to go idle after maintenance
                new_state = "IDLE"
            else:
                new_state = "MAINTENANCE"
        else:  # ERROR
            if state_rand < 0.15:  # 15% chance to recover to running
                new_state = "RUNNING"
            elif state_rand < 0.25:  # 10% chance to require maintenance
                new_state = "MAINTENANCE"
            elif state_rand < 0.35:  # 10% chance to go idle (safe mode)
                new_state = "IDLE"
            else:
                new_state = "ERROR"  # Stay in error
        
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
        
        # FIXED: Production tracking - now incremental per time period
        new_production_count = machine.production_count
        new_good_units = machine.good_units
        new_scrap_units = machine.scrap_units
        new_quality_score = machine.quality_score
        new_error_count = machine.error_count
        new_downtime_incidents = machine.downtime_incidents
        
        # Initialize incremental values for this cycle
        cycle_good_units = 0
        cycle_scrap_units = 0
        
        if new_state == "RUNNING" and not new_alarm:
            # Simulate production based on speed (incremental for this cycle)
            production_increment = max(0, int(new_speed / 200) + random.randint(-1, 2))
            new_production_count += production_increment
            
            # Quality simulation based on temperature and state transitions
            temp_quality_factor = 1.0 - min(0.3, max(0, (new_temp - 50) / 100))  # Quality degrades with high temp
            speed_quality_factor = 1.0 - min(0.2, max(0, abs(new_speed - self.sim_config.speed_optimal) / 1000))
            base_quality = temp_quality_factor * speed_quality_factor
            
            # Generate scrap based on quality factors (for this cycle only)
            if production_increment > 0:
                scrap_probability = (1 - base_quality) * 0.2  # Up to 20% scrap rate in worst conditions
                for _ in range(production_increment):
                    if random.random() < scrap_probability:
                        cycle_scrap_units += 1
                        new_scrap_units += 1
                    else:
                        cycle_good_units += 1
                        new_good_units += 1
                
                # Update quality score (exponential moving average)
                current_batch_quality = 1 - (scrap_probability * random.uniform(0.5, 1.5))
                new_quality_score = 0.8 * machine.quality_score + 0.2 * max(0, min(1, current_batch_quality))
        
        elif new_state == "ERROR":
            new_error_count += 1
            if machine.state != "ERROR":  # New error occurrence
                new_downtime_incidents += 1
                new_quality_score *= 0.95  # Quality degrades during errors
        
        # Calculate scrap rate
        total_units = new_good_units + new_scrap_units
        new_scrap_rate = (new_scrap_units / total_units) if total_units > 0 else 0.0
        
        # Update error timestamp if entering error state
        new_last_error_time = machine.last_error_time
        if new_state == "ERROR" and machine.state != "ERROR":
            new_last_error_time = datetime.now().isoformat()
        
        # Store incremental values for telemetry message
        setattr(machine, '_cycle_good_units', cycle_good_units)
        setattr(machine, '_cycle_scrap_units', cycle_scrap_units)
        
        # Update machine state
        new_machine = MachineState(
            machine_id=machine.machine_id,
            temperature=round(new_temp, 2),
            speed=new_speed,
            state=new_state,
            alarm=new_alarm,
            oee=round(new_oee, 3),
            last_maintenance=machine.last_maintenance,
            operator_name=machine.operator_name,
            shift=machine.shift,
            production_count=new_production_count,
            good_units=new_good_units,
            scrap_units=new_scrap_units,
            scrap_rate=round(new_scrap_rate, 4),
            quality_score=round(new_quality_score, 3),
            error_count=new_error_count,
            downtime_incidents=new_downtime_incidents,
            last_error_time=new_last_error_time
        )
        
        # Set incremental values on the new machine state for telemetry
        setattr(new_machine, '_cycle_good_units', cycle_good_units)
        setattr(new_machine, '_cycle_scrap_units', cycle_scrap_units)
        
        return new_machine
    
    def _create_telemetry_message(self, machine: MachineState) -> dict:
        """Create a telemetry message from machine state"""
        italy_tz = ZoneInfo("Europe/Rome")
        now_italy = datetime.now(italy_tz)
        
        # Get incremental production values for this cycle
        cycle_good_units = getattr(machine, '_cycle_good_units', 0)
        cycle_scrap_units = getattr(machine, '_cycle_scrap_units', 0)
        
        # REAL Manufacturing Job simulation 
        # In real manufacturing: machines work on specific production orders/batches
        
        # Simulate shift-based production (8-hour shifts)
        shift_targets = {
            "Morning": random.choice([400, 500, 600]),   # 8-hour shift target
            "Afternoon": random.choice([350, 450, 550]), # Different shift performance  
            "Night": random.choice([300, 400, 500])      # Night shift typically lower
        }
        
        target_units = shift_targets.get(machine.shift, 400)
        job_id = f"BATCH_{machine.machine_id}_{random.randint(1000, 9999)}"
        
        # Current shift progress: reset daily, track shift completion
        # In reality this would reset at shift change, here we simulate with modulo
        current_shift_production = machine.production_count % target_units
        produced_units = min(current_shift_production, target_units)  # Never exceed shift target
        
        # Job progress: how much of current shift/batch is completed
        job_progress = produced_units / target_units if target_units > 0 else 0.0
        
        # Generate scrap reason and category only if there was scrap in this cycle
        scrap_reason = None
        scrap_category = None
        if cycle_scrap_units > 0:
            scrap_reason = random.choice([
                "TEMPERATURE_HIGH", "SPEED_DEVIATION", "OPERATOR_ERROR", 
                "MATERIAL_DEFECT", "QUALITY_CHECK", "MACHINE_VIBRATION"
            ])
        
        # Scrap category mapping
        scrap_categories = {
            "TEMPERATURE_HIGH": "MACHINE_ERROR",
            "SPEED_DEVIATION": "MACHINE_ERROR", 
            "MACHINE_VIBRATION": "MACHINE_ERROR",
            "MATERIAL_DEFECT": "MATERIAL",
            "OPERATOR_ERROR": "OPERATOR",
            "QUALITY_CHECK": "QUALITY"
        }
        
        if scrap_reason:
            scrap_category = scrap_categories.get(scrap_reason, "UNKNOWN")
        
        return {
            "timestamp": now_italy.isoformat(),
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
            "firmware_version": "v2.1.3",
            # --- JOB FIELDS ---
            "job_id": job_id,
            "job_progress": job_progress,
            "target_units": target_units,
            "produced_units": produced_units,
            "order_start_time": (now_italy - timedelta(seconds=random.randint(1800, 7200))).isoformat(),
            "elapsed_time_sec": random.randint(1800, 7200),
            # --- ENHANCED QUALITY & SCRAP FIELDS (INCREMENTAL) ---
            "good_units": cycle_good_units,  # Changed to incremental
            "scrap_units": cycle_scrap_units,  # Changed to incremental  
            "scrap_rate": machine.scrap_rate,  # Overall rate
            "quality_score": machine.quality_score,
            "error_count": machine.error_count,
            "downtime_incidents": machine.downtime_incidents,
            "last_error_time": machine.last_error_time,
            "scrap_reason": scrap_reason,
            "scrap_category": scrap_category,
            # --- CUMULATIVE TOTALS FOR REFERENCE ---
            "total_good_units": machine.good_units,  # Total cumulative
            "total_scrap_units": machine.scrap_units  # Total cumulative
        }
    
    def connect(self):
        """Connect to MQTT broker with retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to MQTT broker... (attempt {attempt + 1}/{max_retries})")
                self.mqtt_client.connect(
                    self.mqtt_config.broker_host,
                    self.mqtt_config.broker_port,
                    self.mqtt_config.keepalive
                )
                self.mqtt_client.loop_start()
                
                # Wait a moment to ensure connection is established
                time.sleep(1)
                
                if self.mqtt_client.is_connected():
                    logger.info("Successfully connected to MQTT broker")
                    return True
                else:
                    logger.warning(f"Connection attempt {attempt + 1} failed")
                    
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error("Failed to connect to MQTT broker after all retries")
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