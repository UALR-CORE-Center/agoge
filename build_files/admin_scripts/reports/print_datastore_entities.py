import datetime
import time
from cloud_fn_utilities.gcp.datastore_manager import DataStoreManager
from cloud_fn_utilities.globals import DatastoreKeyTypes


def print_datastore_entity(key_type):
    ds = DataStoreManager(key_type=key_type)
    entities = ds.query(limit=1)
    for entity in entities:
        print(entity)


if __name__ == "__main__":
    for key_type in DatastoreKeyTypes:
        print_datastore_entity(key_type)
