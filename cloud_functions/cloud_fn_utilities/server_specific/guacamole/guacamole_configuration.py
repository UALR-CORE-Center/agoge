import random
import string
import textwrap
from typing import Dict, List, Optional
from uuid import uuid4

from common.constants.build_constants import BuildConstants
from common.models.agoge import HumanInteractionModel
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames


class GuacSQL:
    """Holds multi-line SQL templates used for constructing Guacamole initialization and connection scripts.

    For Apache Guacamole JDBC Auth usage, see:
        https://guacamole.apache.org/doc/gug/jdbc-auth.html
    """

    legacy_swarm_recovery = textwrap.dedent("""\
        # Serialize startup and manual retries on this proxy.
        exec 9>/run/agoge-guacamole-startup.lock || exit 1
        flock -n 9 || exit 1

        # Read credentials from the image before Docker discards its old tasks.
        load_legacy_mysql_credentials() {
          local tasks env_lines='' entry
          tasks="$(timeout 10s docker ps -aq --filter label=com.docker.swarm.service.name=guacamole_db)" || return 1
          if [ -n "$tasks" ]; then
            env_lines="$(timeout 10s docker inspect --type container \\
              --format '{{range .Config.Env}}{{println .}}{{end}}' "${tasks%%$'\\n'*}" 2>/dev/null)"
          fi
          if [ -z "$env_lines" ]; then
            env_lines="$(timeout 10s docker service inspect guacamole_db \\
              --format '{{range .Spec.TaskTemplate.ContainerSpec.Env}}{{println .}}{{end}}' 2>/dev/null)"
          fi
          if [ -z "$env_lines" ] && [ -s /opt/guacamole/.env ]; then
            env_lines="$(
              source /opt/guacamole/.env >/dev/null 2>&1 || exit 1
              printf 'MYSQL_ROOT_PASSWORD=%s\\nMYSQL_PASSWORD=%s\\n' "$MYSQL_ROOT_PASSWORD" "$MYSQL_PASSWORD"
            )" || return 1
          fi
          while IFS= read -r entry; do
            case "$entry" in
              MYSQL_ROOT_PASSWORD=*) MYSQL_ROOT_PASSWORD="${entry#*=}" ;;
              MYSQL_PASSWORD=*) MYSQL_PASSWORD="${entry#*=}" ;;
            esac
          done <<< "$env_lines"
          [ -n "$MYSQL_ROOT_PASSWORD" ] && [ -n "$MYSQL_PASSWORD" ]
        }

        guac_ip="$(curl -fsS --max-time 10 -H 'Metadata-Flavor: Google' \\
          http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/ip)" || exit 1
        swarm="$(timeout 10s docker info \\
          --format '{{.Swarm.LocalNodeState}}/{{.Swarm.ControlAvailable}}/{{.Swarm.NodeAddr}}/{{.Swarm.Nodes}}')" || exit 1
        if [ -z "$guac_ip" ] || [ "${swarm##*/}" -gt 1 ]; then
          echo "Guacamole recovery requires this proxy's IP and a single-node Swarm." >&2
          exit 1
        fi

        local_swarm_ready=false
        stack_deployed=false
        if [ "$swarm" = "active/true/$guac_ip/1" ] && \\
           [ "$(timeout 10s docker node inspect self --format '{{.Status.State}}')" = ready ]; then
          local_swarm_ready=true
          if timeout 10s docker service inspect guacamole_db guacamole_guacd \\
            guacamole_guacamole guacamole_nginx >/dev/null 2>&1; then
            stack_deployed=true
          fi
        fi

        if [ "$stack_deployed" = false ]; then
          db_data="$(timeout 10s docker volume inspect --format '{{.Mountpoint}}' guacamole_db_data 2>/dev/null)"
          if [ ! -s /opt/guacamole/docker-compose.yml ] || [ -z "$db_data" ] || [ ! -d "$db_data/mysql" ]; then
            echo "Guacamole recovery needs the stack file and initialized MySQL volume from the project image." >&2
            exit 1
          fi
          export MYSQL_ROOT_PASSWORD= MYSQL_PASSWORD=
          db_env=/etc/agoge-guacamole-db.env
          if [ -s "$db_env" ]; then
            source "$db_env" || exit 1
          elif load_legacy_mysql_credentials; then
            # Preserve the credentials if startup is interrupted after leaving the Swarm.
            saved_env="$(mktemp "$db_env.XXXXXX")" || exit 1
            printf 'MYSQL_ROOT_PASSWORD=%q\\nMYSQL_PASSWORD=%q\\n' \\
              "$MYSQL_ROOT_PASSWORD" "$MYSQL_PASSWORD" > "$saved_env" && mv -f "$saved_env" "$db_env" || exit 1
          fi
          if [ -z "$MYSQL_ROOT_PASSWORD" ] || [ -z "$MYSQL_PASSWORD" ]; then
            echo "Guacamole recovery could not read the existing MySQL credentials from the project image." >&2
            exit 1
          fi

          if [ "$local_swarm_ready" = false ]; then
            echo "Recreating the local Guacamole Swarm on this proxy VM."
            if [ "${swarm%%/*}" != inactive ]; then
              timeout 30s docker swarm leave --force >/dev/null || exit 1
            fi
            # An unusable Swarm can leave running tasks with its old node ID.
            old_tasks="$(timeout 10s docker ps -q --filter label=com.docker.stack.namespace=guacamole)" || exit 1
            if [ -n "$old_tasks" ]; then
              mapfile -t old_task_ids <<< "$old_tasks"
              timeout 40s docker stop "${old_task_ids[@]}" >/dev/null || exit 1
            fi
            timeout 45s docker swarm init --advertise-addr "$guac_ip" >/dev/null || exit 1
          fi

          echo "Deploying the Guacamole stack with its existing MySQL volume."
          if ! (cd /opt/guacamole && timeout 90s docker stack deploy --resolve-image never \\
            --compose-file docker-compose.yml guacamole) >/dev/null 2>&1; then
            echo "Guacamole stack deployment failed. Check Docker on the proxy VM." >&2
            exit 1
          fi
          swarm_recovered=true
        else
          swarm_recovered=false
        fi
        unset MYSQL_ROOT_PASSWORD MYSQL_PASSWORD
    """)

    guac_startup_begin = textwrap.dedent("""\
        #!/bin/bash
        umask 077
        export GUAC_HOST="{guac_host}"
        export GUAC_DOMAIN="{guac_domain}"
        {prepare_swarm}
        
        # Checks for an existing sentinel file (/etc/guac_init_done), which indicates the script has already run.
        if [ -f /etc/guac_init_done ]; then
            {resume_nginx}
            echo "Guacamole initialization script has already run. Exiting..."
            exit 0
        fi

        # --------------------------------------------------------------------------------
        # Step 2: Reset the NGINX so it uses the dynamic DNS hostname 
        # --------------------------------------------------------------------------------
        {reload_nginx}
        
        # --------------------------------------------------------------------------------
        # Step 3: Wait for MySQL to be Ready.
        # --------------------------------------------------------------------------------
        echo "⏳ Waiting for MySQL (service name: 'db') to be ready in Swarm..."
        
        # Check the existing Swarm task directly. Starting another container
        # would require a fresh overlay network attachment.
        deadline=$((SECONDS + 180))
        while :; do
          DB_CID="$(timeout 8s docker ps -q --filter label=com.docker.swarm.service.name=guacamole_db | head -n 1)"
          if [ -n "$DB_CID" ] && timeout 8s docker exec "$DB_CID" sh -c \\
            'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --connect-timeout=5 --host=127.0.0.1 --user=root guacamole_db -e "SELECT 1 FROM guacamole_entity LIMIT 0"' \\
            >/dev/null 2>&1; then
            break
          fi
          if [ "$SECONDS" -ge "$deadline" ]; then
            echo "Guacamole MySQL task did not become ready within 180 seconds." >&2
            exit 1
          fi
          sleep 2
        done
        echo "✅ MySQL is ready!"
        
        # --------------------------------------------------------------------------------
        # Step 4: Prepare the dynamic guacamole configuration through SQL statements.
        # --------------------------------------------------------------------------------
        SQL_FILE="/opt/guacamole/scripts/create_guacamole_user_connections.sql"
        cat <<'{sql_delimiter}' > "$SQL_FILE"
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
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'port', '{port}');
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'username', '{ssh_username}');
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'password', "{ssh_password}");
    """)

    guac_startup_vnc = textwrap.dedent("""\
        INSERT INTO guacamole_connection (connection_name, protocol) VALUES ('{connection}', 'vnc');
        SELECT connection_id INTO @connection_id FROM guacamole_connection
            WHERE connection_name = '{connection}';
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'hostname', '{ip}');
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'password', "{vnc_password}");
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'port', '{port}');
    """)

    guac_startup_rdp = textwrap.dedent("""\
        INSERT INTO guacamole_connection (connection_name, protocol) VALUES ('{connection}', 'rdp');
        SELECT connection_id INTO @connection_id FROM guacamole_connection
            WHERE connection_name = '{connection}';
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'hostname', '{ip}');
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'password', "{rdp_password}");
        INSERT INTO guacamole_connection_parameter VALUES (@connection_id, 'port', '{port}');
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
        SQL_DELIMITER

        # Use the MySQL task's own credentials inside the container.
        timeout 60s docker exec -i "$DB_CID" sh -c \\
          'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --user=root guacamole_db' < "$SQL_FILE" || exit 1

        # Only mark success after mysql command succeeds
        touch /etc/guac_init_done || exit 1
        GUAC_START_NGINX
        echo "Guacamole connections configured."
    """)


class GuacamoleConfiguration:
    """Handles the creation of Guacamole connection settings and
    constructs startup SQL scripts for Apache Guacamole.
    """
    # Used when a connection has no `port` override; VNC 5901 is display :1
    DEFAULT_PORTS = {
        BuildConstants.Guacamole.Protocols.RDP.value: 3389,
        BuildConstants.Guacamole.Protocols.SSH.value: 22,
        BuildConstants.Guacamole.Protocols.VNC.value: 5901,
    }

    def __init__(self, build_id: str, env_dict: Optional[dict] = None) -> None:
        """Initializes GuacamoleConfiguration with a build identifier and optional environment dictionary.

        Args:
            build_id (str): Unique ID for the current build or deployment.
            env_dict (Optional[dict]): An optional dictionary for initializing the CloudEnv object.
        """
        self.build_id = build_id
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.class_name = self.__class__.__name__
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.connection_ctr = 1

    def prepare_guac_connection(
        self,
        connection: HumanInteractionModel,
        server_ip: str,
        ip_aliases: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Prepares a Guacamole connection dictionary to be converted into an SQL script.

        This method takes in user credential information and a server IP address to construct
        a dictionary with all the parameters required by Guacamole.

        Args:
            connection (HumanInteractionModel): Model containing username, password, domain, protocol, etc.
            server_ip (str): The IP address or hostname of the target server.
            ip_aliases (Optional[List[str]]): The alias IPs on the server's NIC 0. A connection with
                `alias_index` targets `ip_aliases[alias_index]` (a nested guest exposed through that alias)
                instead of `server_ip`.

        Returns:
            Dict[str, str]: A dictionary containing Guacamole connection parameters, including the
                resolved target `ip` and `port`.

        Raises:
            ValueError: If the provided server_ip is empty or None, or `alias_index` is out of range.
        """
        if not server_ip:
            self.logger.error("No server IP provided. Cannot prepare Guacamole connection.")
            raise ValueError("server_ip cannot be empty or None.")

        target_ip = self._resolve_target_ip(connection, server_ip, ip_aliases)
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
            "ip": target_ip,
            "port": str(connection.port or self.DEFAULT_PORTS.get(protocol, self.DEFAULT_PORTS[BuildConstants.Guacamole.Protocols.RDP.value])),
            "workspace_username": workspace_username,
            "workspace_password": random_password,
            "connection_user": connection.username,
            "connection_password": self.__make_safe_password(connection.password),
            "domain": connection.domain,
            "security_mode": security_mode,
            "connection_name": f"{self.build_id}-{self.connection_ctr}"
        }

        self.logger.debug(f"Prepared Guacamole {protocol} connection to {server_ip}")
        self.connection_ctr += 1
        return connection_dict

    def _resolve_target_ip(
        self,
        connection: HumanInteractionModel,
        server_ip: str,
        ip_aliases: Optional[List[str]]
    ) -> str:
        """Returns the alias IP the connection targets, or server_ip when it has no alias_index."""
        if connection.alias_index is None:
            return server_ip
        aliases = ip_aliases or []
        if connection.alias_index >= len(aliases):
            self.logger.error(
                f"{self.class_name}:{self.build_id} - alias_index {connection.alias_index} is out of range",
                alias_count=len(aliases), nested_guest=connection.nested_guest
            )
            raise ValueError(
                f"alias_index {connection.alias_index} is out of range for {len(aliases)} ip_aliases."
            )
        # Aliases are stored as bare IPs; tolerate a CIDR suffix rather than hand Guacamole an unusable host
        return aliases[connection.alias_index].split('/')[0]

    def get_guac_startup_script(self, connections: List[Dict[str, str]], *, start_nginx: bool = False) -> str:
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
        sql_delimiter = 'AGOGE_GUAC_SQL_' + uuid4().hex
        scale_nginx = 'docker service scale guacamole_nginx=1 || exit 1' if start_nginx else ''
        prepare_swarm = (
            'agoge-prepare-guacamole-swarm "$GUAC_HOST" "$GUAC_DOMAIN" || exit 1'
            if start_nginx else GuacSQL.legacy_swarm_recovery
        )
        reload_nginx = '' if start_nginx else (
            'if [ "$swarm_recovered" = false ]; then '
            'timeout 20s docker service update --detach --force guacamole_nginx >/dev/null || exit 1; fi'
        )
        startup_script = GuacSQL.guac_startup_begin.format(
            guac_host=f'{guac_host}.{guac_domain}' if start_nginx else guac_host,
            guac_domain=guac_domain,
            sql_delimiter=sql_delimiter,
            prepare_swarm=prepare_swarm,
            resume_nginx=scale_nginx,
            reload_nginx=reload_nginx,
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
                    port=conn["port"],
                    connection=connection_name,
                    vnc_password=conn["connection_password"]
                )
            elif protocol == BuildConstants.Guacamole.Protocols.SSH.value:
                startup_script += GuacSQL.guac_startup_ssh.format(
                    ip=conn["ip"],
                    port=conn["port"],
                    connection=connection_name,
                    ssh_username=conn["connection_user"],
                    ssh_password=conn["connection_password"]
                )
            else:
                # Default to RDP
                startup_script += GuacSQL.guac_startup_rdp.format(
                    ip=conn["ip"],
                    port=conn["port"],
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
        startup_script += GuacSQL.guac_startup_end.replace('SQL_DELIMITER', sql_delimiter).replace(
            'GUAC_START_NGINX', scale_nginx,
        )

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
