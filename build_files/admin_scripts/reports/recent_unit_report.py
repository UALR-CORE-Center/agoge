import datetime
import time
from cloud_fn_utilities.gcp.datastore_manager import DataStoreManager
from cloud_fn_utilities.globals import DatastoreKeyTypes


def workouts_in_use(days_prior):
    try:
        days_prior = int(days_prior)
    except ValueError:
        print("Please enter a valid number of days.")
        return

    current_date = datetime.datetime.now()
    prior_date = current_date - datetime.timedelta(days=days_prior)
    prior_timestamp = int(time.mktime(prior_date.timetuple()))

    ds = DataStoreManager(key_type=DatastoreKeyTypes.UNIT)
    units = ds.query(filters=[('creation_timestamp', '>', prior_timestamp)])

    distinct_workout_names = set()
    for unit in units:
        summary = unit.get('summary', {})
        name = summary.get('name')
        if name:
            distinct_workout_names.add(name)

    if distinct_workout_names:
        print("The distinct workouts for this period are:")
        for name in distinct_workout_names:
            print(name)
    else:
        print("No workouts found for this period.")


if __name__ == "__main__":
    response = input("How many days would you like to look back? ")
    workouts_in_use(response)
