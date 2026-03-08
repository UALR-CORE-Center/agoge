import asyncio
import logging
from typing import Optional, List
from enum import Enum

from common.constants.states import (
    WorkoutStates,
    UnitStates,
    ServerStates,
)
from common.constants.database import DbCollections


async def wait_for_state(
    db,
    collection_name,
    doc_id: str,
    desired_state: str,
    state_field: str = 'state',
    timeout: int = 120,
    logger: Optional[logging.Logger] = None,
) -> dict:
    """
    Waits asynchronously for a Firestore document to reach a desired state using on_snapshot.

    Args:
        db: The database interface instance (with listen_to_document and get methods).
        collection_name: The Firestore collection name enum/identifier.
        doc_id (str): The ID of the document to check.
        desired_state (str): The desired state to wait for.
        state_field (str, optional): The field in the document that represents its state. Defaults to 'state'.
        timeout (int, optional): Maximum time in seconds to wait before timing out.
        logger (logging.Logger, optional): Logger instance for debug/info logs.

    Returns:
        dict: The document data if it reaches the desired state within the timeout.

    Raises:
        TimeoutError: If the document doesn't reach the desired state within the allowed time.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    # Create a Future that will be resolved when the desired state is reached
    loop = asyncio.get_event_loop()
    future = loop.create_future()

    def callback(data: dict) -> None:
        """Callback triggered on Firestore document change."""
        try:
            current_state = data.get(state_field, None)
            logger.debug(f"Callback triggered for {doc_id}: current state = {current_state}")
            if current_state == desired_state and not future.done():
                future.set_result(data)
        except Exception as e:
            logger.error(f"Error in callback for document {doc_id}: {e}")
            if not future.done():
                future.set_exception(e)

    # Log initial check
    logger.debug(f"Checking initial state for document {doc_id}")
    initial_entity = db.get(collection_name=collection_name, doc_id=doc_id)
    if initial_entity:
        current_state = initial_entity.get(state_field, None)
        logger.debug(f"Initial state for {doc_id}: {current_state}")
        if current_state == desired_state:
            logger.info(f"Document {doc_id} is already in the desired state '{desired_state}'")
            return initial_entity

    # Register listener for state changes
    logger.debug(f"Setting up listener for document {doc_id}")
    listener = db.listen_to_document(collection_name=collection_name, doc_id=doc_id, callback=callback)

    try:
        # Wait for the future to be resolved
        result = await asyncio.wait_for(future, timeout=timeout)
        logger.info(f"Document {doc_id} reached desired state '{desired_state}'")
        return result
    except asyncio.TimeoutError:
        logger.error(f"Timeout waiting for document {doc_id} to reach state '{desired_state}'")
        raise TimeoutError(
            f"Timed out waiting for document ID {doc_id} in collection {collection_name} to reach state '{desired_state}'"
        )
    finally:
        # Ensure listener cleanup
        logger.debug(f"Stopping listener for document {doc_id}")
        listener.unsubscribe()


def check_state(
    current_state: str,
    desired_states: List[Enum],
    collection_type: DbCollections
) -> bool:
    """
    Checks if the current state of a specific collection matches the desired state.

    Args:
        current_state (str): The current state value (as a string).
        desired_state (Enum): The desired state as an Enum member.
        collection_type (DbCollections): The type of collection (determines the state Enum to use).

    Returns:
        bool: True if the current state matches the desired state's value, False otherwise.

    Raises:
        ValueError: If the collection type is not recognized or the desired state is invalid.
    """
    # Map DbCollections to their respective state Enums
    state_enum_map = {
        DbCollections.UNIT: UnitStates,
        DbCollections.WORKOUT: WorkoutStates,
        DbCollections.SERVER: ServerStates,
    }

    # Get the corresponding Enum class
    state_enum = state_enum_map.get(collection_type)
    if state_enum is None:
        raise ValueError(f"Unsupported collection type: {collection_type}")

    # Create a value-to-name mapping for the Enum
    value_to_name = {state.value: state.name for state in state_enum}

    # Find the state name for the current state
    state_name = value_to_name.get(current_state)
    if state_name is None:
        return False  # Current state is unknown or invalid

    # Compare the state name with the desired state's name
    return state_name in [state.name for state in desired_states]
