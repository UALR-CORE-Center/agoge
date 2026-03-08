import logging
import pytest
from typing import List, Tuple, Dict

from api.core.workout_internet_firewall import WorkoutInternetFirewall
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.models.agoge import WorkoutModel
from .network_helpers import get_external_ip, check_rdp_port, check_ssh_connection

logger = logging.getLogger(__name__)


def get_servers_with_human_interaction(workout: WorkoutModel) -> List[Dict]:
    """
    Extracts the names, protocols, usernames, and passwords of servers that have human interaction enabled.

    Args:
        workout (WorkoutModel): The workout data containing the list of servers.

    Returns:
        List[Tuple[str, str, str, str]]: A list of tuples containing server names, protocols, usernames, and passwords.
    """
    if not workout.servers:
        return []

    # Use a list comprehension for concise and efficient filtering
    return [
        {
            'server_name': server.name,
            'hostname': server.hostname,
            'protocol': interaction.protocol,
            'username': interaction.username,
            'password': interaction.password
        }
        for server in workout.servers
        if server.human_interaction
        for interaction in server.human_interaction
        if interaction.display
    ]


async def student_connection_helper(db, env_dict, workout_id: str):
    """
    Helper that tests connectivity (SSH/RDP) for the servers with human interaction.
    """
    # Firewall
    workout_firewall = WorkoutInternetFirewall(workout_id=workout_id, env_dict=env_dict)
    external_ip_address = await get_external_ip()
    workout_firewall.add_ip_address(ip_address=external_ip_address)

    # Get workout data
    workout_data = db.get(collection_name=DbCollections.WORKOUT, doc_id=workout_id)
    if not workout_data:
        pytest.fail(f"Workout with ID {workout_id} not found in data store.")

    workout_object = WorkoutModel(**workout_data)

    # Check servers requiring human interaction
    human_interactions = get_servers_with_human_interaction(workout=workout_object)
    if not human_interactions:
        pytest.fail(f"No servers requiring human interaction found for workout {workout_id}.")

    # Check connectivity
    for server in human_interactions:
        hostname = server.get('hostname')
        protocol = server.get('protocol')
        username = server.get('username')
        password = server.get('password')

        if protocol == 'ssh':
            result = check_ssh_connection(dns_name=hostname, username=username, password=password)
            assert result, f"Failed SSH connection to {hostname} with username {username}."
        elif protocol == 'rdp':
            result = check_rdp_port(dns_name=hostname)
            assert result, f"Failed RDP port connection to {hostname}."
        else:
            pytest.fail(f"Unsupported protocol '{protocol}' for server {hostname}.")


def stop_workout_helper(test_client, workout_id: str):
    """
    Helper that stops a workout using the test client.
    """
    json_payload = {"action": PubSub.Actions.STOP.value}
    response = test_client.put(
        f"/workouts/{workout_id}",
        json=json_payload,
        headers={"Host": "127.0.0.1"},
    )
    assert response.status_code == 200, f"Failed to stop workout {workout_id}."


def start_workout_helper(test_client, workout_id: str):
    """
    Helper that stops a workout using the test client.
    """
    json_payload = {"action": PubSub.Actions.START.value}
    response = test_client.put(
        f"/workouts/{workout_id}",
        json=json_payload,
        headers={"Host": "127.0.0.1"},
    )
    assert response.status_code == 200, f"Failed to start workout {workout_id}."
