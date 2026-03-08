import googleapiclient.discovery
import re

from cloud_fn_utilities.gcp.datastore_manager import DataStoreManager
from cloud_fn_utilities.globals import DatastoreKeyTypes


def get_instance_metadata(instance):
    # Retrieve the instance metadata
    result = compute.instances().get(
        project=project,
        zone=zone,
        instance=instance
    ).execute()
    return result['metadata']


def update_startup_script(instance):
    # Get current metadata
    metadata = get_instance_metadata(instance)

    # Find the startup script in the metadata
    items = metadata.get('items', [])
    startup_script_found = False
    for item in items:
        if item['key'] == 'startup-script':
            new_startup_script = correct_startup_script(item['value'])
            # Modify the startup script
            item['value'] = new_startup_script
            startup_script_found = True
            break

    if not startup_script_found:
        # If the startup script is not found, add it
        print(f'No startup script found for {instance}.')

    # Update the instance metadata
    body = {
        'fingerprint': metadata['fingerprint'],
        'items': items
    }
    compute.instances().setMetadata(
        project=project,
        zone=zone,
        instance=instance,
        body=body
    ).execute()


def correct_startup_script(startup_script):
    # Correct the specific line in the startup script
    corrected_script = re.sub(r"-p 'promiseme'", '-ppromiseme', startup_script)
    return corrected_script


def main():
    instances = []
    while True:
        unit_id = str(input(f"For what unit ID do you wish to build student workouts? "))
        ds_unit = DataStoreManager(key_type=DatastoreKeyTypes.UNIT, key_id=unit_id)
        workouts = ds_unit.get_children(child_key_type=DatastoreKeyTypes.WORKOUT, parent_id=unit_id)
        for workout in workouts:
            instances.append(f"{workout['id']}-display-guacamole-server")

        for instance in instances:
            print(f'Updating startup script for instance: {instance}')
            update_startup_script(instance)
            print(f'Finished for instance: {instance}')


if __name__ == '__main__':
    project = 'trojan-cybergym'
    zone = 'us-central1-a'
    compute = googleapiclient.discovery.build('compute', 'v1')
    main()
