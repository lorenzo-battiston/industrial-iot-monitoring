package it.elena.inf.spark;

import com.google.common.collect.ImmutableMap;
import org.apache.spark.sql.Dataset;
import org.apache.spark.sql.Row;
import org.apache.spark.sql.SparkSession;
import org.apache.spark.sql.streaming.StreamingQuery;
import org.apache.spark.sql.streaming.StreamingQueryException;
import org.apache.spark.sql.streaming.Trigger;
import org.apache.spark.sql.types.DataTypes;
import org.apache.spark.sql.types.StructField;
import org.apache.spark.sql.types.StructType;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Properties;
import java.util.concurrent.TimeoutException;

import static org.apache.spark.sql.functions.*;

/**
 * Industrial IoT Monitoring System - Real-time Data Processor
 * 
 * Processes streaming telemetry data from Kafka topics and generates:
 * - Machine performance metrics
 * - Real-time alerts
 * - Factory-wide KPIs
 */
public class IoTProcessor {

    private static final Logger LOGGER = LoggerFactory.getLogger(IoTProcessor.class);
    
    // Configuration defaults
    private static final String DEFAULT_BOOTSTRAP_SERVERS = "localhost:9092";
    private static final String DEFAULT_POSTGRES_HOST = "localhost";
    private static final String DEFAULT_POSTGRES_DB = "iot_analytics";
    private static final String DEFAULT_POSTGRES_USER = "iot_user" ;
    private static final String DEFAULT_POSTGRES_PASSWORD = "iot_password";
    
    // Kafka topics
    private static final String TELEMETRY_TOPIC = "telemetry";
    
    // Processing parameters
    private static final String METRICS_WINDOW = "5 minutes";
    private static final String WATERMARK_DELAY = "2 minutes";

    public static void main(String[] args) throws Exception {
        
        // Parse command line arguments
        Configuration config = parseArguments(args);
        
        LOGGER.info("Starting Industrial IoT Processor with config: {}", config);
        
        // Create Spark session
        SparkSession spark = SparkSession.builder()
                .appName("Industrial-IoT-Processor")
                .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", "true")
                .config("spark.sql.adaptive.enabled", "true")
                .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
                .getOrCreate();

        try {
            // Wait for Kafka topics to be available
            LOGGER.info("Waiting for Kafka topics...");
            KafkaUtils.waitForTopics(config.bootstrapServers, TELEMETRY_TOPIC);
            
            // Read telemetry stream
            Dataset<Row> telemetryStream = readTelemetryStream(spark, config);
            
            if (config.dryRun) {
                // DRY RUN: Print to console
                runDryMode(telemetryStream);
            } else {
                // PRODUCTION: Write to PostgreSQL
                runProductionMode(telemetryStream, config);
            }
            
        } catch (Exception e) {
            LOGGER.error("Error in IoT Processor", e);
            throw e;
        } finally {
            spark.stop();
        }
    }

    /**
     * Read and parse telemetry data from Kafka
     */
    private static Dataset<Row> readTelemetryStream(SparkSession spark, Configuration config) {
        
        LOGGER.info("Setting up telemetry stream from topic: {}", TELEMETRY_TOPIC);
        
        // Define telemetry schema
        StructType telemetrySchema = DataTypes.createStructType(new StructField[]{
            DataTypes.createStructField("timestamp", DataTypes.StringType, false),
            DataTypes.createStructField("machine_id", DataTypes.StringType, false),
            DataTypes.createStructField("temperature", DataTypes.DoubleType, true),
            DataTypes.createStructField("speed", DataTypes.DoubleType, true),
            DataTypes.createStructField("state", DataTypes.StringType, true),
            DataTypes.createStructField("alarm", DataTypes.BooleanType, true),
            DataTypes.createStructField("oee", DataTypes.DoubleType, true),
            DataTypes.createStructField("last_maintenance", DataTypes.StringType, true),
            DataTypes.createStructField("operator_name", DataTypes.StringType, true),
            DataTypes.createStructField("shift", DataTypes.StringType, true),
            DataTypes.createStructField("production_count", DataTypes.IntegerType, true),
            DataTypes.createStructField("location", DataTypes.StringType, true),
            DataTypes.createStructField("firmware_version", DataTypes.StringType, true),
            DataTypes.createStructField("mqtt_topic", DataTypes.StringType, true),
            DataTypes.createStructField("bridge_timestamp", DataTypes.StringType, true),
            DataTypes.createStructField("bridge_id", DataTypes.StringType, true)
        });

        // Read from Kafka
        Dataset<Row> df = spark
                .readStream()
                .format("kafka")
                .option("kafka.bootstrap.servers", config.bootstrapServers)
                .option("subscribe", TELEMETRY_TOPIC)
                .option("startingOffsets", "earliest")  // Changed from "latest" to process existing messages
                .option("failOnDataLoss", "false")
                .option("maxOffsetsPerTrigger", "1000")  // Limit batch size
                .load()
                .selectExpr("CAST(value AS STRING) as json_string")
                .filter("json_string IS NOT NULL AND length(trim(json_string)) > 0")
                .select(from_json(col("json_string"), telemetrySchema).as("telemetry"))
                .filter("telemetry IS NOT NULL")
                .select("telemetry.*")
                .select(
                        to_timestamp(col("timestamp"), "yyyy-MM-dd'T'HH:mm:ss.SSSSSS").as("timestamp"),
                        col("machine_id"),
                        col("temperature"),
                        col("speed"), 
                        col("state"),
                        col("alarm"),
                        col("oee"),
                        to_timestamp(col("last_maintenance"), "yyyy-MM-dd'T'HH:mm:ss.SSSSSS").as("last_maintenance"),
                        col("operator_name"),
                        col("shift"),
                        col("production_count"),
                        col("location"),
                        col("firmware_version"),
                        col("mqtt_topic"),
                        col("bridge_timestamp"),
                        col("bridge_id")
                )
                .filter("machine_id IS NOT NULL AND timestamp IS NOT NULL")
                .withWatermark("timestamp", WATERMARK_DELAY);

        LOGGER.info("Telemetry stream schema:");
        df.printSchema();

        return df;
    }

    /**
     * Run in dry mode - print results to console
     */
    private static void runDryMode(Dataset<Row> telemetryStream) throws StreamingQueryException, TimeoutException {
        
        LOGGER.info("Running in DRY-RUN mode - data will be printed to console");
        
        // Raw telemetry
        StreamingQuery rawQuery = telemetryStream
                .writeStream()
                .outputMode("append")
                .format("console")
                .option("truncate", false)
                .trigger(Trigger.ProcessingTime("30 seconds"))
                .start();

        // Machine metrics (5-minute windows)
        Dataset<Row> machineMetrics = telemetryStream
                .groupBy(
                        window(col("timestamp"), METRICS_WINDOW),
                        col("machine_id")
                )
                .agg(
                        avg("temperature").as("avg_temperature"),
                        max("temperature").as("max_temperature"),
                        min("temperature").as("min_temperature"),
                        avg("speed").as("avg_speed"),
                        max("speed").as("max_speed"),
                        avg("oee").as("avg_oee"),
                        min("oee").as("min_oee"),
                        sum(when(col("alarm"), 1).otherwise(0)).as("alarm_count"),
                        sum(when(col("state").equalTo("Running"), 1).otherwise(0)).as("running_seconds"),
                        sum(when(col("state").equalTo("Maintenance"), 1).otherwise(0)).as("maintenance_seconds"),
                        sum(when(col("state").equalTo("Idle"), 1).otherwise(0)).as("idle_seconds"),
                        count("*").as("total_readings"),
                        first("operator_name").as("operator_name"),
                        first("shift").as("shift"),
                        first("location").as("location"),
                        first("firmware_version").as("firmware_version")
                )
                .select(
                        col("machine_id"),
                        col("window.start").as("window_start"),
                        col("window.end").as("window_end"),
                        col("avg_temperature"),
                        col("max_temperature"),
                        col("min_temperature"),
                        col("avg_speed"),
                        col("max_speed"),
                        col("avg_oee"),
                        col("min_oee"),
                        col("alarm_count"),
                        col("running_seconds"),
                        col("maintenance_seconds"),
                        col("idle_seconds"),
                        col("total_readings"),
                        col("operator_name"),
                        col("shift"),
                        col("location"),
                        col("firmware_version")
                );

        StreamingQuery metricsQuery = machineMetrics
                .writeStream()
                .outputMode("complete")
                .format("console")
                .option("truncate", false)
                .trigger(Trigger.ProcessingTime("1 minute"))
                .start();

        LOGGER.info("DRY-RUN mode started. Check console output for processed data.");
        LOGGER.info("Spark UI available at: http://localhost:4040");
        
        // Wait for termination
        rawQuery.awaitTermination();
        metricsQuery.awaitTermination();
    }

    /**
     * Run in production mode - write to PostgreSQL
     */
    private static void runProductionMode(Dataset<Row> telemetryStream, Configuration config) throws StreamingQueryException, TimeoutException {
        
        LOGGER.info("Running in PRODUCTION mode - writing to PostgreSQL");
        
        // PostgreSQL connection properties
        Properties props = new Properties();
        props.setProperty("user", config.postgresUser);
        props.setProperty("password", config.postgresPassword);
        props.setProperty("driver", "org.postgresql.Driver");
        
        String jdbcUrl = String.format("jdbc:postgresql://%s:5432/%s", 
                config.postgresHost, config.postgresDb);

        // Machine metrics aggregation
        Dataset<Row> machineMetrics = telemetryStream
                .groupBy(
                        window(col("timestamp"), METRICS_WINDOW),
                        col("machine_id")
                )
                .agg(
                        avg("temperature").as("avg_temperature"),
                        max("temperature").as("max_temperature"),
                        min("temperature").as("min_temperature"),
                        avg("speed").as("avg_speed"),
                        max("speed").as("max_speed"),
                        avg("oee").as("avg_oee"),
                        min("oee").as("min_oee"),
                        sum(when(col("alarm"), 1).otherwise(0)).as("alarm_count"),
                        sum(when(col("state").equalTo("Running"), 1).otherwise(0)).as("running_seconds"),
                        sum(when(col("state").equalTo("Maintenance"), 1).otherwise(0)).as("maintenance_seconds"),
                        sum(when(col("state").equalTo("Idle"), 1).otherwise(0)).as("idle_seconds"),
                        count("*").as("total_readings"),
                        first("operator_name").as("operator_name"),
                        first("shift").as("shift"),
                        first("location").as("location"),
                        first("firmware_version").as("firmware_version")
                );

        // Write machine metrics to PostgreSQL
        StreamingQuery metricsQuery = machineMetrics
                .writeStream()
                .foreachBatch((batchDf, batchId) -> {
                    LOGGER.info("Writing batch {} to machine_metrics_5min", batchId);
                    batchDf.select(
                            col("machine_id"),
                            col("window.start").as("window_start"),
                            col("window.end").as("window_end"),
                            col("avg_temperature"),
                            col("max_temperature"),
                            col("min_temperature"),
                            col("avg_speed"),
                            col("max_speed"),
                            col("avg_oee"),
                            col("min_oee"),
                            lit(0).as("production_delta"),
                            col("alarm_count"),
                            col("running_seconds"),
                            col("maintenance_seconds"),
                            col("idle_seconds"),
                            col("total_readings"),
                            col("operator_name"),
                            col("shift"),
                            col("location"),
                            col("firmware_version")
                    ).write()
                     .mode("append")
                     .jdbc(jdbcUrl, "machine_metrics_5min", props);
                })
                .trigger(Trigger.ProcessingTime("1 minute"))
                .start();

        // Real-time alerts processing
        Dataset<Row> alerts = telemetryStream
                .filter(
                    col("alarm").equalTo(true)
                    .or(col("temperature").gt(80.0))
                    .or(col("temperature").lt(10.0))
                    .or(col("speed").gt(2000.0))
                    .or(col("oee").lt(0.5))
                )
                .withColumn("alert_type", 
                    when(col("alarm").equalTo(true), "MACHINE_ALARM")
                    .when(col("temperature").gt(80.0), "HIGH_TEMPERATURE")
                    .when(col("temperature").lt(10.0), "LOW_TEMPERATURE") 
                    .when(col("speed").gt(2000.0), "HIGH_SPEED")
                    .when(col("oee").lt(0.5), "LOW_OEE")
                    .otherwise("UNKNOWN"))
                .withColumn("alert_level",
                    when(col("alarm").equalTo(true), "CRITICAL")
                    .when(col("temperature").gt(90.0).or(col("temperature").lt(5.0)), "CRITICAL")
                    .when(col("speed").gt(2500.0), "CRITICAL")
                    .when(col("oee").lt(0.3), "CRITICAL")
                    .when(col("temperature").gt(80.0).or(col("temperature").lt(10.0)), "WARNING")
                    .when(col("speed").gt(2000.0), "WARNING")
                    .when(col("oee").lt(0.5), "WARNING")
                    .otherwise("INFO"))
                .withColumn("alert_message",
                    when(col("alarm").equalTo(true), "Machine alarm activated")
                    .when(col("temperature").gt(80.0), concat(lit("High temperature detected: "), col("temperature"), lit("°C")))
                    .when(col("temperature").lt(10.0), concat(lit("Low temperature detected: "), col("temperature"), lit("°C")))
                    .when(col("speed").gt(2000.0), concat(lit("High speed detected: "), col("speed"), lit(" RPM")))
                    .when(col("oee").lt(0.5), concat(lit("Low OEE detected: "), col("oee")))
                    .otherwise("Alert condition detected"));

        // Write alerts to PostgreSQL
        StreamingQuery alertsQuery = alerts
                .writeStream()
                .foreachBatch((batchDf, batchId) -> {
                    LOGGER.info("Writing batch {} to machine_alerts", batchId);
                    batchDf.select(
                            col("machine_id"),
                            col("alert_type"),
                            col("alert_level"),
                            col("alert_message"),
                            col("state").as("machine_state"),
                            col("temperature"),
                            col("speed"),
                            col("oee"),
                            col("timestamp")
                    ).write()
                     .mode("append")
                     .jdbc(jdbcUrl, "machine_alerts", props);
                })
                .trigger(Trigger.ProcessingTime("30 seconds"))
                .start();

        // Factory-wide KPIs processing  
        Dataset<Row> factoryKpis = telemetryStream
                .groupBy(window(col("timestamp"), METRICS_WINDOW))
                .agg(
                        countDistinct("machine_id").as("active_machines"),
                        avg("temperature").as("avg_temperature_all"),
                        avg("speed").as("avg_speed_all"),
                        avg("oee").as("avg_oee_all"),
                        sum(when(col("alarm"), 1).otherwise(0)).as("total_alarms"),
                        avg(when(col("state").equalTo("Running"), 100.0)
                            .when(col("state").equalTo("Idle"), 50.0)
                            .otherwise(0.0)).as("availability_percentage"),
                        sum("production_count").as("total_production_estimate")
                )
                .select(
                        lit("factory_overall").as("scope"),
                        col("window.start").as("window_start"),
                        col("window.end").as("window_end"),
                        col("active_machines"),
                        col("avg_temperature_all"),
                        col("avg_speed_all"),
                        col("avg_oee_all"),
                        col("total_alarms"),
                        col("availability_percentage"),
                        col("total_production_estimate")
                );

        // Write factory KPIs to PostgreSQL
        StreamingQuery factoryKpisQuery = factoryKpis
                .writeStream()
                .foreachBatch((batchDf, batchId) -> {
                    LOGGER.info("Writing batch {} to factory_kpis", batchId);
                    batchDf.write()
                           .mode("append")
                           .jdbc(jdbcUrl, "factory_kpis", props);
                })
                .trigger(Trigger.ProcessingTime("2 minutes"))
                .start();

        LOGGER.info("Production mode started. Writing to PostgreSQL at: {}", jdbcUrl);
        LOGGER.info("Spark UI available at: http://localhost:4040");
        
        // Wait for any query to terminate
        spark.streams().awaitAnyTermination();
    }

    /**
     * Parse command line arguments
     */
    private static Configuration parseArguments(String[] args) {
        Configuration config = new Configuration();
        
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--bootstrap-servers":
                    config.bootstrapServers = args[++i];
                    break;
                case "--postgres-host":
                    config.postgresHost = args[++i];
                    break;
                case "--postgres-db":
                    config.postgresDb = args[++i];
                    break;
                case "--postgres-user":
                    config.postgresUser = args[++i];
                    break;
                case "--postgres-password":
                    config.postgresPassword = args[++i];
                    break;
                case "--dry-run":
                    config.dryRun = true;
                    break;
                default:
                    LOGGER.warn("Unknown argument: {}", args[i]);
            }
        }
        
        return config;
    }

    /**
     * Configuration class
     */
    private static class Configuration {
        String bootstrapServers = DEFAULT_BOOTSTRAP_SERVERS;
        String postgresHost = DEFAULT_POSTGRES_HOST;
        String postgresDb = DEFAULT_POSTGRES_DB;
        String postgresUser = DEFAULT_POSTGRES_USER;
        String postgresPassword = DEFAULT_POSTGRES_PASSWORD;
        boolean dryRun = false;

        @Override
        public String toString() {
            return String.format("Configuration{bootstrapServers='%s', postgresHost='%s', postgresDb='%s', postgresUser='%s', dryRun=%s}",
                    bootstrapServers, postgresHost, postgresDb, postgresUser, dryRun);
        }
    }
}