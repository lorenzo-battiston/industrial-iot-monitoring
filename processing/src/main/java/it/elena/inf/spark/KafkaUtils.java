package it.elena.inf.spark;

import com.google.common.collect.ImmutableMap;
import com.google.common.collect.ImmutableSet;
import org.apache.kafka.clients.admin.AdminClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Set;
import java.util.concurrent.TimeUnit;

/**
 * Utility class for Kafka operations in IoT monitoring system
 */
public class KafkaUtils {

    private static final Logger LOGGER = LoggerFactory.getLogger(KafkaUtils.class);

    /**
     * Wait for specified Kafka topics to be created before proceeding
     * This prevents Spark from creating topics with default settings
     * 
     * @param bootstrapServers Kafka bootstrap servers
     * @param topics Topic names to wait for
     * @throws Exception if interrupted or Kafka connection fails
     */
    @SuppressWarnings("BusyWait")
    public static void waitForTopics(String bootstrapServers, String... topics) throws Exception {
        Set<String> expectedTopics = ImmutableSet.copyOf(topics);
        
        LOGGER.info("Waiting for Kafka topics: {}", String.join(", ", topics));
        LOGGER.info("This may take several minutes if topics are created by external services...");
        
        // Configuration with shorter timeouts for faster feedback
        ImmutableMap<String, Object> config = ImmutableMap.of(
            "bootstrap.servers", bootstrapServers,
            "request.timeout.ms", 10000,  // 10 seconds
            "connections.max.idle.ms", 10000,
            "metadata.max.age.ms", 10000
        );
        
        try (AdminClient client = AdminClient.create(config)) {
            // Increased max attempts to wait up to 10 minutes (120 * 5 seconds)
            int maxAttempts = 120; 
            int attempt = 0;
            long startTime = System.currentTimeMillis();
            
            while (attempt < maxAttempts) {
                attempt++;
                
                try {
                    Set<String> existingTopics = client.listTopics()
                        .names()
                        .get(5, TimeUnit.SECONDS); // 5 second timeout
                    
                    if (existingTopics.containsAll(expectedTopics)) {
                        long elapsedTime = (System.currentTimeMillis() - startTime) / 1000;
                        LOGGER.info("All required topics are present after {}s: {}", 
                            elapsedTime, String.join(", ", topics));
                        return;
                    }
                    
                    // Log which topics are missing (less frequently to reduce noise)
                    if (attempt % 12 == 0) { // Log every minute
                        Set<String> missingTopics = ImmutableSet.copyOf(expectedTopics);
                        missingTopics.removeAll(existingTopics);
                        long elapsedMinutes = (System.currentTimeMillis() - startTime) / 60000;
                        LOGGER.info("After {}min: Still waiting for topics: {}", 
                            elapsedMinutes, String.join(", ", missingTopics));
                        LOGGER.info("Available topics: {}", existingTopics.isEmpty() ? "none" : String.join(", ", existingTopics));
                    }
                    
                } catch (Exception e) {
                    // Only log connection errors every minute to reduce noise
                    if (attempt % 12 == 0) {
                        LOGGER.warn("Attempt {}/{}: Failed to list topics: {}", 
                            attempt, maxAttempts, e.getMessage());
                    }
                }
                
                if (attempt < maxAttempts) {
                    Thread.sleep(5000); // Wait 5 seconds before retry
                }
            }
            
            // If we get here, topics are still missing after max attempts
            long elapsedMinutes = (System.currentTimeMillis() - startTime) / 60000;
            Set<String> existingTopics = Set.of(); // Default to empty
            try {
                existingTopics = client.listTopics().names().get(5, TimeUnit.SECONDS);
            } catch (Exception ignored) {}
            
            Set<String> missingTopics = ImmutableSet.copyOf(expectedTopics);
            missingTopics.removeAll(existingTopics);
            
            LOGGER.warn("After {}min: Some topics are still missing: {}", elapsedMinutes, String.join(", ", missingTopics));
            LOGGER.warn("Available topics: {}", existingTopics.isEmpty() ? "none" : String.join(", ", existingTopics));
            LOGGER.warn("Proceeding anyway - Spark will attempt to create missing topics with default settings");
            
        } catch (Exception e) {
            LOGGER.error("Error while waiting for topics: {}", e.getMessage());
            LOGGER.info("Proceeding anyway - topics may be created dynamically");
        }
    }

    /**
     * Check if Kafka broker is reachable
     * 
     * @param bootstrapServers Kafka bootstrap servers
     * @return true if broker is reachable, false otherwise
     */
    public static boolean isKafkaReachable(String bootstrapServers) {
        ImmutableMap<String, Object> config = ImmutableMap.of(
            "bootstrap.servers", bootstrapServers,
            "request.timeout.ms", 5000,
            "connections.max.idle.ms", 5000
        );
        
        try (AdminClient client = AdminClient.create(config)) {
            client.listTopics().names().get(3, TimeUnit.SECONDS);
            return true;
        } catch (Exception e) {
            LOGGER.warn("Kafka broker not reachable at {}: {}", bootstrapServers, e.getMessage());
            return false;
        }
    }

    private KafkaUtils() {
        throw new UnsupportedOperationException("Utility class - do not instantiate");
    }
}