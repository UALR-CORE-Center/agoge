import guacamole
import ipaddress
import math
import re
import time
import requests

from json import JSONDecodeError
from requests.exceptions import ConnectTimeout, ConnectionError

from common.exceptions import (
    NotFound,
    GuacamoleUserNotFound,
    GuacamoleInvalidSession,
    GuacamoleSessionNotFound,
    GuacamoleServerNotFound,
    BadRequest
)
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import LoggerNames
from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.document_database import DocumentDatabaseFactory


# Apache JSON credentials stop granting new connections at this deadline;
# existing display tunnels end when their student VM stops. Shared DHCP reuse
# must remain quarantined longer than this credential window.
SHARED_CREDENTIAL_TTL_SECONDS = 120


class Guacamole:
    def __init__(
        self,
        build_id: str,
        env_dict: dict,
        build: dict = None,
    ) -> None:
        self.build_id = build_id
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.build = self.load(build_id) if not build else build
        parent_id = self.build.get('parent_id')
        self.community_unit = (self.db.get(collection_name=DbCollections.UNIT, doc_id=parent_id)
                               if parent_id else None)
        proxies = [server for server in (self.community_unit or {}).get('servers') or []
                   if server.get('community_proxy') is True and server.get('community_server') is True]
        self.shared_proxy = proxies[0] if len(proxies) == 1 else None
        shared_auth = (self.build.get('guacamole_auth') == 'json'
                       or any(connection.get('auth_type') == 'json'
                              for connection in self.build.get('proxy_connections') or []))
        if len(proxies) > 1 or (shared_auth and not self.shared_proxy):
            raise GuacamoleInvalidSession('The community display proxy configuration is unavailable')
        target_id = parent_id if self.shared_proxy else self.build_id
        self.guac_url = self.get_guac_url(target_id, self.env.parent_dns_suffix)
        self.username = None
        self.password = None
        self.___session = None

    @staticmethod
    def get_guac_url(
        build_id: str,
        dns_suffix: str
    ) -> str:
        if not str(dns_suffix).startswith("."):
            dns_suffix = f'.{dns_suffix}'
        if dns_suffix.endswith('.'):
            dns_suffix = dns_suffix[:-1]
        return f'https://{build_id}-display{dns_suffix}/guacamole'

    def load(
        self,
        build_id: str
    ) -> dict:
        workout = self.db.get(collection_name=DbCollections.WORKOUT, doc_id=build_id)
        if workout:
            return workout
        raise NotFound(message=f"No build found for given ID, {build_id}")

    def token(self) -> str:
        if self.___session:
            return self.___session.token
        raise GuacamoleInvalidSession(f'Invalid session of type {type(self.___session)}')

    def user_list(self):
        if self.___session:
            return self.___session.list_users()
        raise GuacamoleInvalidSession(f'Invalid session of type {type(self.___session)}')

    def get_user_details(
        self,
        username: str
    ) -> str:
        if self.___session:
            return self.___session.detail_user(username)
        raise GuacamoleInvalidSession(f'Invalid session of type {type(self.___session)}')

    def get_user_connections(self) -> list[str]:
        if self.___session:
            return self.___session.list_connections()
        raise GuacamoleInvalidSession(f'Invalid session of type {type(self.___session)}')

    def get_all_connections(self) -> dict:
        """Extracts all connection (minus session info) from `self.build`"""
        connections = self._get_ordered_connections()
        if self.shared_proxy:
            return {name: {key: value for key, value in connection.items() if not key.startswith('_')}
                    for name, connection in connections.items()}
        return connections

    def get_connection_from_server(
        self,
        server_idx: str
    ) -> dict:
        """
        :param server_idx: int(idx) of server in sorted server list
        :return: dict(token, protocol, hostname, server, guac_url)
        """
        connections = self._get_ordered_connections()
        try:
            server_idx = int(server_idx)
        except (ValueError, TypeError):
            raise BadRequest(message="Invalid or missing value for server index")

        for conn in connections.values():
            if server_idx == conn['idx']:
                if self.shared_proxy:
                    token = self._shared_user_session(conn)
                else:
                    self._set_user_session(conn['username'], conn['password'])
                    token = self.token()
                return {
                    'token': token,
                    'protocol': conn['protocol'],
                    'hostname': conn['hostname'],
                    'server': conn['server'],
                    'url': self.guac_url
                }
        raise GuacamoleServerNotFound(f'No server found with index {server_idx}')

    def _get_ordered_connections(self) -> dict:
        if self.shared_proxy:
            return self._get_shared_connections()
        proxy_connections = self.build.get('proxy_connections', [])
        servers = self.build.get('servers', [])

        if not proxy_connections:
            raise GuacamoleServerNotFound(message='No servers found with proxy connections')

        sorted_list = sorted(proxy_connections, key=lambda x: x['server'])
        sorted_dict = {conn['server']: {'idx': idx, **conn} for idx, conn in enumerate(sorted_list)}

        main_app_url = self.env.main_app_url
        if not main_app_url.startswith('https://'):
            main_app_url = f'https://{main_app_url}'

        for server in servers:
            server_name = server['name']
            if server_name in sorted_dict:
                sorted_dict[server_name]['hostname'] = server.get('hostname')
                sorted_dict[server_name]['protocol'] = server['human_interaction'][0]['protocol']
                sorted_dict[server_name]['url'] = (
                    f'{main_app_url}/student/workout/{self.build_id}'
                    f'/guacamole/{sorted_dict[server_name]["idx"]}'
                )

        return sorted_dict

    def _get_shared_connections(self) -> dict:
        """Use only this Workout's actual, owned student records as targets.

        The saved descriptors are for the user interface, never authority for a
        connection address or credentials on the shared proxy.
        """
        unit = self.community_unit or {}
        unit_id = unit.get('id')
        if (not re.fullmatch(r'[a-z]{10}', str(self.build_id))
                or self.build.get('id') != self.build_id
                or self.build.get('parent_id') != unit_id
                or unit.get('unit_type') != 'community'):
            raise GuacamoleInvalidSession('The community workout does not belong to this lab')
        templates = {server['name']: server for server in unit.get('servers') or []
                     if server.get('name') and not server.get('community_server')}
        connections = {}
        prefix = f'{self.build_id}-'
        for server in self.build.get('servers') or []:
            raw_name = server.get('name') or ''
            name = raw_name[len(prefix):] if raw_name.startswith(prefix) else raw_name
            if name not in templates:
                continue
            runtime = self.db.get(collection_name=DbCollections.SERVER, doc_id=f'{prefix}{name}') or {}
            if runtime.get('parent_id') != self.build_id or runtime.get('community_server'):
                raise GuacamoleInvalidSession('A student display server is missing or belongs to another workout')
            interactions = [item for item in runtime.get('human_interaction') or [] if item.get('display') is True]
            if not interactions:
                continue
            interaction = interactions[0]
            address = next((nic.get('internal_ip') for nic in runtime.get('nics') or []
                            if nic.get('internal_ip')), None)
            try:
                ip = ipaddress.ip_address(address)
                networks = [ipaddress.ip_network(subnet['ip_subnet'], strict=True)
                            for network in unit.get('networks') or [] for subnet in network.get('subnets') or []]
                if ip.version != 4 or not any(ip in network for network in networks):
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                raise GuacamoleInvalidSession('The student display address is not in its lab network') from None
            protocol = interaction.get('protocol') or 'rdp'
            if protocol not in ('ssh', 'vnc', 'rdp'):
                raise GuacamoleInvalidSession('The student display protocol is unsupported')
            connections[name] = {
                'server': name, 'username': f'agoge-{self.build_id}', 'password': None,
                'internal_ip_address': str(ip), 'hostname': runtime.get('hostname'),
                'protocol': protocol, '_runtime': runtime, '_interaction': interaction,
            }
        ordered = {}
        origin = self.env.main_app_url.rstrip('/')
        for idx, name in enumerate(sorted(connections)):
            ordered[name] = {**connections[name], 'idx': idx,
                             'url': f'{origin}/student/workout/{self.build_id}/guacamole/{idx}'}
        if not ordered:
            raise GuacamoleServerNotFound('No student servers have display connections')
        return ordered

    def _shared_user_session(self, connection) -> str:
        from common.services.community_guacamole import CommunityGuacamoleService, encode_json_auth

        now = time.time()
        unit = self.community_unit
        if (self.build.get('state') != WorkoutStates.RUNNING.value
                or unit.get('state') not in (UnitStates.READY.value, UnitStates.RUNNING.value)
                or connection['_runtime'].get('state') != ServerStates.RUNNING.value):
            raise GuacamoleInvalidSession('Start the student workout before opening its shared display')
        limits = [now + SHARED_CREDENTIAL_TTL_SECONDS]
        for index, timestamp in enumerate([(unit.get('workspace_settings') or {}).get('expires'),
                                           self.build.get('expires'), self.build.get('shutoff_timestamp')]):
            if timestamp is None and index > 0:
                continue
            if (type(timestamp) not in (int, float) or not math.isfinite(timestamp) or timestamp <= now):
                raise GuacamoleInvalidSession('The student workout or lab has expired')
            limits.append(timestamp)
        proxy_name = f'{unit["id"]}-{self.shared_proxy["name"]}'
        proxy = self.db.get(collection_name=DbCollections.SERVER, doc_id=proxy_name) or {}
        if (proxy.get('parent_id') != unit['id'] or proxy.get('community_proxy') is not True
                or proxy.get('state') != ServerStates.RUNNING.value):
            raise GuacamoleInvalidSession('The shared community display proxy is not running')
        interaction = connection['_interaction']
        protocol = connection['protocol']
        parameters = {'hostname': connection['internal_ip_address'],
                      'port': {'ssh': '22', 'vnc': '5901', 'rdp': '3389'}[protocol]}
        if interaction.get('username') is not None:
            parameters['username'] = str(interaction['username'])
        if interaction.get('password') is not None:
            parameters['password'] = str(interaction['password'])
        if protocol == 'rdp':
            parameters.update({'security': interaction.get('security_mode') or 'nla', 'ignore-cert': 'true'})
            if interaction.get('domain'):
                parameters['domain'] = str(interaction['domain'])
        payload = {'username': f'agoge-{self.build_id}', 'expires': int(min(limits) * 1000),
                   'connections': {f'{self.build_id}-{connection["server"]}': {
                       'protocol': protocol, 'parameters': parameters,
                   }}}
        try:
            key = CommunityGuacamoleService(self.env.get_env()).get_key(
                unit['id'], proxy.get('guacamole_secret_version_name'))
            encoded = encode_json_auth(payload, key)
        except Exception:
            raise GuacamoleInvalidSession('The shared display authentication configuration is unavailable') from None
        try:
            response = requests.post(f'{self.guac_url}/api/tokens', data={'data': encoded},
                                     timeout=(5, 15), allow_redirects=False)
            if response.status_code != 200:
                raise GuacamoleInvalidSession('The shared display proxy did not accept the session')
            result = response.json()
            token = result.get('authToken') if isinstance(result, dict) else None
            if not isinstance(token, str) or not token or len(token) > 8192:
                raise GuacamoleInvalidSession('The shared display proxy returned an invalid session')
            return token
        except (requests.RequestException, ValueError):
            # Requests carry a signed token and potentially sensitive response
            # bodies. Neither belongs in API errors or logs.
            raise GuacamoleInvalidSession('The shared display proxy is temporarily unavailable') from None

    def _set_user_session(
        self,
        username: str,
        password: str
    ) -> None:
        self.username = str(username)
        self.password = str(password)
        self.___session = self.___get_session()

    def ___get_session(self) -> guacamole.session:
        try:
            return guacamole.session(
                self.guac_url,
                'mysql',
                self.username,
                self.password
            )
        except ConnectTimeout:
            raise GuacamoleSessionNotFound(message='Is the server on?')
        except ConnectionError:
            raise GuacamoleInvalidSession(message='Max retries exceeded')
        except JSONDecodeError:
            raise GuacamoleUserNotFound
        except Exception:
            raise
