import subprocess
import textwrap
import socket
import ssl
import sys
import time

from google.api_core.exceptions import Forbidden, NotFound
from google.cloud import compute_v1

from cloud_fn_utilities.globals import BuildConstants
from cloud_fn_utilities.course_objects.compute.factory import ComputeManagerFactory

from common.utilities.gcp.cloud_env import CloudEnv
from common.document_database.factory import DocumentDatabaseFactory
from common.constants.database import DatabaseTypes, DATABASE_NAME, DbCollections
from common.constants.pub_sub import PubSub
from common.constants.build_constants import BuildConstants
from common.models.agoge import AgogeImageModel
from .clean_guacamole_image import publish_clean_guacamole_image


class GuacamoleImageManager:
    """
    Manages the creation and synchronization of Guacamole images and startup configurations.
    """
    BASE_IMAGE = 'image-guac-base'
    IMAGE_WAIT_SECONDS = 15 * 60
    STARTUP_READY_MARKER = 'AGOGE_GUAC_PROJECT_IMAGE_READY'
    STARTUP_FAILURE_HINTS = ('error', 'too many', 'retry after', 'denied', 'unauthorized', 'failed', 'missing')
    COPY_GUAC_BASE = (
        "gcloud compute --project={dst_project} images create image-guac-{dst_project} "
        "--source-image=image-guac-base --source-image-project={src_project}"
    )
    DELETE_IMAGE_COMMAND = "gcloud compute --project={project} images delete image-guac-{project} --quiet"

    # Guacamole VM configuration template (placeholders will be replaced with the project name)
    GUAC_PROJECT_SERVER = {
        "name": "guac-{project}",
        "machine_type": "e2-standard-2",
        "description": "Guacamole proxy server image used for building lab guacamole proxies.",
        "tags": ["http-server"],
        # The capture target. The VM boots from `self_link` (the shared base);
        # naming the base here made the record look like that shared image, so
        # check-out was refused and check-in would have replaced image-guac-base.
        "image": "image-guac-{project}",
        "os": "linux",
        "add_disk": "50",
        "human_interaction": [],
        "status": 0,
        "services": ["guacamole", "certbot", "docker"],
        'metadata': {},
        "dns_record": None,
        "in_use_by": None,
        "base_family": 'ubuntu-2004-lts',
        "state": 1,
        "state_timestamp": None,
        "image_exists": False
    }

    # Dedented bash script template for Guacamole startup. This keeps the script readable and easy to maintain.
    GUAC_PROJECT_SERVER_STARTUP_SCRIPT_TEMPLATE = textwrap.dedent("""\
        #!/bin/bash
        set -e  # Exit immediately if a command fails
        umask 077
        for file in docker-compose.yml initdb.sql nginx/conf.d/guacamole.conf scripts/update-admin-password.sql.template; do
          if [ ! -s "/opt/guacamole/$file" ]; then
            echo "Guacamole base image is missing /opt/guacamole/$file." >&2
            exit 1
          fi
        done
        cd /opt/guacamole
        SQL_FILE=$(mktemp)
        NGINX_OVERRIDE=$(mktemp)
        trap 'rm -f /secrets/dns-google.json "$SQL_FILE" "$NGINX_OVERRIDE"' EXIT
        
        # --------------------------------------------------------------------------------
        # Step 1: Dynamically Set Environment Variables
        # --------------------------------------------------------------------------------
        echo "🔹 Setting environment variables for Guacamole..."
        
        export GUAC_HOST="{guac_host}"
        export GUAC_DOMAIN="{guac_domain}"
        export MYSQL_ROOT_PASSWORD="{guac_sql_root_password}"
        export MYSQL_PASSWORD="{guac_sql_password}"
        export GUAC_ADMIN_PASSWORD="{guac_admin_password}"
        
        mkdir -p /secrets
        install -m 600 /dev/null /secrets/dns-google.json
        cat <<'EOF' > /secrets/dns-google.json
        {google_dns_service_key}
        EOF
        
        # Set strict permissions so only root can read (avoid prying eyes)
        chmod 600 /secrets/dns-google.json
        echo "✅ Created /secrets/dns-google.json with restricted permissions."
        
        {cert_section}
        
        # --------------------------------------------------------------------------------
        # Step 3: Start/Deploy Guacamole (Swarm). Leaving swarm first due to unknown issues
        #       with the initial deployment.
        # --------------------------------------------------------------------------------
        echo "🔹 Deploying Guacamole via Docker Swarm..."
        # Proxy clones need these credentials even if Docker cannot load the captured Swarm.
        install -m 0600 /dev/null /etc/agoge-guacamole-db.env
        printf 'MYSQL_ROOT_PASSWORD=%q\\nMYSQL_PASSWORD=%q\\n' \\
          "$MYSQL_ROOT_PASSWORD" "$MYSQL_PASSWORD" > /etc/agoge-guacamole-db.env
        swarm_state=$(timeout 10s docker info --format '{{{{.Swarm.LocalNodeState}}}}')
        if [ "$swarm_state" != inactive ]; then
          timeout 30s docker swarm leave --force
        fi
        address=$(curl -fsS --max-time 10 -H 'Metadata-Flavor: Google' \\
          http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/ip)
        timeout 45s docker swarm init --advertise-addr "$address"
        # Keep HTTPS closed until the initial admin password is changed.
        cat > "$NGINX_OVERRIDE" <<'NGINX_EOF'
        version: '3.7'
        services:
          nginx:
            deploy:
              replicas: 0
        NGINX_EOF
        timeout 90s docker stack deploy -c docker-compose.yml -c "$NGINX_OVERRIDE" guacamole
        echo "✅ Guacamole stack deployed."
        
        # --------------------------------------------------------------------------------
        # Step 4: Wait for MySQL to be Ready, Then Update guacadmin Password
        # --------------------------------------------------------------------------------
        echo "⏳ Waiting for MySQL (service name: 'db') to be ready in Swarm..."
        
        deadline=$((SECONDS + 360))
        while :; do
          DB_CID=$(timeout 10s docker ps -q --filter label=com.docker.swarm.service.name=guacamole_db | head -n 1)
          if [ -n "$DB_CID" ] && timeout 10s docker exec "$DB_CID" sh -c \\
            'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --connect-timeout=5 --host=127.0.0.1 --user=root guacamole_db -e "SELECT 1 FROM guacamole_user LIMIT 0"' \\
            >/dev/null 2>&1; then
            break
          fi
          if [ "$SECONDS" -ge "$deadline" ]; then
            echo "Guacamole image setup failed to initialize its MySQL schema." >&2
            exit 1
          fi
          sleep 5
        done
        echo "✅ MySQL is ready!"
        
        # Generate final SQL for updating the guacadmin password
        TEMPLATE_FILE="/opt/guacamole/scripts/update-admin-password.sql.template"
        
        echo "🔹 Generating the final SQL to update guacadmin's password..."
        sed "s|REPLACE_ME_PASSWORD|{guac_admin_password}|g" "${{TEMPLATE_FILE}}" > "${{SQL_FILE}}"
        
        echo "🔄 Updating guacadmin password..."
        timeout 60s docker exec -i "$DB_CID" sh -c \\
          'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --user=root guacamole_db' < "$SQL_FILE"
        db_data=$(timeout 10s docker volume inspect --format '{{{{.Mountpoint}}}}' guacamole_db_data)
        if [ -z "$db_data" ] || [ ! -d "$db_data/mysql" ]; then
          echo "Guacamole image setup failed to verify the initialized MySQL volume." >&2
          exit 1
        fi
        if ! timeout 10s docker exec "$DB_CID" sh -c \\
          'MYSQL_PWD="$MYSQL_PASSWORD" exec mysql --connect-timeout=5 --host=127.0.0.1 --user="$MYSQL_USER" guacamole_db -e "SELECT 1 FROM guacamole_user LIMIT 0"' \\
          >/dev/null 2>&1; then
          echo "Guacamole image setup failed to verify the application database login." >&2
          exit 1
        fi
        
        echo "✅ guacadmin password updated successfully."
        
        # --------------------------------------------------------------------------------
        # Step 5: Clean Up Secrets
        # --------------------------------------------------------------------------------
        echo "🔹 Removing sensitive secrets file"
        rm -f /secrets/dns-google.json "$SQL_FILE" "$NGINX_OVERRIDE"
        trap - EXIT
        echo "✅ Secrets have been cleaned up!"
        timeout 60s docker service scale --detach guacamole_nginx=1
        sync
        echo '{ready_marker}'

    """)

    def __init__(self, project):
        """
        Initializes the GuacamoleImageManager with environment and Firestore DB references.
        """
        self.project = project
        self.env = CloudEnv(project=project)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            project_id=self.project
        )

        # Here, we set debug equal to True because the shared resource project does not have cloud functions
        # to pick this up. It must be run locally.
        self.image_manager = ComputeManagerFactory.create_manager_object(
            manager_type=PubSub.CourseObjects.TEMPLATE_SERVER,
            env_dict=self.env.env_dict,
            debug=True
        )

    def create_guac_project_image(self) -> bool:
        """
        Creates or updates the Guacamole project image for the current environment.

        Returns:
            bool: True if the image creation process completes successfully, False otherwise.
        """
        environment = getattr(self.env, 'env_dict', {})
        if environment.get('guacamole_tls_secret'):
            image = environment.get('guacamole_tls_image')
            if image:
                print(f"Managed Guacamole TLS is enabled. Proxies use the configured image {image}.")
            else:
                print("Managed Guacamole TLS is enabled. Existing proxy images remain the migration source. "
                      "Use setup.py guacamole-tls build-image to prepare a clean image.")
            return True

        server_name = f"guac-{self.env.project}"
        # Resolve the source before reading startup secrets or replacing the
        # Firestore record. A record in Firestore does not create a GCE image.
        source_image = self._resolve_base_image()

        # 1. Replace placeholders and store the updated image record in the DB
        print(f"📥 Importing server image '{server_name}' into Firestore...")
        server_record = self._replace_project_variable(self.GUAC_PROJECT_SERVER)
        server_record['self_link'] = source_image
        server_record['startup_script'] = self._get_guac_startup_script()
        validated = AgogeImageModel(**server_record)
        self.db.insert(collection_name=DbCollections.IMAGE, data=validated.model_dump(), id_field="name")
        print(f"✅ Server image '{server_name}' imported successfully.")

        # 2. Check out the server, which will also request the new certificate, and then check the server back in.
        print("🚀 Deploying Guacamole server for initial setup and certificate provisioning...")
        self.image_manager.load(server_name=server_name)
        self.image_manager.check_out()

        # Nginx can present a valid certificate before the proxy database is usable.
        print("🔍 Waiting for the Guacamole database, startup cleanup, and wildcard SSL certificate...")
        deadline = time.monotonic() + self.IMAGE_WAIT_SECONDS
        while True:
            ready, failure = self._startup_status()
            if failure is not None:
                print(f"❌ The Guacamole server's startup script failed:\n{failure}\n"
                      f"The server '{server_name}' stays checked out and was NOT captured; fix the cause "
                      "and rerun this option.")
                return False
            if ready and self._verify_certificate_operation():
                break
            if time.monotonic() >= deadline:
                pending = 'wildcard certificate verification' if ready else 'Guacamole database setup and startup cleanup'
                print(f"❌ Timed out waiting for {pending} after {self.IMAGE_WAIT_SECONDS // 60} minutes. "
                      f"The server '{server_name}' stays checked out and was NOT captured; inspect it with "
                      "'sudo journalctl -u google-startup-scripts.service' and rerun this option.")
                return False
            time.sleep(15)

        print("🔄 Checking Guacamole server back in...")
        self.image_manager.check_in()
        print("🎉 Guacamole project image setup completed successfully.")

        return True

    def create_guac_tls_image(self, image_name: str | None = None) -> str:
        """Prepare an opt-in proxy image without any Let’s Encrypt material."""
        return publish_clean_guacamole_image(
            self.project,
            self.env.zone,
            self._resolve_base_image(),
            image_name or f'image-guac-tls-{self.project}',
        )

    def _resolve_base_image(self) -> str:
        source_project = (
            self.env.default_server_image_project
            or self.env.parent_project
            or self.env.project
        )
        image_name = self.BASE_IMAGE
        resource = f'projects/{source_project}/global/images/{image_name}'
        try:
            image = compute_v1.ImagesClient().get(project=source_project, image=image_name)
        except NotFound as error:
            raise RuntimeError(
                f'Guacamole base image {resource} was not found. '
                'Create the base image in the configured image project or correct '
                'default_server_image_project before retrying.'
            ) from error
        except Forbidden as error:
            raise RuntimeError(
                f'Cannot access Guacamole base image {resource}. '
                'The account running setup needs access to this image.'
            ) from error
        if image.status != 'READY' or not image.self_link:
            raise RuntimeError(f'Guacamole base image {resource} is not ready (status: {image.status}).')
        print(f'Using Guacamole base image: {image.self_link}')
        return image.self_link

    def _verify_certificate_operation(self) -> bool:
        """True once the server presents a trusted certificate that also covers lab proxy hosts."""
        # Template DNS names are fully qualified (trailing dot); TLS name checks are not.
        dns_entry = self.image_manager.dns_record.rstrip('.')
        wildcard = '*.' + (self.env.parent_dns_suffix or self.env.dns_suffix).strip('.')
        try:
            context = ssl.create_default_context()
            with socket.create_connection((dns_entry, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=dns_entry) as ssock:
                    cert = ssock.getpeercert()
        except (OSError, ssl.SSLError):
            return False
        names = {value for kind, value in cert.get('subjectAltName', ()) if kind == 'DNS'}
        if wildcard not in names:
            print(f"⚠️ The certificate at {dns_entry} does not cover {wildcard}.")
            return False
        print("✅ SSL certificate verified successfully.")
        return True

    def _startup_status(self) -> tuple[bool, str | None]:
        """Read readiness or failure from the current boot of the template VM."""
        try:
            output = compute_v1.InstancesClient().get_serial_port_output(
                project=self.env.project, zone=self.image_manager.server_zone or self.env.zone,
                instance=self.image_manager.server_name,
            ).contents
        except Exception:
            # Serial output is a diagnostic; without it, fall back to the deadline.
            return False, None
        # A rerun can reuse the instance, so only the latest boot counts.
        boot = output.rsplit('Starting startup scripts', 1)[-1]
        # Each line appears twice (console and journal); the script never echoes its secrets.
        lines = list(dict.fromkeys(
            line.split('startup-script: ', 1)[1].strip()
            for line in boot.splitlines() if 'startup-script: ' in line
        ))
        if 'Script "startup-script" failed' in boot:
            reasons = [line for line in lines if any(hint in line.lower() for hint in self.STARTUP_FAILURE_HINTS)]
            return False, '\n'.join(f'   {line}' for line in (reasons or lines[-5:]))
        if self.STARTUP_READY_MARKER in lines:
            return True, None
        if 'Finished running startup scripts' in boot:
            return False, '   The startup script finished without confirming image readiness. Check the builder VM startup script.'
        return False, None

    def _get_guac_startup_script(self) -> str:
        """
        Returns a properly formatted startup script for the Guacamole server,
        replacing placeholders with the provided host and domain. It also prompts the user
        to determine if the SSL certificate should be renewed now.

        Returns:
            str: The final bash script with placeholders replaced by actual values.
        """
        base_guac_domain = (self.env.parent_dns_suffix or self.env.dns_suffix).strip('.')
        raw_cert_section = textwrap.dedent("""\
            # ------------------------------------------------------------------------------
            # Step 2: Obtain Wildcard SSL Certificate
            # ------------------------------------------------------------------------------
            echo "🔹 Obtaining wildcard SSL certificate for *.{guac_domain}"
            certbot certonly \\
              --dns-google \\
              --dns-google-credentials /secrets/dns-google.json \\
              --dns-google-propagation-seconds 60 \\
              -d "*.{guac_domain}" -d "{guac_domain}" \\
              --email {admin_email} \\
              --agree-tos \\
              --no-eff-email \\
              --non-interactive

            echo "✅ SSL certificate obtained successfully!"
        """)
        cert_section = raw_cert_section.format(guac_domain=base_guac_domain, admin_email=self.env.admin_email)

        try:
            startup_script = self.GUAC_PROJECT_SERVER_STARTUP_SCRIPT_TEMPLATE.format(
                guac_host=f"guac.{base_guac_domain}",
                guac_domain=base_guac_domain,
                guac_sql_root_password=self.env.guac_sql_root_password,
                guac_sql_password=self.env.guac_sql_password,
                guac_admin_password=self.env.guac_admin_password,
                google_dns_service_key=self.env.google_dns_service_key,
                cert_section=cert_section,
                ready_marker=self.STARTUP_READY_MARKER,
            )
        except KeyError as e:
            print(f"A KeyError occurred, missing environment variable: {e}")
            sys.exit(1)
        return startup_script

    def _replace_project_variable(self, config):
        """
        Recursively replaces occurrences of "{project}" in all string values in
        the provided configuration with the current environment's project name.

        Args:
            config (dict | list | str): The configuration data.

        Returns:
            (dict | list | str): The updated configuration with placeholders replaced.
        """
        if isinstance(config, dict):
            return {k: self._replace_project_variable(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_project_variable(item) for item in config]
        elif isinstance(config, str):
            return config.replace("{project}", self.env.project)
        return config
