from common.constants.database import DbCollections
from .base_mirror import BasePacketMirror


class SoloBuildMirroring(BasePacketMirror):
    """Creates packet mirroring objects for individual workouts. Resources are not shared
    in the Unit
    """
    def __init__(self, build_id, build=None, debug=False, env_dict=None):
        super().__init__(build_id=build_id, build=build, debug=debug, env_dict=env_dict)
        self.class_name = self.__class__.__name__
        if self.build_id and not self.build:
            self._load_build()

    def _load_build(self):
        if not isinstance(self.build, dict):
            self.build = self.db.get(collection_name=DbCollections.WORKOUT, doc_id=self.build_id)
            if not self.build:
                raise ValueError(f'{self.class_name}:{self.build_id} - No build found for given id')
        return self.build

# [ eof ]
