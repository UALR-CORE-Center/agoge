import subprocess
import textwrap
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import ConnectTimeout

from common.models.agoge import HumanInteractionModel, NicModel, ServerModel
from cloud_fn_utilities.course_objects.compute.base_compute_manager import BaseComputeManager
from cloud_fn_utilities.server_specific.guacamole.display_proxy import DisplayProxy
from cloud_fn_utilities.server_specific.guacamole.guacamole_configuration import GuacamoleConfiguration

GUAC = 'cloud_fn_utilities.server_specific.guacamole.guacamole_configuration'
PROXY = 'cloud_fn_utilities.server_specific.guacamole.display_proxy'
ALIASES = ['10.1.1.20', '10.1.1.21']


@pytest.fixture
def guac():
    with patch(f'{GUAC}.CloudEnv') as cloud_env, patch(f'{GUAC}.Logger'):
        cloud_env.return_value.parent_dns_suffix = '.example.com'
        yield GuacamoleConfiguration('abcdefghij', env_dict={'x': 1})


def _rdp_alias():
    return HumanInteractionModel(display=True, protocol='rdp', username='admin', password='pw',
                                 nested_guest='dc01', alias_index=1)


def _vnc_console():
    return HumanInteractionModel(display=True, protocol='vnc', password='vncpass', nested_guest='ws01', port=5903)


def _ordinary_ssh():
    return HumanInteractionModel(display=True, protocol='ssh', username='kali', password='pw')


def test_alias_target_connects_to_the_alias_ip(guac):
    conn = guac.prepare_guac_connection(_rdp_alias(), server_ip='10.1.1.10', ip_aliases=ALIASES)

    assert (conn['ip'], conn['port']) == ('10.1.1.21', '3389')
    script = guac.get_guac_startup_script([conn])
    assert "'hostname', '10.1.1.21'" in script
    assert "'port', '3389'" in script


def test_alias_with_a_cidr_suffix_uses_the_bare_address(guac):
    connection = _rdp_alias()
    conn = guac.prepare_guac_connection(connection, server_ip='10.1.1.10', ip_aliases=['10.1.1.20/32', '10.1.1.21/32'])

    assert conn['ip'] == '10.1.1.21'


def test_console_target_keeps_the_parent_ip_and_overrides_the_port(guac):
    conn = guac.prepare_guac_connection(_vnc_console(), server_ip='10.1.1.10', ip_aliases=ALIASES)

    assert (conn['ip'], conn['port']) == ('10.1.1.10', '5903')
    script = guac.get_guac_startup_script([conn])
    assert "'hostname', '10.1.1.10'" in script
    assert "'port', '5903'" in script
    assert "'port', '5901'" not in script


@pytest.mark.parametrize('protocol, port', [('ssh', '22'), ('vnc', '5901'), ('rdp', '3389')])
def test_ordinary_target_is_unchanged(guac, protocol, port):
    connection = HumanInteractionModel(display=True, protocol=protocol, username='u', password='pw')
    conn = guac.prepare_guac_connection(connection, server_ip='10.1.1.10')

    assert (conn['ip'], conn['port']) == ('10.1.1.10', port)
    assert f"'port', '{port}'" in guac.get_guac_startup_script([conn])


def test_out_of_range_alias_index_raises(guac):
    with pytest.raises(ValueError, match='alias_index 1 is out of range'):
        guac.prepare_guac_connection(_rdp_alias(), server_ip='10.1.1.10', ip_aliases=['10.1.1.20'])


@pytest.mark.parametrize('managed_tls', [False, True])
def test_display_proxy_records_the_resolved_target_per_connection(managed_tls):
    server = ServerModel(
        name='ad-lab-host',
        image='image-ad-lab-host',
        machine_type='n2-standard-8',
        nics=[NicModel(network='lab', internal_ip='10.1.1.10', ip_aliases=ALIASES)],
        human_interaction=[_rdp_alias(), _vnc_console(), _ordinary_ssh()],
    )
    build_model = SimpleNamespace(servers=[server], firewalls=False, build_type='unit', networks=[])
    with patch(f'{PROXY}.CloudEnv') as cloud_env, patch(f'{PROXY}.Logger'), \
            patch(f'{PROXY}.DocumentDatabaseFactory') as db_factory, patch(f'{PROXY}.DatabaseMask'), \
            patch(f'{PROXY}.ComputeManagerFactory'), patch(f'{GUAC}.CloudEnv') as guac_env, patch(f'{GUAC}.Logger'):
        cloud_env.return_value.main_app_url = 'app.example.com'
        cloud_env.return_value.parent_dns_suffix = '.example.com'
        cloud_env.return_value.project = 'tenant-project'
        tls_secret = 'projects/shared-project/secrets/tls'
        tls_image = 'projects/tenant-project/global/images/guacamole-clean'
        cloud_env.return_value.get_env.return_value = {
            'guacamole_tls_secret': tls_secret, 'guacamole_tls_image': tls_image,
        } if managed_tls else {}
        guac_env.return_value.parent_dns_suffix = '.example.com'
        db = db_factory.create_db_object.return_value
        proxy = DisplayProxy('abcdefghij', build_model, env_dict={'x': 1})
        # The build record is only re-saved with proxy_connections; keep the real model out of it
        proxy.model = MagicMock()
        record = proxy.model.return_value

        server_record = proxy.prepare_server_record()

    targets = {c.internal_ip_address for c in record.proxy_connections}
    assert targets == {'10.1.1.21', '10.1.1.10'}
    assert len(record.proxy_connections) == 3
    script = server_record['guacamole_startup_script']
    assert "'hostname', '10.1.1.21'" in script
    assert "'port', '5903'" in script
    assert "'port', '22'" in script
    assert db.update.call_count == 2
    assert ('BEGIN AGOGE GUACAMOLE TLS' in script) == managed_tls
    if managed_tls:
        assert server_record['image'] == tls_image
        assert server_record['metadata']['agoge-guacamole-tls-secret'] == tls_secret
        assert server_record['service_accounts'] == [{
            'email': 'agoge-guac-tls@tenant-project.iam.gserviceaccount.com',
            'scopes': ['https://www.googleapis.com/auth/cloud-platform'],
        }]
        assert script.index('BEGIN AGOGE GUACAMOLE TLS') < script.index('agoge-prepare-guacamole-swarm')
        assert 'docker service scale guacamole_nginx=1' in script
    else:
        assert server_record['image'] == 'projects/tenant-project/global/images/image-guac-tenant-project'


@pytest.mark.parametrize('stored_image, expected_image', [
    ('image-guac-agoge-shared-resources',
     'projects/test-dev-787001/global/images/image-guac-test-dev-787001'),
    ('projects/shared-images/global/images/image-guac-tls-shared-images',
     'projects/shared-images/global/images/image-guac-tls-shared-images'),
])
def test_rebuild_display_proxy_uses_tenant_or_explicit_boot_image(stored_image, expected_image):
    manager = object.__new__(BaseComputeManager)
    manager.project = 'test-dev-787001'
    manager.env = SimpleNamespace(project=manager.project, zone='us-central1-a')
    manager.parent_build_id = 'abcdefghij'
    manager.server_name = f'{manager.parent_build_id}-display-guacamole-server'
    manager.server_spec = SimpleNamespace(image=stored_image, guacamole_startup_script='#!/bin/bash')
    manager.compute_image = MagicMock()

    disk = manager._get_boot_disk()

    assert disk.initialize_params.source_image == expected_image
    manager.compute_image.get.assert_not_called()


@pytest.fixture
def legacy_startup(guac, tmp_path):
    app_dir = tmp_path / 'guacamole'
    app_dir.mkdir()
    (app_dir / 'docker-compose.yml').write_text('Guacamole stack file from project image\n')
    (tmp_path / 'db_data' / 'mysql').mkdir(parents=True)
    stubs = textwrap.dedent(r"""
        timeout() { shift; "$@"; }
        curl() { echo '10.0.0.3'; }
        sleep() { SECONDS=$((SECONDS + 181)); }
        docker() {
          printf '%s\n' "$*" >> "$TEST_WORKDIR/docker-calls.log"
          case "$1 $2" in
            'info --format')
              if [ -f "$TEST_WORKDIR/left" ]; then echo 'inactive/false//0'; else echo "$TEST_SWARM"; fi ;;
            'node inspect') echo 'ready' ;;
            'service inspect')
              if [ "$4" = --format ]; then return 1; fi
              test "$TEST_STACK_DEPLOYED" = yes ;;
            'volume inspect') echo "$TEST_WORKDIR/db_data" ;;
            'ps -aq')
              if [ "$TEST_IMAGE_CREDENTIALS" = yes ] && [ ! -f "$TEST_WORKDIR/left" ]; then
                printf '%s\n' 'old-mysql-task' 'older-mysql-task'
              fi ;;
            'inspect --type')
              [ "$6" = old-mysql-task ] || return 1
              printf '%s\n' 'OTHER=unused' 'MYSQL_ROOT_PASSWORD=test=Root!' 'MYSQL_PASSWORD=test Pass$'
              ;;
            'swarm leave') touch "$TEST_WORKDIR/left" ;;
            'swarm init')
              [ "$3" != --force-new-cluster ] || { echo 'This node is not a swarm manager.' >&2; return 1; }
              test "$TEST_SWARM_INIT" = yes ;;
            'ps -q')
              case "$4" in
                'label=com.docker.stack.namespace=guacamole') echo 'orphan-task' ;;
                'label=com.docker.swarm.service.name=guacamole_db') echo 'mysql-task' ;;
                *) return 1 ;;
              esac ;;
            'stop orphan-task'|'service update') return 0 ;;
            'stack deploy')
              [ "$PWD" = "$TEST_WORKDIR/guacamole" ] && [ -f docker-compose.yml ] &&
                [ "$MYSQL_ROOT_PASSWORD" = 'test=Root!' ] && [ "$MYSQL_PASSWORD" = 'test Pass$' ] ;;
            'exec mysql-task') test "$TEST_DATABASE_READY" = yes ;;
            'exec -i') cat > applied.sql ;;
            *) return 1 ;;
          esac
        }
    """)
    script = guac.get_guac_startup_script([guac.prepare_guac_connection(_ordinary_ssh(), server_ip='10.0.0.4')])
    script = script.replace('/etc/guac_init_done', 'guac_init_done')
    script = script.replace('/etc/agoge-guacamole-db.env', 'db.env')
    script = script.replace('/run/agoge-guacamole-startup.lock', 'startup.lock')
    script = script.replace('/opt/guacamole/scripts/create_guacamole_user_connections.sql', 'connections.sql')
    script = script.replace('/opt/guacamole', str(app_dir))

    def run(swarm, *, stack_deployed=True, database_ready=True, image_credentials=True, swarm_init=True):
        log_path = tmp_path / 'docker-calls.log'
        log_path.unlink(missing_ok=True)
        completed = subprocess.run(
            ['bash', '-s'], input=stubs + script, cwd=tmp_path, text=True, capture_output=True, timeout=5,
            env={
                'TEST_WORKDIR': str(tmp_path), 'TEST_SWARM': swarm,
                'TEST_STACK_DEPLOYED': 'yes' if stack_deployed else 'no',
                'TEST_DATABASE_READY': 'yes' if database_ready else 'no',
                'TEST_IMAGE_CREDENTIALS': 'yes' if image_credentials else 'no',
                'TEST_SWARM_INIT': 'yes' if swarm_init else 'no',
            },
        )
        assert 'test=Root!' not in completed.stdout + completed.stderr
        assert 'test Pass$' not in completed.stdout + completed.stderr
        return completed, log_path.read_text().splitlines()

    return run


@pytest.mark.parametrize('swarm', ['active/true/10.0.0.2/1', 'error/false/10.0.0.2/0'])
def test_cloned_guacamole_swarm_redeploys_with_existing_database(legacy_startup, tmp_path, swarm):
    completed, calls = legacy_startup(swarm)
    assert completed.returncode == 0, completed.stderr
    assert 'Guacamole connections configured.' in completed.stdout
    inspect = next(i for i, call in enumerate(calls) if call.startswith('inspect --type container'))
    assert inspect < calls.index('swarm leave --force') < calls.index('stop orphan-task')
    assert calls.index('stop orphan-task') < calls.index('swarm init --advertise-addr 10.0.0.3')
    assert (tmp_path / 'db.env').stat().st_mode & 0o777 == 0o600
    assert (tmp_path / 'guac_init_done').exists()
    assert any(call.startswith('exec mysql-task ') for call in calls)
    assert "'hostname', '10.0.0.4'" in (tmp_path / 'applied.sql').read_text()


def test_swarm_retry_uses_saved_credentials_after_stale_tasks_are_gone(legacy_startup, tmp_path):
    completed, _ = legacy_startup('error/false/10.0.0.2/0', swarm_init=False)
    assert completed.returncode == 1
    assert (tmp_path / 'db.env').exists()
    assert not (tmp_path / 'guac_init_done').exists()

    completed, calls = legacy_startup('error/false/10.0.0.2/0', image_credentials=False)
    assert completed.returncode == 0, completed.stderr
    assert 'swarm leave --force' not in calls
    assert 'swarm init --advertise-addr 10.0.0.3' in calls
    assert (tmp_path / 'guac_init_done').exists()


def test_local_swarm_with_missing_stack_can_be_retried_without_leaving(legacy_startup):
    completed, calls = legacy_startup('active/true/10.0.0.3/1', stack_deployed=False)
    assert completed.returncode == 0, completed.stderr
    assert not any(call.startswith('swarm ') for call in calls)
    assert any(call.startswith('stack deploy ') for call in calls)


def test_swarm_recovery_does_not_deploy_an_empty_database(legacy_startup, tmp_path):
    (tmp_path / 'db_data' / 'mysql').rmdir()
    completed, calls = legacy_startup('error/false/10.0.0.2/0')
    assert completed.returncode == 1
    assert 'initialized MySQL volume' in completed.stderr
    assert not any(call.startswith(('swarm ', 'stack deploy ')) for call in calls)


@pytest.mark.parametrize('swarm, database_ready, image_credentials, error_message', [
    ('active/true/10.0.0.3/1', True, True, ''),
    ('active/true/10.0.0.3/1', False, True, 'MySQL task did not become ready'),
    ('error/false/10.0.0.2/0', True, False, 'could not read the existing MySQL credentials'),
    ('active/true/10.0.0.2/2', True, True, 'a single-node Swarm'),
], ids=['healthy', 'mysql-timeout', 'missing-credentials', 'multi-node'])
def test_guacamole_startup_checks_mysql_and_protects_existing_swarm(
    legacy_startup, tmp_path, swarm, database_ready, image_credentials, error_message,
):
    completed, calls = legacy_startup(swarm, database_ready=database_ready, image_credentials=image_credentials)

    assert not any(call.startswith(('swarm ', 'run ')) for call in calls)
    if error_message:
        assert completed.returncode == 1 and error_message in completed.stderr
        assert not (tmp_path / 'guac_init_done').exists()
    else:
        assert completed.returncode == 0, completed.stderr
        assert (tmp_path / 'guac_init_done').exists()


def test_guacamole_restart_checks_the_public_https_endpoint():
    manager = object.__new__(BaseComputeManager)
    manager.logger = MagicMock()
    host = 'abcdefghij-display.example.com'
    not_ready, ready = MagicMock(), MagicMock()
    not_ready.__enter__.return_value.status_code = 503
    ready.__enter__.return_value.status_code = 200

    with patch('cloud_fn_utilities.course_objects.compute.base_compute_manager.requests.get',
               side_effect=[not_ready, ConnectTimeout(), ready]) as get, \
            patch('cloud_fn_utilities.course_objects.compute.base_compute_manager.time.sleep'):
        assert manager._wait_for_guacamole(host) is True

    assert [request.args[0] for request in get.call_args_list] == [f'https://{host}/guacamole/'] * 3
