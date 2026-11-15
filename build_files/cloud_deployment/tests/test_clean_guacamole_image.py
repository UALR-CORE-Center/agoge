import subprocess
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import NotFound
from google.cloud import compute_v1

from cloud_deployment.operations.guacamole_image_management import clean_guacamole_image as clean

PROJECT = 'tenant-project'
ZONE = 'us-central1-a'
BASE = 'projects/base-images/global/images/image-guac-base'
NAME = 'image-guac-tls-tenant-project'
TARGET = f'projects/{PROJECT}/global/images/{NAME}'


@pytest.fixture
def clients(monkeypatch):
    images = Mock()
    instances = Mock()
    monkeypatch.setattr(clean.compute_v1, 'ImagesClient', lambda: images)
    monkeypatch.setattr(clean.compute_v1, 'InstancesClient', lambda: instances)
    return images, instances


def test_publish_waits_for_safe_guest_bootstrap_and_stops_before_capture(clients):
    images, instances = clients
    image_ready = compute_v1.Image(status='READY', self_link=TARGET, labels={clean.LABEL: 'enabled'})
    images.get.side_effect = [NotFound('new image'), image_ready]
    disk = f'projects/{PROJECT}/zones/{ZONE}/disks/builder-boot'
    instances.get.return_value = compute_v1.Instance(
        status='TERMINATED', disks=[compute_v1.AttachedDisk(boot=True, source=disk)],
    )
    order = []

    def read_serial(**kwargs):
        resource = instances.insert.call_args.kwargs['instance_resource']
        scripts = [item.value for item in resource.metadata.items if item.key == 'startup-script']
        marker = next(line.split("'")[1] for line in scripts[0].splitlines() if 'AGOGE_GUAC_TLS_IMAGE_READY_' in line)
        return compute_v1.SerialPortOutput(contents=f'\nstartup-script: {marker}\n')

    instances.get_serial_port_output.side_effect = read_serial
    instances.stop.return_value.result.side_effect = lambda **_: order.append('stop')
    images.insert.return_value.result.side_effect = lambda **_: order.append('capture')
    instances.delete.return_value.result.side_effect = lambda **_: order.append('delete builder')

    assert clean.publish_clean_guacamole_image(PROJECT, ZONE, BASE, NAME) == TARGET
    assert order == ['stop', 'capture', 'delete builder']
    builder = instances.insert.call_args.kwargs['instance_resource']
    assert not builder.service_accounts
    assert builder.disks[0].initialize_params.source_image == BASE
    assert builder.disks[0].auto_delete is True
    image = images.insert.call_args.kwargs['image_resource']
    assert image.name == NAME
    assert image.source_disk == disk
    assert image.labels == {clean.LABEL: 'enabled'}


def test_builder_failure_does_not_publish_an_image(clients):
    images, instances = clients
    images.get.side_effect = NotFound('new image')
    instances.get_serial_port_output.return_value = compute_v1.SerialPortOutput(contents=(
        'startup-script: The Guacamole base image already contains TLS material.\n'
        'Script "startup-script" failed with error: exit status 1'
    ))
    with pytest.raises(RuntimeError, match='already contains TLS material'):
        clean.publish_clean_guacamole_image(PROJECT, ZONE, BASE, NAME)
    images.insert.assert_not_called()
    instances.delete.assert_called_once()


def test_verified_image_can_be_reused_but_unrelated_image_is_never_replaced(clients):
    images, instances = clients
    images.get.return_value = compute_v1.Image(
        status='READY', self_link=TARGET, labels={clean.LABEL: 'enabled'},
    )
    assert clean.publish_clean_guacamole_image(PROJECT, ZONE, BASE, NAME) == TARGET
    images.get.return_value = compute_v1.Image(status='READY', self_link=TARGET)
    with pytest.raises(RuntimeError, match='unrelated image'):
        clean.publish_clean_guacamole_image(PROJECT, ZONE, BASE, NAME)
    images.insert.assert_not_called()
    instances.insert.assert_not_called()


def test_bash_bootstrap_syntax_and_key_free_image_invariants():
    assert 'replicas: 0' in clean.BUILDER_SCRIPT
    assert 'SET disabled = 1' in clean.BUILDER_SCRIPT
    assert 'certbot ' not in clean.BUILDER_SCRIPT
    assert 'secretmanager.googleapis.com' not in clean.BUILDER_SCRIPT + clean.PREPARE_SWARM
    rendered = clean.BUILDER_SCRIPT.replace('@@PREPARE_SWARM@@', clean.PREPARE_SWARM.rstrip())
    for script in (rendered, clean.PREPARE_SWARM):
        subprocess.run(['bash', '-n'], input=script, text=True, check=True)
