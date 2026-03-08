from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes
from common.document_database import DocumentDatabaseFactory
from common.models.agoge import UnitModel
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from .solo_unit import SoloUnit
from .community_unit import CommunityUnit


class UnitFactory:
    """
    A factory class for creating specific types of unit objects based on unit types.

    This class provides a method to create and return either a SoloUnit or CommunityUnit object
    based on the 'unit_type' attribute in the unit entity fetched from the Datastore. The factory
    pattern allows for easy creation and management of different unit types with varying behaviors
    and properties.

    Methods:
        create_unit_object: Creates and returns a unit object based on the unit type.
    """
    cloud_log = Logger(LoggerNames.CLOUD_FN)

    @classmethod
    def create_unit_object(
        cls,
        unit_id: str,
        workout_id: str = None,
        form_data: str = None,
        debug: bool = False,
        force: bool = False,
        env_dict: dict = None
    ):
        """
        Creates and returns a unit object based on the specified unit type.

        Fetches the unit entity from the Datastore using the provided unit_id and determines the type of
        unit to create. Depending on the unit type, either a SoloUnit or CommunityUnit object is instantiated
        and returned.

        Args:
            unit_id (str): The unique identifier of the unit.
            workout_id (str, optional): The identifier for a specific workout within the unit. Defaults to None.
            form_data (str, optional): JSON string containing form data. Defaults to None.
            debug (bool, optional): Flag to enable verbose logging. Defaults to False.
            force (bool, optional): Flag to force operations irrespective of checks. Defaults to False.
            env_dict (dict, optional): Dictionary containing environment variables. Defaults to None.

        Returns:
            SoloUnit or CommunityUnit: An instance of either SoloUnit or CommunityUnit based on the unit type.

        Raises:
            ValueError: If the unit type is not recognized or supported.
        """
        db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )

        unit = db.get(collection_name=DbCollections.UNIT, doc_id=unit_id)
        if not unit:
            cls.cloud_log.warning(f"{cls.__name__}:{unit_id} - Attempting to pull back a "
                                  f"non-existent unit ID")
            return
        unit_type = unit.get('unit_type')
        unit_model = UnitModel(**unit)
        if unit_type in [BuildConstants.UnitType.SOLO, None]:
            return SoloUnit(
                unit_model=unit_model,
                workout_id=workout_id,
                form_data=form_data,
                debug=debug,
                force=force,
                env_dict=env_dict
            )
        elif unit_type == BuildConstants.UnitType.COMMUNITY:
            return CommunityUnit(
                unit_model=unit_model,
                workout_id=workout_id,
                form_data=form_data,
                debug=debug,
                force=force,
                env_dict=env_dict
            )
        else:
            cls.cloud_log.error(f"{cls.__name__}:{unit_id} - In unit factory, unit type "
                                f"{unit_type} is not supported")
            raise ValueError
