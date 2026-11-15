"""Build a Guacamole image whose production TLS key is acquired only by lab VMs."""

import re
import time
from uuid import uuid4

from google.api_core.exceptions import Conflict, NotFound
from google.cloud import compute_v1

LABEL = 'agoge-guacamole-tls'
OPERATION_TIMEOUT = 300
BOOTSTRAP_TIMEOUT = 600

# Standalone Guacamole clones need the JDBC stack and its local DB volume.
# Reinitialize a copied Swarm when its advertise address or certificate is stale.
PREPARE_SWARM = r'''#!/bin/bash
set -euo pipefail

export GUAC_HOST="$1" GUAC_DOMAIN="$2"
if [[ ! "$GUAC_HOST" =~ ^[a-z0-9.-]+$ || ! "$GUAC_DOMAIN" =~ ^[a-z0-9.-]+$ ]]; then
    exit 1
fi
systemctl start docker
address="$(curl -fsS --max-time 10 -H 'Metadata-Flavor: Google' \
    http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/ip)"
if [[ "$(docker info --format '{{.Swarm.LocalNodeState}}/{{.Swarm.NodeAddr}}')" == "active/$address" ]] \
    && docker service inspect guacamole_db guacamole_nginx >/dev/null 2>&1; then
    exit 0
fi

if [[ "$(docker info --format '{{.Swarm.LocalNodeState}}')" != 'inactive' ]]; then
    docker swarm leave --force >/dev/null
fi
docker swarm init --advertise-addr "$address" >/dev/null
set -a
source /etc/agoge-guacamole-db.env
set +a
cd /opt/guacamole
# The lab startup script exposes HTTPS only after configuring its SQL users.
docker stack deploy -c docker-compose.yml -c /etc/agoge-guacamole-nginx-disabled.yml guacamole
'''

BUILDER_SCRIPT = r'''#!/bin/bash
set -euo pipefail
umask 077

# The source must be a pristine image-guac-base. Refuse an image with an old
# ACME account, wildcard key, or a preinstalled managed-certificate agent.
for directory in /etc/letsencrypt/{live,archive,accounts,renewal,keys}; do
    if [[ -L /etc/letsencrypt || -L "$directory" ]] || \
        { [[ -d "$directory" ]] && [[ -n "$(find "$directory" -mindepth 1 -print -quit)" ]]; }; then
        echo 'The Guacamole base image already contains TLS material.'
        exit 1
    fi
done
if [[ -e /secrets/dns-google.json || -e /etc/agoge-guacamole-tls || -e /etc/guac_init_done ]]; then
    echo 'The Guacamole base image already carries project-specific state.'
    exit 1
fi

test -s /opt/guacamole/docker-compose.yml
test -s /opt/guacamole/initdb.sql
install -d -m 0700 /etc/letsencrypt
cat >/usr/local/sbin/agoge-prepare-guacamole-swarm <<'AGOGE_SWARM_EOF'
@@PREPARE_SWARM@@
AGOGE_SWARM_EOF
chmod 0755 /usr/local/sbin/agoge-prepare-guacamole-swarm

if [[ ! -s /etc/agoge-guacamole-db.env ]]; then
    printf 'MYSQL_ROOT_PASSWORD=%s\nMYSQL_PASSWORD=%s\n' \
        "$(openssl rand -hex 24)" "$(openssl rand -hex 24)" > /etc/agoge-guacamole-db.env
fi
cat >/etc/agoge-guacamole-nginx-disabled.yml <<'AGOGE_NGINX_EOF'
version: '3.7'
services:
  nginx:
    deploy:
      replicas: 0
AGOGE_NGINX_EOF

if systemctl cat guacamole.service >/dev/null 2>&1; then
    systemctl disable --now guacamole.service
fi
/usr/local/sbin/agoge-prepare-guacamole-swarm guacamole-image-build.invalid invalid

deadline=$((SECONDS + 420))
while ((SECONDS < deadline)); do
    db_container="$(docker ps -q --filter label=com.docker.swarm.service.name=guacamole_db | head -n 1)"
    if [[ -n "$db_container" ]] && disabled="$(docker exec -i "$db_container" sh -c \
        'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --user=root --batch --skip-column-names guacamole_db' \
        2>/dev/null <<'AGOGE_SQL_EOF'
UPDATE guacamole_user SET disabled = 1 WHERE entity_id = (
    SELECT entity_id FROM guacamole_entity WHERE name = 'guacadmin' AND type = 'USER'
);
SELECT disabled FROM guacamole_user JOIN guacamole_entity USING (entity_id)
    WHERE name = 'guacadmin' AND type = 'USER';
AGOGE_SQL_EOF
    )" && [[ "$disabled" == 1 ]]; then
        sync
        echo '@@READY@@'
        exit 0
    fi
    sleep 5
done
echo 'The Guacamole image database did not become ready.'
exit 1
'''


def publish_clean_guacamole_image(project: str, zone: str, source_image: str, image_name: str) -> str:
    """Publish a new immutable image. Repeat calls return an existing verified result."""
    if not re.fullmatch(r'image-guac-tls-[a-z0-9](?:[a-z0-9-]{0,46}[a-z0-9])?', image_name):
        raise ValueError('Use a GCE image name beginning with image-guac-tls- (at most 63 characters).')

    images = compute_v1.ImagesClient()
    if existing := _existing_image(images, project, image_name):
        return existing

    identifier = uuid4().hex
    name = f'guac-tls-build-{identifier[:16]}'
    ready = f'AGOGE_GUAC_TLS_IMAGE_READY_{identifier}'
    startup = BUILDER_SCRIPT.replace('@@PREPARE_SWARM@@', PREPARE_SWARM.rstrip()).replace('@@READY@@', ready)
    instances = compute_v1.InstancesClient()
    instance = compute_v1.Instance(
        name=name,
        machine_type=f'zones/{zone}/machineTypes/e2-standard-2',
        disks=[compute_v1.AttachedDisk(
            boot=True, auto_delete=True, initialize_params=compute_v1.AttachedDiskInitializeParams(
                source_image=source_image, disk_type=f'zones/{zone}/diskTypes/pd-balanced',
            ),
        )],
        network_interfaces=[compute_v1.NetworkInterface(
            network=f'projects/{project}/global/networks/default',
            access_configs=[compute_v1.AccessConfig(name='External NAT', type_='ONE_TO_ONE_NAT')],
        )],
        service_accounts=[],
        metadata=compute_v1.Metadata(items=[
            compute_v1.Items(key='block-project-ssh-keys', value='TRUE'),
            compute_v1.Items(key='startup-script', value=startup),
        ]),
    )
    try:
        print(f'Starting temporary Guacamole image builder {name} in {project}/{zone}.', flush=True)
        instances.insert(project=project, zone=zone, instance_resource=instance).result(timeout=OPERATION_TIMEOUT)
        _wait_for_builder(instances, project, zone, name, ready)
        instances.stop(project=project, zone=zone, instance=name).result(timeout=OPERATION_TIMEOUT)
        stopped = instances.get(project=project, zone=zone, instance=name)
        boot_disk = next((disk.source for disk in stopped.disks if disk.boot), None)
        if stopped.status != 'TERMINATED' or not boot_disk:
            raise RuntimeError(f'Cannot capture the boot disk from stopped builder {name}.')
        image = compute_v1.Image(
            name=image_name, source_disk=boot_disk, labels={LABEL: 'enabled'},
            description='Agoge Guacamole JDBC image initialized without any TLS certificate or key.',
        )
        try:
            images.insert(project=project, image_resource=image).result(timeout=OPERATION_TIMEOUT)
        except Conflict:
            # Concurrent builders can only add an image, never overwrite one.
            if existing := _existing_image(images, project, image_name):
                return existing
            raise
        if existing := _existing_image(images, project, image_name):
            return existing
        raise RuntimeError(f'Compute Engine did not return the new image {image_name}.')
    finally:
        try:
            instances.delete(project=project, zone=zone, instance=name).result(timeout=OPERATION_TIMEOUT)
        except NotFound:
            pass
        except Exception:
            print(f'Could not delete temporary builder {name} in {project}/{zone}. Check and remove it manually.')


def _existing_image(images, project, image_name):
    try:
        image = images.get(project=project, image=image_name)
    except NotFound:
        return None
    if image.labels.get(LABEL) != 'enabled':
        raise RuntimeError(f'An unrelated image already uses {image_name}. Choose a new image name.')
    if image.status != 'READY' or not image.self_link:
        raise RuntimeError(f'The image {image_name} is not ready. Retry after the image finishes.')
    return image.self_link


def _wait_for_builder(instances, project, zone, name, ready):
    deadline = time.monotonic() + BOOTSTRAP_TIMEOUT
    while time.monotonic() < deadline:
        output = instances.get_serial_port_output(project=project, zone=zone, instance=name).contents
        boot = output.rsplit('Starting startup scripts', 1)[-1]
        if any(f'startup-script: {ready}' in line for line in boot.splitlines()):
            return
        if 'Script "startup-script" failed with error' in boot:
            for reason in (
                'The Guacamole base image already contains TLS material.',
                'The Guacamole base image already carries project-specific state.',
                'The Guacamole image database did not become ready.',
            ):
                if reason in boot:
                    raise RuntimeError(reason)
            raise RuntimeError(
                f'The Guacamole image builder {name} failed startup. Verify Docker and the base image files.'
            )
        time.sleep(10)
    raise TimeoutError(f'Timed out waiting for Guacamole image builder {name}.')
