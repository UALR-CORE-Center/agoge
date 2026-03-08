from cloud_fn_utilities.globals import DatastoreKeyTypes
from cloud_fn_utilities.gcp.datastore_manager import DataStoreManager
from cloud_fn_utilities.globals import PubSub


class AttackReport:
    def __init__(self, event_attributes):
        self.event_attributes = event_attributes
        self.attack_id = self.event_attributes.get('attack_id', None)

        # Parent id refers to the workspace that the agent machine is injected into
        self.parent_id = self.event_attributes.get('parent_id', None)
        self.parent_build_type = self.event_attributes.get('parent_build_type', None)
        if not self.parent_id:
            raise AttributeError(f'No attribute build_id')

        self.ds = DataStoreManager()
        self.parent_type = self._get_parent_type()
        self.cyber_arena_build = self.ds.get(key_type=self.parent_build_type, key_id=self.parent_id)
        if not self.cyber_arena_build:
            raise AttributeError(f'No build found with build_id {self.parent_id}')

    def create(self):
        log_event = self.ds.set(key_type=DatastoreKeyTypes.CYBERARENA_ATTACK, key_id=self.attack_id)
        parent_id = self.cyber_arena_build.get('parent_id', None)
        log_event['logs'] = self.event_attributes['data']
        log_event['status'] = self.event_attributes['status']

    def _get_parent_type(self):
        valid_types = [PubSub.BuildActions.WORKOUT.value]
        parent_build_type = self.event_attributes['parent_build_type']
        if parent_build_type in valid_types:
            return PubSub.BuildActions(parent_build_type)

# [ eof ]
