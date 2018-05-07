import os
import json

DEFAULT_CONFIG_PATH = os.path.expanduser('~/.config/tildemush/config.json')

CONFIG_DEFAULTS = {
    'server_host':'localhost',
    'server_port': 10014}

def ensure_config_file(path):
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    if not os.path.isfile(path):
        with open(path, 'w') as config_file:
            config_file.write("{}")

class Config:
    def __init__(self, path=DEFAULT_CONFIG_PATH):
        self.path = path
        ensure_config_file(path)
        self._data = CONFIG_DEFAULTS
        self.read()

    def read(self):
        self._data = CONFIG_DEFAULTS

        file_config = None
        with open(self.path) as config_file:
            file_config = json.loads(config_file.read())

        for k,v in file_config.items():
            self._data[k] = v

    def set_path(self, new_path):
        self.path = new_path
        self.read()

    def get(self, key):
        return self._data.get(key)

    def set(self, key, value):
        self._data[key] = value
        self.sync()

    def sync(self):
        with open(self.path, 'w') as config_file:
            config_file.write(json.dumps(self._data, sort_keys=True, indent=4))