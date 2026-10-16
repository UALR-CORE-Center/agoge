from common.constants.build_constants import BuildConstants
from common.constants.states import WorkoutStates
from common.models.agoge import AgogeWorkoutSummaryModel, UnitModel, WebApplicationModel, WorkoutModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.timestamps import Timestamps


def build_workout_record(
    unit_model: UnitModel,
    workout_id: str,
    log_name: str,
    test: bool = False,
    **kwargs
) -> dict:
    """
    Creates and validates a NOT_BUILT workout record for a unit. Writing it starts no VMs; a later
    workout BUILD does. Shared by the Cloud Function (BaseUnit) and the API (CTF team rosters).

    Args:
        unit_model (UnitModel): The unit the workout belongs to.
        workout_id (str): The identifier for the workout.
        log_name (str): Logger name for validation failures.
        test (bool): Marks the record as a test record.
        **kwargs (Dict[str, Any]): Additional top-level details to add to record model

    Returns:
        dict: WorkoutModel in dictionary form representing the workout record.
    """
    unit_summary = unit_model.summary
    workout_record = {
        'id': workout_id,
        'parent_id': unit_model.id,
        'parent_build_type': BuildConstants.BuildType.UNIT,
        'build_type': BuildConstants.BuildType.WORKOUT,
        'creation_timestamp': Timestamps.get_current_timestamp_utc(),
        'state': WorkoutStates.NOT_BUILT.value,
        'summary': AgogeWorkoutSummaryModel(
            name=unit_summary.name,
            description=unit_summary.description,
            student_instructions_url=unit_summary.student_instructions_url
        )
    }

    for key, value in kwargs.items():
        if key == 'student_email':
            workout_record[key] = str(value).lower()
        else:
            workout_record[key] = value

    # Expiration based on workout_duration_days
    if (workout_duration_days := unit_model.workout_duration_days) is not None:
        workout_record['expires'] = Timestamps.get_current_timestamp_utc(add_seconds=86400*workout_duration_days)
    else:
        workout_record['expires'] = unit_model.workspace_settings.expires

    # Networks, servers, and firewall_rules
    for key in ['unit_type', 'networks', 'servers', 'firewall_rules', 'firewalls']:
        value = getattr(unit_model, key, None)
        if value:
            if key == 'servers':
                workout_record['shutoff_timestamp'] = (
                    Timestamps.get_current_timestamp_utc(add_seconds=7200, round_to_quarter=True)
                )
            workout_record[key] = value

    # Optional Fields
    # Process web_applications if they exist
    if (web_applications := unit_model.web_applications) is not None:
        workout_record['web_applications'] = [
            WebApplicationModel(
                host_name=app.host_name,
                name=app.name,
                starting_directory=app.starting_directory,
                url=f"https://{app.host_name}/{app.starting_directory}"
            )
            for app in web_applications
        ]

    # Optional escape room, assessment, or lms_quiz
    if (escape_room := unit_model.escape_room) is not None:
        workout_record['escape_room'] = escape_room
    elif (assessment := unit_model.assessment) is not None:
        workout_record['assessment'] = assessment
    elif (lms_integration := unit_model.lms_integration) is not None:
        workout_record['lms_integration'] = lms_integration

    if test:
        workout_record['test'] = True

    return ModelValidator(model=WorkoutModel, log_location=log_name).load(workout_record, as_dict=True)
