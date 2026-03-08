import httpx
import paramiko
import socket
import time


async def get_external_ip():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.ipify.org?format=json", timeout=5)
            response.raise_for_status()
            ip = response.json()["ip"]
            return ip
    except httpx.RequestError as e:
        print(f"Error retrieving external IP: {e}")
        return None


def check_ssh_connection(dns_name, username, password, retries=3, delay=10):
    """
    Checks if an SSH connection can be established.

    Args:
        dns_name (str): The hostname or IP address to connect to.
        username (str): The username for the SSH connection.
        password (str): The password for the SSH connection.
        retries (int): Number of retry attempts (default is 3).
        delay (int): Delay in seconds between retry attempts (default is 10).

    Returns:
        bool: True if the SSH connection is successful, False otherwise.
    """
    for attempt in range(1, retries + 1):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=dns_name, username=username, password=password)
            client.close()
            print(f"SSH connection to {dns_name} successful.")
            return True
        except Exception as e:
            print(f"Attempt {attempt}/{retries}: Failed to connect to {dns_name} via SSH - {e}")
            if attempt < retries:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("All retry attempts failed.")
    return False


def check_rdp_port(dns_name, port=3389, timeout=30, retries=3, delay=10):
    """
    Checks if the RDP port is open on the specified DNS name.

    Args:
        dns_name (str): The hostname or IP address to check.
        port (int): The port number to check (default is 3389).
        timeout (int): Timeout in seconds for the socket connection.
        retries (int): Number of retry attempts (default is 3).
        delay (int): Delay in seconds between retry attempts (default is 10).

    Returns:
        bool: True if the port is open, False otherwise.
    """
    for attempt in range(1, retries + 1):
        try:
            # Attempt to create a socket connection
            with socket.create_connection((dns_name, port), timeout=timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, socket.gaierror) as e:
            print(f"Attempt {attempt}/{retries}: Failed to connect to {dns_name}:{port} - {e}")
            if attempt < retries:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("All retry attempts failed.")
    return False
