import logging
from time import sleep
from confluent_kafka.admin import NewTopic, AdminClient
from confluent_kafka import KafkaException

def setup_topic(topic, bootstrap_servers="localhost:29092", num_partitions=1, replication_factor=1, num_attempts=10):
    client = AdminClient({ "bootstrap.servers": bootstrap_servers })
    template = "topic '{topic}' with {np} partitions and replication factor {rf}"
    topic_desc_new = template.format(topic=topic, np=num_partitions, rf=replication_factor)
    topic_desc_old = "none"
    for i in range(num_attempts):
        try:
            topics = [NewTopic(topic=topic, num_partitions=num_partitions, replication_factor=replication_factor)]
            futures = client.create_topics(new_topics=topics)
            futures[topic].result()
            logging.debug(f"Created {topic_desc_new}")
            return True
        except KafkaException as ex:
            t = client.list_topics().topics.get(topic)
            if t is not None:
                np = len(t.partitions)
                rf = len(t.partitions[0].replicas) if np > 0 else 0
                topic_desc_old = template.format(topic=t, np=np, rf=rf)
                if num_partitions == np and replication_factor == rf:
                    logging.debug(f"Found {topic_desc_new}")
                    return False
        sleep(1.0)
    raise Exception(f"Expected to find/create {topic_desc_new}, found {topic_desc_old}") 