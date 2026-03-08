import datetime
from cloud_fn_utilities.gcp.datastore_manager import DataStoreManager
from cloud_fn_utilities.gcp.cloud_env import CloudEnv
from cloud_fn_utilities.globals import DatastoreKeyTypes, get_current_timestamp_utc

def run():
        ds = DataStoreManager(key_type=DatastoreKeyTypes.UNIT)
        current_timestamp = get_current_timestamp_utc()
        units = ds.query(filters=[('workspace_settings.expires', '>', current_timestamp)])
        for unit in units:
            unit_expiration_epoch = unit['workspace_settings']['expires']
            unit_expiration_str = datetime.datetime.utcfromtimestamp(unit_expiration_epoch)
            print(f"unit {unit['id']} expiration: {unit_expiration_str} or {unit_expiration_epoch}")
            workouts = ds.get_children(child_key_type=DatastoreKeyTypes.WORKOUT, parent_id=unit['id'])
            for workout in workouts:
                expiration_epoch = workout['expiration']
                workout_expiration_str = datetime.datetime.utcfromtimestamp(expiration_epoch)
                print(f" - workout {workout['id']} expiration: {workout_expiration_str} or {expiration_epoch}")
                if workout_expiration_str != unit_expiration_str:
                    print(f" - workout has a different expiration than unit. Fixing it now.")
                    workout['expiration'] = unit_expiration_epoch
                    ds.put(workout)


if __name__ == "__main__":
    run()
