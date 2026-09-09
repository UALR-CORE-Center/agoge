import subprocess
import textwrap
import socket
import ssl
import sys
import time
from datetime import datetime, UTC

from cloud_fn_utilities.globals import BuildConstants
from cloud_fn_utilities.course_objects.compute.factory import ComputeManagerFactory

from common.utilities.gcp.cloud_env import CloudEnv
from common.document_database.factory import DocumentDatabaseFactory
from common.constants.database import DatabaseTypes, DATABASE_NAME, DbCollections
from common.constants.pub_sub import PubSub
from common.constants.build_constants import BuildConstants
from common.models.agoge import AgogeImageModel


class GuacamoleImageManager:
    """
    Manages the creation and synchronization of Guacamole images and startup configurations.
    """
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
        "image": "image-guac-base",
        "os": "linux",
        "add_disk": "50",
        "human_interaction": [],
        "status": 0,
        "services": ["guacamole", "certbot", "docker"],
        "self_link": "https://www.googleapis.com/compute/v1/projects/{project}/global/images/image-guac-base",
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
        cat <<EOF > /secrets/dns-google.json
        {google_dns_service_key}
        EOF
        
        # Set strict permissions so only root can read (avoid prying eyes)
        chmod 644 /secrets/dns-google.json
        echo "✅ Created /secrets/dns-google.json with restricted permissions."
        
        {cert_section}
        
        # --------------------------------------------------------------------------------
        # Step 3: Start/Deploy Guacamole (Swarm). Leaving swarm first due to unknown issues
        #       with the initial deployment.
        # --------------------------------------------------------------------------------
        echo "🔹 Deploying Guacamole via Docker Swarm..."
        sudo docker swarm leave --force
        sudo docker swarm init --advertise-addr $(hostname -I | awk '{{print $1}}')
        docker stack deploy -c /opt/guacamole/docker-compose.yml guacamole
        echo "✅ Guacamole stack deployed."
        
        # --------------------------------------------------------------------------------
        # Step 4: Wait for MySQL to be Ready, Then Update guacadmin Password
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
        
        # Generate final SQL for updating the guacadmin password
        TEMPLATE_FILE="/opt/guacamole/scripts/update-admin-password.sql.template"
        SQL_FILE="/opt/guacamole/scripts/update-admin-password.sql"
        
        echo "🔹 Generating the final SQL to update guacadmin's password..."
        sed "s|REPLACE_ME_PASSWORD|{guac_admin_password}|g" "${{TEMPLATE_FILE}}" > "${{SQL_FILE}}"
        
        echo "🔄 Updating guacadmin password..."
        docker run --rm --network guacamole_guacnet \
          -v "${{SQL_FILE}}:/update-admin-password.sql" \
          mysql:8.0 \
          sh -c "mysql -h 'db' -u root -p"{guac_sql_root_password}" guacamole_db < /update-admin-password.sql"
        
        echo "✅ guacadmin password updated successfully."
        
        # --------------------------------------------------------------------------------
        # Step 5: Clean Up Secrets
        # --------------------------------------------------------------------------------
        echo "🔹 Removing sensitive secrets file"
        rm -f /secrets/dns-google.json
        echo "✅ Secrets have been cleaned up!"

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
        server_name = f"guac-{self.env.project}"

        # 1. Replace placeholders and store the updated image record in the DB
        print(f"📥 Importing server image '{server_name}' into Firestore...")
        server_record = self._replace_project_variable(self.GUAC_PROJECT_SERVER)
        server_record['startup_script'] = self._get_guac_startup_script()
        validated = AgogeImageModel(**server_record)
        self.db.insert(collection_name=DbCollections.IMAGE, data=validated.model_dump(), id_field="name")
        print(f"✅ Server image '{server_name}' imported successfully.")

        # 2. Check out the server, which will also request the new certificate, and then check the server back in.
        print("🚀 Deploying Guacamole server for initial setup and certificate provisioning...")
        self.image_manager.load(server_name=server_name)
        self.image_manager.check_out()
        time.sleep(120)

        print("🔍 Verifying SSL certificate for the Guacamole server...")
        self._verify_certificate_operation()

        print("🔄 Checking Guacamole server back in...")
        self.image_manager.check_in()
        print("🎉 Guacamole project image setup completed successfully.")

        return True

    def _verify_certificate_operation(self):
        dns_entry = self.image_manager.dns_record
        try:
            context = ssl.create_default_context()
            with socket.create_connection((dns_entry, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=dns_entry) as ssock:
                    cert = ssock.getpeercert()
            issued_date = datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z').date()
            if issued_date == datetime.now(UTC).date():
                print("✅ SSL certificate verified successfully.")
            else:
                print("⚠️ Certificate date mismatch.")
        except Exception as e:
            print(f"⚠️ SSL verification error for {dns_entry}: {e}")
            input(f"🔎 Verify manually at https://{dns_entry} and press Enter to continue.")

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
                cert_section=cert_section
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
