from common.constants.pub_sub import PubSub
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from cloud_fn_utilities.budget_manager import BudgetManager
from handlers.build_handler import BuildHandler
from handlers.maintenance_handler import MaintenanceHandler
from handlers.control_handler import ControlHandler

logger = Logger(LoggerNames.CLOUD_FN, class_name="main")


def agoge_cloud_function(event, context, debug_mode: bool = False):
    """
    Responds to a Pub/Sub event from other cloud functions to build servers.

    Args:
         event (dict): The dictionary with data specific to this type of
         event. The `data` field contains the PubsubMessage message. The
         `attributes` field will contain custom attributes if there are any.
         context (google.cloud.functions.Context): The Cloud Functions event
         metadata. The `event_id` field contains the Pub/Sub message ID. The
         `timestamp` field contains the publish time.
         debug_mode (bool): Whether to run functions directly or use PubSub

    Returns:
        A success status
    """
    attributes = event.get('attributes', {})

    logger.info("Cloud Function invoked.", extra={
        "event_id": context.event_id,
        "timestamp": context.timestamp,
        "attributes": attributes
    })

    bm = BudgetManager()
    if not bm.check_budget():
        logger.error(
            "BUDGET ALERT: Budget exceeded. Cloud Function execution halted.",
            extra={"event_id": context.event_id, "attributes": attributes}
        )
        return

    if not attributes:
        logger.error("No attributes provided to the cloud function.", extra={
            "event_id": context.event_id,
        })
        raise ValueError("Attributes missing from the event.")

    handler = attributes.get(PubSub.EventAttributes.HANDLER)
    if not handler:
        logger.error("No handler provided in attributes.", extra={
            "event_id": context.event_id,
            "attributes": attributes
        })
        raise ValueError("Handler missing in attributes.")

    logger.info(f"Processing handler: {handler}", extra={
        "event_id": context.event_id,
        "attributes": attributes
    })

    try:
        if handler == PubSub.Handlers.BUILD:
            BuildHandler(event['attributes'], debug_mode=debug_mode).route()
        elif handler == PubSub.Handlers.CONTROL:
            ControlHandler(event['attributes'], debug=debug_mode).route()
        elif handler == PubSub.Handlers.MAINTENANCE:
            MaintenanceHandler(debug=debug_mode).route()
        elif handler == PubSub.Handlers.AGENCY:
            pass
        else:
            logger.warning(f"Unknown handler: {handler}", extra={
                "event_id": context.event_id,
                "attributes": attributes
            })
            raise ValueError(f"Unknown handler: {handler}")

    except Exception as e:
        logger.error("Error occurred while processing the event.", extra={
            "event_id": context.event_id,
            "attributes": attributes
        })
        raise

    logger.info("Cloud Function execution completed successfully.", extra={
        "event_id": context.event_id,
        "attributes": attributes
    })
