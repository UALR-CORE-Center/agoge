from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.constants.build_constants import BuildConstants
from common.document_database import DocumentDatabaseFactory
from common.models.agoge import WorkoutModel, UnitModel
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from .community_workout import CommunityWorkout
from .solo_workout import SoloWorkout
from .base_workout import BaseWorkout


class WorkoutFactory:
    """
    A factory class for creating workout objects based on specific unit types.

    This class offers a method to instantiate and return either a SoloWorkout or CommunityWorkout object
    depending on the unit type associated with the workout. It encapsulates the logic to determine the
    correct type of workout to create, thus abstracting these details from the client code.

    Methods:
        create_workout_object: Dynamically creates and returns a workout object based on the unit type.
    """
    cloud_log = Logger(LoggerNames.CLOUD_FN)

    @classmethod
    def create_workout_object(
        cls,
        workout_id: str,
        duration_hours: int = 2,
        debug: bool = False,
        env_dict: dict = None
    ) -> BaseWorkout:
        """
        Creates and returns a workout object based on the unit type associated with the workout_id.

        This method fetches the workout entity using the provided workout_id and determines the parent
        unit's type. It then instantiates either a SoloWorkout or CommunityWorkout object based on the
        unit type. If the unit type is unsupported, logs an error.

        Args:
            workout_id (str): The identifier for the workout to be created.
            duration_hours (int, optional): Duration of the workout in hours. Defaults to 2.
            debug (bool, optional): Enables debug mode if set to True. Defaults to False.
            env_dict (dict, optional): Dictionary of environment variables. Defaults to None.

        Returns:
            SoloWorkout or CommunityWorkout: An instance of the workout object based on the unit type.

        Raises:
            ValueError: If the unit type is not recognized or supported.
        """
        db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        workout = db.get(collection_name=DbCollections.WORKOUT, doc_id=workout_id)
        workout_model = WorkoutModel(**workout)
        unit = db.get(collection_name=DbCollections.UNIT, doc_id=workout['parent_id'])
        unit_type = unit.get('unit_type')
        unit_model = UnitModel(**unit)
        if unit_type in [BuildConstants.UnitType.SOLO, None]:
            return SoloWorkout(
                workout_id=workout_id,
                workout_model=workout_model,
                unit_model=unit_model,
                duration_hours=duration_hours,
                debug=debug,
                env_dict=env_dict
            )
        elif unit_type == BuildConstants.UnitType.COMMUNITY:
            return CommunityWorkout(
                workout_id=workout_id,
                workout_model=workout_model,
                unit_model=unit_model,
                duration_hours=duration_hours,
                debug=debug,
                env_dict=env_dict
            )
        else:
            cls.cloud_log.error(f"{cls.__name__}:{unit_type} - In workout factory, given unit type is not supported")

