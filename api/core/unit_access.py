import re

from common.constants.database import DbCollections
from common.exceptions import NotFound, Unauthorized
from common.models.agoge import UnitModel
from common.models.users import AgogeUser

LAB_SERVER_PREFIX = re.compile(r'^[a-z]{10}-')


class UnitAccess:
    """
    Resolves the Unit that owns a build object and requires the requester to be one of
    its instructors (or an admin). Role dependencies such as `teacher_required` only
    prove that a user is *an* instructor; every route acting on a specific Unit, Workout
    or lab server must also pass through here.
    """

    def __init__(self, db) -> None:
        self.db = db

    @staticmethod
    def require_instructor(unit: UnitModel | dict, requester: AgogeUser) -> None:
        """Raise Unauthorized unless the requester is an admin or an instructor of the given Unit."""
        if requester.is_admin:
            return
        instructor_ids = (
            unit.get('instructor_id', [])
            if isinstance(unit, dict)
            else unit.instructor_id
        )
        if isinstance(instructor_ids, str):
            instructor_ids = [instructor_ids]
        if requester.email not in (instructor_ids or []):
            raise Unauthorized(
                message="Requesting user is not an instructor of this Unit"
            )

    def unit(self, unit_id: str, requester: AgogeUser) -> dict:
        """Load a Unit and require the requester to be its instructor."""
        unit = self.db.get(collection_name=DbCollections.UNIT, doc_id=unit_id)
        if not unit:
            raise NotFound(message="No Unit found for given ID")
        self.require_instructor(unit, requester)
        return unit

    def workout(self, workout_id: str, requester: AgogeUser) -> dict:
        """Load a Workout and require the requester to be an instructor of its parent Unit."""
        workout = self.db.get(collection_name=DbCollections.WORKOUT, doc_id=workout_id)
        if not workout:
            raise NotFound(message="No Workout found for given ID")
        if not (unit_id := workout.get('parent_id')):
            raise NotFound(message="Workout has no parent Unit")
        self.unit(unit_id, requester)
        return workout

    def build(self, build_id: str, requester: AgogeUser) -> None:
        """Require instructor access to a build ID that may name either a Workout or a Unit."""
        if self.db.get(collection_name=DbCollections.WORKOUT, doc_id=build_id):
            self.workout(build_id, requester)
        else:
            self.unit(build_id, requester)

    def server(self, server_name: str, requester: AgogeUser) -> None:
        """
        Require instructor access to the Unit owning a lab server. Ownership comes from the
        stored server record, never from a course object the caller supplies. Template
        servers (image records with no lab parent) are shared by all instructors.
        """
        if requester.is_admin:
            return
        server = self.db.get(collection_name=DbCollections.SERVER, doc_id=server_name) or {}
        parent_id = server.get('parent_id')
        # Lab servers are named "<build_id>-<server>". If that prefix is a live build, the
        # name is a lab server even when its record is gone, so an image of the same name
        # cannot pass it off as a shared template.
        prefix = server_name.split('-', 1)[0]
        if not parent_id and LAB_SERVER_PREFIX.match(server_name) and (
            self.db.get(collection_name=DbCollections.WORKOUT, doc_id=prefix)
            or self.db.get(collection_name=DbCollections.UNIT, doc_id=prefix)
        ):
            parent_id = prefix
        if not parent_id:
            if self.db.get(collection_name=DbCollections.IMAGE, doc_id=server_name):
                return
            # A deleted lab server can still have snapshots that record their parent
            snapshots = self.db.get(collection_name=DbCollections.SNAPSHOTS, doc_id=server_name) or {}
            parent_id = snapshots.get('parent_build_id')
        if not parent_id:
            raise Unauthorized(message="Requesting user is not an instructor of this server's Unit")
        self.build(parent_id, requester)
