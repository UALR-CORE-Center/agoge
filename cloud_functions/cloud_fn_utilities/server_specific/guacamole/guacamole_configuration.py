import random
import string
import textwrap
from typing import Dict, List, Optional

from common.constants.build_constants import BuildConstants
from common.models.agoge import HumanInteractionModel
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames


class GuacSQL:
    """Holds multi-line SQL templates used for constructing Guacamole initialization and connection scripts.

    For Apache Guacamole JDBC Auth usage, see:
        https://guacamole.apache.org/doc/gug/jdbc-auth.html
    """

    guac_startup_begin = textwrap.dedent("""\
        #!/bin/bash
        
        # Checks for an existing sentinel file (/etc/guac_init_done), which indicates the script has already run.
        if [ -f /etc/guac_init_done ]; then
            echo "Guacamole initialization script has already run. Exiting..."
            exit 0
        fi
        
        # --------------------------------------------------------------------------------
        # Step 1: Set the environment variable for the hostname
        # --------------------------------------------------------------------------------
        export GUAC_HOST="{guac_host}"
        export GUAC_DOMAIN="{guac_domain}"
        
        # --------------------------------------------------------------------------------
        # Step 2: Reset the NGINX so it uses the dynamic DNS hostname 
        # --------------------------------------------------------------------------------
        docker service update --force guacamole_nginx
        
        # --------------------------------------------------------------------------------
        # Step 3: Wait for MySQL to be Ready.
        # --------------------------------------------------------------------------------
        echo "⏳ Waiting for MySQL (service name: 'db') to be ready in Swarm..."
        
        # Ping MySQL inside a throwaway container that shares the overlay network
        until docker run --rm --network guacamole_guacnet \
               mysql:8.0 mysqladmin ping -h"db" -u root --silent
        do
          echo "   MySQL not yet reachable. Retrying..."
          sleep 2
        done
        echo "✅ MySQL is ready!"
        
        # --------------------------------------------------------------------------------
        # Step 4: Prepare the dynamic guacamole configuration through SQL statements.
        # --------------------------------------------------------------------------------
        SQL_FILE="/opt/guacamole/scripts/create_guacamole_user_connections.sql"
        cat <<'EOF' > "$SQL_FILE"
    """)

    guac_startup_user_add = textwrap.dedent("""\
        SET @salt = UNHEX(SHA2(UUID(), 256));
        INSERT INTO guacamole_entity (name, type) VALUES ('{user}', 'USER');
        SELECT entity_id INTO @entity_id FROM guacamole_entity WHERE name = '{user}';
        INSERT INTO guacamole_user (entity_id, password_salt, password_hash, password_date)
        VALUES (
            @entity_id,
            @salt,
            UNHEX(SHA2(CONCAT('{guac_password}', HEX(@salt)), 256)),
            '2020-06-12 00:00:00'
        );
    """)

    guac_startup_ssh = textwrap.dedent("""\
        INSERT INTO guacamole_connection (connection_name, protocol) VALUES ('{connection}', 'ssh');
        SELECT connection_id INTO @connection_id FROM guacamole_connection
            WHERE connection_name = '{connection}';
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'hostname', '{ip}');
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'port', '22');
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'username', '{ssh_username}');
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'password', "{ssh_password}");
    """)

    guac_startup_vnc = textwrap.dedent("""\
        INSERT INTO guacamole_connection (connection_name, protocol) VALUES ('{connection}', 'vnc');
        SELECT connection_id INTO @connection_id FROM guacamole_connection
            WHERE connection_name = '{connection}';
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'hostname', '{ip}');
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'password', "{vnc_password}");
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'port', '5901');
    """)

    guac_startup_rdp = textwrap.dedent("""\
        INSERT INTO guacamole_connection (connection_name, protocol) VALUES ('{connection}', 'rdp');
        SELECT connection_id INTO @connection_id FROM guacamole_connection
            WHERE connection_name = '{connection}';
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'hostname', '{ip}');
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'password', "{rdp_password}");
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'port', '3389');
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'username', '{rdp_username}');
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'security', '{security_mode}');
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'ignore-cert', 'true');
    """)

    guac_startup_rdp_domain = textwrap.dedent("""\
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'domain', '{domain}');
    """)

    guac_startup_join_connection_user = textwrap.dedent("""\
        INSERT INTO guacamole_connection_permission (entity_id, connection_id, permission)
        VALUES (@entity_id, @connection_id, 'READ');
    """)

    guac_startup_end = textwrap.dedent("""\
        EOF

        # Find the running db container created by the swarm service
        DB_CID="$(docker ps -q --filter name=guacamole_db | head -n 1)"
        if [ -z "$DB_CID" ]; then
          echo "Could not find running guacamole_db container"
          exit 1
        fi

        # Read the real root password from the db container environment
        MYSQL_ROOT_PASSWORD="$(docker exec "$DB_CID" printenv MYSQL_ROOT_PASSWORD || true)"
        if [ -z "$MYSQL_ROOT_PASSWORD" ]; then
          echo "MYSQL_ROOT_PASSWORD not found in DB container env"
          exit 1
        fi

        # Apply SQL by piping it into mysql running inside the db container
        docker exec -i "$DB_CID" mysql -u root -p"$MYSQL_ROOT_PASSWORD" guacamole_db < "$SQL_FILE"

        # Only mark success after mysql command succeeds
        touch /etc/guac_init_done
    """)


class GuacamoleConfiguration:
    """Handles the creation of Guacamole connection settings and
    constructs startup SQL scripts for Apache Guacamole.
    """

    def __init__(self, build_id: str, env_dict: Optional[dict] = None) -> None:
        """Initializes GuacamoleConfiguration with a build identifier and optional environment dictionary.

        Args:
            build_id (str): Unique ID for the current build or deployment.
            env_dict (Optional[dict]): An optional dictionary for initializing the CloudEnv object.
        """
        self.build_id = build_id
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.__class__.__name__)
        self.connection_ctr = 1

    def prepare_guac_connection(
        self,
        connection: HumanInteractionModel,
        server_ip: str
    ) -> Dict[str, str]:
        """Prepares a Guacamole connection dictionary to be converted into an SQL script.

        This method takes in user credential information and a server IP address to construct
        a dictionary with all the parameters required by Guacamole.

        Args:
            connection (HumanInteractionModel): Model containing username, password, domain, protocol, etc.
            server_ip (str): The IP address or hostname of the target server.

        Returns:
            Dict[str, str]: A dictionary containing Guacamole connection parameters.

        Raises:
            ValueError: If the provided server_ip is empty or None.
        """
        if not server_ip:
            self.logger.error("No server IP provided. Cannot prepare Guacamole connection.")
            raise ValueError("server_ip cannot be empty or None.")

        protocol = connection.protocol
        security_mode = connection.security_mode

        # Warn for unknown or empty protocol / security mode, then default them.
        if not protocol:
            self.logger.info("No protocol provided. Defaulting to RDP.")
            protocol = BuildConstants.Guacamole.Protocols.RDP.value
        if not security_mode:
            self.logger.info("No security mode provided. Defaulting to NLA.")
            security_mode = BuildConstants.Guacamole.SecurityModes.NLA.value

        # Create a unique workspace username and password
        workspace_username = f"agoge{self.connection_ctr}"
        random_password = self._get_random_password()

        connection_dict = {
            "build_id": self.build_id,
            "protocol": protocol,
            "ip": server_ip,
            "workspace_username": workspace_username,
            "workspace_password": random_password,
            "connection_user": connection.username,
            "connection_password": self.__make_safe_password(connection.password),
            "domain": connection.domain,
            "security_mode": security_mode,
            "connection_name": f"{self.build_id}-{self.connection_ctr}"
        }

        self.logger.debug(f"Prepared Guacamole connection: {connection_dict}")
        self.connection_ctr += 1
        return connection_dict

    def get_guac_startup_script(self, connections: List[Dict[str, str]]) -> str:
        """Builds a Guacamole startup script (SQL) from a list of connection dictionaries.

        The script can be run against the Guacamole database to initialize user
        accounts and connections.

        Args:
            connections (List[Dict[str, str]]): A list of dictionaries generated by prepare_guac_connection.

        Returns:
            str: A multi-line string containing the complete Guacamole startup script.
        """
        self.logger.info(f"Generating Guacamole startup script for {len(connections)} connection(s).")

        guac_host = f"{self.build_id}-display"
        if self.env.parent_dns_suffix:
            guac_domain = self.env.parent_dns_suffix.lstrip(".")
        else:
            guac_domain = self.env.dns_suffix.lstrip(".")

        # Begin script
        startup_script = GuacSQL.guac_startup_begin.format(
            guac_host=guac_host,
            guac_domain=guac_domain
        )

        # Append connection details
        for conn in connections:
            guac_user = conn["workspace_username"]
            guac_password = conn["workspace_password"]
            connection_name = conn["connection_name"]
            protocol = conn["protocol"]

            startup_script += GuacSQL.guac_startup_user_add.format(
                user=guac_user,
                guac_password=guac_password
            )

            if protocol == BuildConstants.Guacamole.Protocols.VNC.value:
                startup_script += GuacSQL.guac_startup_vnc.format(
                    ip=conn["ip"],
                    connection=connection_name,
                    vnc_password=conn["connection_password"]
                )
            elif protocol == BuildConstants.Guacamole.Protocols.SSH.value:
                startup_script += GuacSQL.guac_startup_ssh.format(
                    ip=conn["ip"],
                    connection=connection_name,
                    ssh_username=conn["connection_user"],
                    ssh_password=conn["connection_password"]
                )
            else:
                # Default to RDP
                startup_script += GuacSQL.guac_startup_rdp.format(
                    ip=conn["ip"],
                    connection=connection_name,
                    rdp_username=conn["connection_user"],
                    rdp_password=conn["connection_password"],
                    security_mode=conn["security_mode"]
                )
                if conn.get("domain"):
                    startup_script += GuacSQL.guac_startup_rdp_domain.format(
                        domain=conn["domain"]
                    )

            startup_script += GuacSQL.guac_startup_join_connection_user

        # End script
        startup_script += GuacSQL.guac_startup_end

        self.logger.debug("Final Guacamole startup script generated.")
        return startup_script

    @staticmethod
    def _get_random_password(length: int = 12) -> str:
        """Generates a random alphanumeric password of the specified length.

        The resulting password is then made safe by escaping certain special characters to
        avoid shell or SQL injection issues.

        Args:
            length (int, optional): The desired password length. Defaults to 12.

        Returns:
            str: A safe, random password string.
        """
        letters_and_digits = string.ascii_letters + string.digits
        raw_password = "".join(random.choice(letters_and_digits) for _ in range(length))
        safe_password = GuacamoleConfiguration.__make_safe_password(raw_password)
        return safe_password

    @staticmethod
    def __make_safe_password(password: str) -> str:
        """Escapes certain special characters for safer use in shell/SQL contexts.

        Replaces the `$` and `'` characters to avoid problems in shell or SQL queries.

        Args:
            password (str): The original password string.

        Returns:
            str: A cleaned-up and escaped password string.
        """
        safe_password = password.replace("$", "\\$")
        safe_password = safe_password.replace("'", "\\'")
        return safe_password
