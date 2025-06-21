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
            // Read telemetry stream
            Dataset<Row> telemetryStream = readTelemetryStream(spark, config);

            if (config.dryRun) {
                // DRY RUN: Print to console
                runDryMode(telemetryStream);
            } else {
                // PRODUCTION: Write to PostgreSQL
                runProductionMode(spark, telemetryStream, config);
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
            DataTypes.createStructField("bridge_id", DataTypes.StringType, true),
            DataTypes.createStructField("job_id", DataTypes.StringType, true),
            DataTypes.createStructField("job_progress", DataTypes.DoubleType, true),
            DataTypes.createStructField("target_units", DataTypes.IntegerType, true),
            DataTypes.createStructField("produced_units", DataTypes.IntegerType, true),
            DataTypes.createStructField("order_start_time", DataTypes.StringType, true),
            DataTypes.createStructField("elapsed_time_sec", DataTypes.IntegerType, true)
        });

        Dataset<Row> df = spark
                .readStream()
                .format("kafka")
                .option("kafka.bootstrap.servers", config.bootstrapServers)
                .option("subscribe", TELEMETRY_TOPIC)
                .option("startingOffsets", "earliest")
                .option("failOnDataLoss", "false")
                .option("maxOffsetsPerTrigger", "1000")
                .load()
                .selectExpr("CAST(value AS STRING) as json_string")
                .filter("json_string IS NOT NULL AND length(trim(json_string)) > 0")
                .select(from_json(col("json_string"), telemetrySchema).as("telemetry"))
                .filter("telemetry IS NOT NULL")
                .select("telemetry.*")
                .select(
                        to_timestamp(col("timestamp")).as("timestamp"),
                        col("machine_id"),
                        col("temperature"),
                        col("speed"), 
                        col("state"),
                        col("alarm"),
                        col("oee"),
                        to_timestamp(col("last_maintenance")).as("last_maintenance"),
                        col("operator_name"),
                        col("shift"),
                        col("production_count"),
                        col("location"),
                        col("firmware_version"),
                        col("mqtt_topic"),
                        col("bridge_timestamp"),
                        col("bridge_id"),
                        col("job_id"),
                        col("job_progress"),
                        col("target_units"),
                        col("produced_units"),
                        to_timestamp(col("order_start_time")).as("order_start_time"),
                        col("elapsed_time_sec")
                )
                .filter("machine_id IS NOT NULL AND timestamp IS NOT NULL")
                .withWatermark("timestamp", WATERMARK_DELAY);

        LOGGER.info("Telemetry stream schema:");
        df.printSchema();

        return df;
    }

    private static void runDryMode(Dataset<Row> telemetryStream) throws StreamingQueryException, TimeoutException {
        // implementation not included here
    }

    private static void runProductionMode(SparkSession spark, Dataset<Row> telemetryStream, Configuration config) throws StreamingQueryException, TimeoutException {

        LOGGER.info("Running in PRODUCTION mode - data will be written to PostgreSQL");

        // Machine metrics (5-minute windows)
        Dataset<Row> aggregatedDf = telemetryStream
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
                        first("firmware_version").as("firmware_version"),
                        first("job_id").as("job_id"),
                        first("job_progress").as("job_progress"),
                        first("target_units").as("target_units"),
                        first("produced_units").as("produced_units"),
                        first("order_start_time").as("order_start_time"),
                        first("elapsed_time_sec").as("elapsed_time_sec")
                );

        // Define JDBC properties for PostgreSQL
        Properties connectionProperties = new Properties();
        connectionProperties.setProperty("user", config.postgresUser);
        connectionProperties.setProperty("password", config.postgresPassword);
        connectionProperties.setProperty("driver", "org.postgresql.Driver");

        String jdbcUrl = String.format("jdbc:postgresql://%s:5432/%s", config.postgresHost, config.postgresDb);

        // Write the aggregated data to the console and PostgreSQL
        StreamingQuery query = aggregatedDf
                .writeStream()
                .outputMode("complete")
                .trigger(Trigger.ProcessingTime("1 minute"))
                .foreachBatch((batchDf, batchId) -> {
                    LOGGER.info("Writing batch {} to PostgreSQL...", batchId);
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
                            lit(0).as("production_delta"), // Placeholder
                            col("alarm_count"),
                            col("running_seconds"),
                            col("maintenance_seconds"),
                            col("idle_seconds"),
                            col("total_readings"),
                            col("operator_name"),
                            col("shift"),
                            col("location"),
                            col("firmware_version"),
                            col("job_id"),
                            col("job_progress"),
                            col("target_units"),
                            col("produced_units"),
                            col("order_start_time"),
                            col("elapsed_time_sec")
                    )
                    .write()
                    .format("jdbc")
                    .option("url", jdbcUrl)
                    .option("dbtable", "machine_metrics_5min")
                    .option("user", config.postgresUser)
                    .option("password", config.postgresPassword)
                    .option("driver", "org.postgresql.Driver")
                    .mode("append")
                    .save();
                })
                .start();

        LOGGER.info("PRODUCTION mode started. Writing data to PostgreSQL.");
        LOGGER.info("Spark UI available at: http://localhost:4040");

        query.awaitTermination();
    }

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
