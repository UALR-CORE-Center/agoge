import guacamole

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
from common.document_database import DocumentDatabaseFactory


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
        self.guac_url = self.get_guac_url(self.build_id, self.env.parent_dns_suffix)
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
        return self._get_ordered_connections()

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
        except ValueError:
            raise BadRequest(message="Invalid or missing value for server index")

        for conn in connections.values():
            if server_idx == conn['idx']:
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
