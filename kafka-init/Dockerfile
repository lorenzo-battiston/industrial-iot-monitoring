FROM confluentinc/cp-kafka:7.4.0

USER root
RUN microdnf update && microdnf install -y nc && microdnf clean all

# Copy and prepare the script
COPY create-topics.sh /tmp/
RUN chmod +x /tmp/create-topics.sh

# Run the script
CMD ["/tmp/create-topics.sh"] 