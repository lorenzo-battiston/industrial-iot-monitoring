# Copiato da data_ingestion/mqtt-kafka-bridge/config.py

import yaml
import os

class Config:
    def __init__(self, config_file=None):
        if config_file is None:
            config_file = os.path.join(os.path.dirname(__file__), 'config.yaml')
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def __getitem__(self, key):
        return self.config[key]

    def __contains__(self, key):
        return key in self.config 