"""The nested finalize handshake (PRD V14): ImageTemplateManager.finalize_nested, its NESTED_FINALIZE route,
the finalized check-in, the watcher bootstraps, and agoge-nested-finalize run for real against fake virsh/curl.
"""
import copy
import json
import shutil
import subprocess
import textwrap
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from cloud_fn_utilities.course_objects.compute import image_template_manager as itm_module
from cloud_fn_utilities.course_objects.compute.image_template_manager import (FINALIZE_METADATA_KEY,
                                                                              MSG_CHECK_IN_FAILED,
                                                                              MSG_FINALIZE_TIMEOUT,
                                                                              ImageTemplateManager)
from cloud_fn_utilities.server_specific import nested_scripts
from cloud_fn_utilities.server_specific.nested_scripts import (FINALIZE_ANSWERED_PATH, FINALIZE_PATH, HOST_JSON_PATH,
                                                               MEDIA_DIR, RUN_DIR, STATE_DIR, WORK_DIR,
                                                               render_finalize_bootstrap, render_finalize_watcher)
from cloud_functions.handlers import control_handler as control_handler_module
from cloud_functions.handlers.control_handler import ControlHandler
from common.constants.database import DbCollections
from common.constants.nested import NESTED_FINALIZE_TIMEOUT_SECONDS
from common.constants.pub_sub import PubSub
from common.constants.states import ImageStatus
from common.exceptions import Conflict, OperationTimeout

from test_nested_template_provisioning import _manager as _provisioning_manager
from test_nested_template_provisioning import _record as _provisioning_record

PROJECT = 'test-dev-787001'


# ------------------------------------------------------------------ finalize_nested

class FakeDb:
    """Field-mask updates, like the Firestore wrapper."""

    def __init__(self, record):
        self.record = record

    def get(self, collection_name, doc_id):
        assert collection_name == DbCollections.IMAGE and doc_id == 'nestlab'
        return copy.deepcopy(self.record)

    def update(self, collection_name, doc_id, data):
        self.record.update(copy.deepcopy(data))


class FakeClock:
    """time.monotonic and time.sleep: sleeping advances the clock instantly."""

    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def _record(phase='ready', status=ImageStatus.CHECKED_OUT.value, **build):
    return {'name': 'nestlab', 'status': status, 'nested': {'parent_os': 'debian-12'},
            'nested_build': {'phase': phase, **build}}


@pytest.fixture
def finalize(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(itm_module, 'time', SimpleNamespace(monotonic=clock.monotonic, sleep=clock.sleep))

    def make(record, answers=()):
        manager = object.__new__(ImageTemplateManager)
        manager.class_name = 'ImageTemplateManager'
        manager.logger = Mock()
        manager.image_name = manager.server_name = 'nestlab'
        manager.collection = DbCollections.IMAGE
        manager.shared_edit_authorized = False
        manager._require_image_management = Mock()
        manager.db = FakeDb(record)
        manager.pubsub_manager = Mock()
        manager.compute_instance = Mock()
        nonces = []

        def set_metadata(name, items=None, remove=None, wait=True):
            if items:
                nonces.append(items[FINALIZE_METADATA_KEY])
                # The record already says finalizing when the watcher is asked.
                assert manager.db.record['nested_build']['phase'] == 'finalizing'
                assert manager.db.record['nested_build']['finalize_nonce'] == items[FINALIZE_METADATA_KEY]
        manager.compute_instance.set_metadata.side_effect = set_metadata
        # Each answer is a function of the nonce; past the list the watcher has said nothing.
        script = list(answers)
        manager.compute_instance.get_guest_attributes.side_effect = (
            lambda name, query_path: script.pop(0)(nonces[-1]) if script else {})
        return manager, nonces
    make.clock = clock
    return make


def _published(manager):
    return [call.kwargs for call in manager.pubsub_manager.msg.call_args_list]


def _key_removed(manager):
    return any(call.kwargs.get('remove') == [FINALIZE_METADATA_KEY]
               for call in manager.compute_instance.set_metadata.call_args_list)


def test_ok_publishes_check_in_once_and_removes_the_key(finalize):
    manager, nonces = finalize(_record(), answers=[lambda n: {}, lambda n: {'finalize-result': f'ok:{n}'}])

    assert manager.finalize_nested() is True

    assert _published(manager) == [{
        'handler': str(PubSub.Handlers.CONTROL.value), 'action': str(PubSub.Actions.CHECK_IN.value),
        'course_object': str(PubSub.CourseObjects.TEMPLATE_SERVER.value), 'image_name': 'nestlab',
        'shared_edit_authorized': 'false',
    }]
    assert len(nonces) == 1 and len(nonces[0]) == 32
    assert _key_removed(manager)
    manager.compute_instance.get_guest_attributes.assert_called_with('nestlab', query_path='agoge-nested/')
    # CHECK_IN moves it to finalized after the image exists; until then it stays finalizing.
    assert manager.db.record['nested_build']['phase'] == 'finalizing'


def test_an_answer_to_an_earlier_nonce_is_ignored(finalize):
    manager, _ = finalize(_record(phase='finalized'), answers=[
        lambda n: {'finalize-result': 'ok:stale-nonce'},
        lambda n: {'finalize-result': f'ok:{n}'},
    ])

    assert manager.finalize_nested() is True
    assert manager.compute_instance.get_guest_attributes.call_count == 2
    assert len(_published(manager)) == 1


def test_error_stores_the_message_and_publishes_nothing(finalize):
    manager, nonces = finalize(_record(), answers=[
        lambda n: {'finalize-result': f'error:{n}:web: guest did not shut down'}])

    assert manager.finalize_nested() is False

    assert _published(manager) == []
    build = manager.db.record['nested_build']
    assert build['phase'] == 'failed'
    assert build['message'] == 'web: guest did not shut down'
    # Kept, so the API routes the next Check In to a finalize again.
    assert build['finalize_nonce'] == nonces[0]
    assert _key_removed(manager)
    # Nothing stopped or deleted the server.
    assert manager.compute_instance.method_calls == [
        call for call in manager.compute_instance.method_calls if call[0] in ('set_metadata', 'get_guest_attributes')]


def test_timeout_returns_the_phase_to_ready_with_a_message(finalize):
    manager, _ = finalize(_record())

    assert manager.finalize_nested() is False

    assert _published(manager) == []
    build = manager.db.record['nested_build']
    assert build['phase'] == 'ready'
    assert build['message'] == MSG_FINALIZE_TIMEOUT
    assert build['finalize_nonce'] is None
    assert _key_removed(manager)
    # The wait stays inside the function budget.
    assert finalize.clock.now - 1000.0 <= NESTED_FINALIZE_TIMEOUT_SECONDS
    assert manager.compute_instance.get_guest_attributes.call_count > 1


def test_unreadable_attributes_keep_the_wait_going(finalize):
    def unreadable(nonce):
        raise RuntimeError('503 from compute')
    manager, _ = finalize(_record(), answers=[unreadable, lambda n: {'finalize-result': f'ok:{n}'}])

    assert manager.finalize_nested() is True


def test_a_failed_finalize_can_be_finalized_again(finalize):
    manager, nonces = finalize(_record(phase='failed', finalize_nonce='old', message='web: guest did not shut down'),
                               answers=[lambda n: {'finalize-result': f'ok:{n}'}])

    assert manager.finalize_nested() is True
    assert nonces[0] != 'old'
    assert manager.db.record['nested_build']['message'] is None


@pytest.mark.parametrize('record', [
    _record(phase='building'),
    _record(phase='finalizing', finalize_nonce='in-flight'),
    _record(phase='failed', message='no guest was built'),
    _record(phase='finalized', status=ImageStatus.CHECKED_IN.value),
], ids=['building', 'duplicate-delivery', 'failed-build', 'checked-in'])
def test_a_record_that_cannot_be_finalized_is_refused_before_any_request(finalize, record):
    manager, _ = finalize(record)

    with pytest.raises(Conflict):
        manager.finalize_nested()

    manager.compute_instance.set_metadata.assert_not_called()
    assert manager.db.record == record


def test_a_failed_check_in_publish_returns_the_phase_to_ready(finalize):
    manager, _ = finalize(_record(), answers=[lambda n: {'finalize-result': f'ok:{n}'}])
    manager.pubsub_manager.msg.side_effect = RuntimeError('pubsub down')

    with pytest.raises(RuntimeError):
        manager.finalize_nested()

    # Never stuck at finalizing, which the API refuses to check in.
    assert manager.db.record['nested_build']['phase'] == 'ready'
    assert manager.db.record['nested_build']['message'] == MSG_CHECK_IN_FAILED


def test_a_failed_request_returns_the_phase_to_ready(finalize):
    manager, _ = finalize(_record())
    manager.compute_instance.set_metadata.side_effect = RuntimeError('412')

    with pytest.raises(RuntimeError):
        manager.finalize_nested()

    assert manager.db.record['nested_build']['phase'] == 'ready'
    assert _published(manager) == []


# ------------------------------------------------------------------ check-in after the finalize

def _check_in_manager(record, created=True):
    manager = object.__new__(ImageTemplateManager)
    manager.class_name = 'ImageTemplateManager'
    manager.log_name = 'test'
    manager.logger = Mock()
    manager.debug = False
    manager.image_name = manager.server_name = 'nestlab'
    manager.collection = DbCollections.IMAGE
    manager.shared_edit_authorized = False
    manager.env = SimpleNamespace(project=PROJECT)
    manager._require_image_management = Mock()
    manager.create_production_image = Mock(return_value=created)
    manager.pubsub_manager = Mock()
    manager.compute_image = Mock()
    manager.compute_image.self_link.return_value = f'projects/{PROJECT}/global/images/image-nestlab'
    manager.db = FakeDb(record)
    return manager


def _full_record(phase):
    # A record that validates as AgogeImageModel, which the check-in's write requires.
    return _provisioning_record(name='nestlab', image='nestlab', nested_build={'phase': phase, 'finalize_nonce': 'n1'})


def test_check_in_after_a_finalize_records_finalized():
    manager = _check_in_manager(_full_record('finalizing'))

    manager.check_in()

    record = manager.db.record
    assert record['status'] == ImageStatus.CHECKED_IN.value
    assert record['nested_build']['phase'] == 'finalized'
    assert record['nested_build']['finalize_nonce'] is None


def test_a_failed_image_after_a_finalize_returns_the_phase_to_ready():
    manager = _check_in_manager(_full_record('finalizing'), created=False)

    with pytest.raises(OperationTimeout):
        manager.check_in()

    assert manager.db.record['nested_build']['phase'] == 'ready'
    assert manager.db.record['nested_build']['message'] == MSG_CHECK_IN_FAILED
    assert manager.db.record['status'] == ImageStatus.CHECKED_OUT.value


def test_check_in_of_a_failed_build_does_not_claim_finalized():
    manager = _check_in_manager(_full_record('failed'))

    manager.check_in()

    assert manager.db.record['nested_build']['phase'] == 'failed'


# ------------------------------------------------------------------ routing

def test_nested_finalize_routes_to_finalize_nested():
    manager = MagicMock()
    attributes = {
        PubSub.EventAttributes.HANDLER: str(PubSub.Handlers.CONTROL.value),
        PubSub.EventAttributes.ACTION: str(PubSub.Actions.NESTED_FINALIZE.value),
        PubSub.EventAttributes.IMAGE_NAME: 'nestlab',
        PubSub.EventAttributes.COURSE_OBJECT: str(PubSub.CourseObjects.TEMPLATE_SERVER.value),
        'shared_edit_authorized': 'true',
    }
    with (
        patch.object(control_handler_module, 'CloudEnv'),
        patch.object(control_handler_module, 'Logger'),
        patch.object(control_handler_module, 'PubSubManager'),
        patch.object(control_handler_module.DocumentDatabaseFactory, 'create_db_object'),
        patch.object(control_handler_module.ComputeManagerFactory, 'create_manager_object',
                     return_value=manager) as factory,
    ):
        ControlHandler(event_attributes=attributes, env_dict={'project': PROJECT}).route()

    assert factory.call_args.kwargs['manager_type'] == PubSub.CourseObjects.TEMPLATE_SERVER
    assert factory.call_args.kwargs['shared_edit_authorized'] is True
    manager.load.assert_called_once_with(server_name='nestlab')
    manager.finalize_nested.assert_called_once_with()


# ------------------------------------------------------------------ bootstraps

def test_both_check_out_paths_install_the_finalize_watcher():
    first, first_built = _provisioning_manager(_provisioning_record())
    first.check_out(product_keys={'desk': 'ABCDE-FGHIJ-KLMNO-PQRST-UVWXY'})
    again, again_built = _provisioning_manager(_provisioning_record(
        phase='finalized', self_link=f'projects/{PROJECT}/global/images/image-nestedhost',
        status=ImageStatus.CHECKED_IN.value))
    again.check_out()

    for built in (first_built, again_built):
        script = built['items']['startup-script']
        assert render_finalize_bootstrap() in script
        assert script.index('useradd') < script.index('agoge-nested-finalize bootstrap')
        subprocess.run(['bash', '-n'], input=script, text=True, check=True)
    assert 'agoge-nested-builder bootstrap' in first_built['items']['startup-script']
    assert 'agoge-nested-builder' not in again_built['items']['startup-script']


def test_finalize_bootstrap_is_valid_bash_transient_and_embeds_the_watcher():
    bootstrap = render_finalize_bootstrap()

    subprocess.run(['bash', '-n'], input=bootstrap, text=True, check=True)
    assert render_finalize_watcher().rstrip('\n') in bootstrap
    assert f"'{FINALIZE_PATH}'" in bootstrap and 'systemd-run --unit=agoge-nested-finalize' in bootstrap
    # Never enabled: an enabled unit would be baked into the image and run on every lab server.
    assert 'systemctl enable' not in bootstrap
    assert not any(line.strip().startswith('exit') for line in bootstrap.splitlines()[-6:])


def test_finalize_bootstrap_refuses_a_watcher_holding_its_delimiter(monkeypatch):
    monkeypatch.setattr(nested_scripts, 'render_finalize_watcher', lambda: 'AGOGE_NESTED_FINALIZE_SCRIPT\n')

    with pytest.raises(ValueError):
        render_finalize_bootstrap()


def test_watcher_passes_bash_n_and_never_destroys_a_domain(tmp_path):
    script = tmp_path / 'agoge-nested-finalize'
    script.write_text(render_finalize_watcher())

    assert subprocess.run(['bash', '-n', str(script)], capture_output=True).returncode == 0
    assert 'virsh destroy' not in render_finalize_watcher()
    assert 'destroy' not in render_finalize_watcher()


# ------------------------------------------------------------------ the watcher, executed

needs_tools = pytest.mark.skipif(shutil.which('bash') is None or shutil.which('jq') is None, reason='needs bash, jq')

# Metadata: the attributes directory answers with $FAKE_DIR/attributes.json and an ETag header.
FAKE_CURL = textwrap.dedent("""\
    #!/bin/bash
    echo "curl $*" >> "$FAKE_LOG"
    headers= data= url=
    while [ $# -gt 0 ]; do
      case "$1" in
        -D) headers=$2; shift ;;
        --data) data=$2; shift ;;
        -X|-H) shift ;;
        http*) url=$1 ;;
      esac
      shift
    done
    case "$url" in
      */guest-attributes/agoge-nested/*) echo "${url##*/}=$data" >> "$FAKE_DIR/guest-attributes" ;;
      */instance/attributes/\\?*)
        [ -n "$headers" ] && printf 'HTTP/1.1 200 OK\\r\\nETag: etag-1\\r\\n\\r\\n' > "$headers"
        cat "$FAKE_DIR/attributes.json" ;;
      *) exit 22 ;;
    esac
""")
# Domains: $FAKE_DIR/domains/<name>.state; names in $FAKE_STUBBORN ignore an ACPI shutdown.
FAKE_VIRSH = textwrap.dedent("""\
    #!/bin/bash
    echo "virsh $*" >> "$FAKE_LOG"
    D="$FAKE_DIR/domains"
    case "$1" in
      domstate) cat "$D/$2.state" ;;
      shutdown)
        case " $FAKE_STUBBORN " in *" $2 "*) ;; *) echo "shut off" > "$D/$2.state" ;; esac ;;
      managedsave-remove) ;;
      snapshot-list) cat "$D/$2.snapshots" 2>/dev/null ;;
      snapshot-delete) sed -i.bak "/^$3\\$/d" "$D/$2.snapshots" ;;
      snapshot-create-as)
        [ "$(cat "$D/$2.state")" = "shut off" ] || exit 1
        echo "$3" >> "$D/$2.snapshots" ;;
    esac
    exit 0
""")
FAKE_LOGGER = '#!/bin/bash\necho "$(basename "$0") $*" >> "$FAKE_LOG"\n'


@pytest.fixture
def watcher(tmp_path):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name, body in {'curl': FAKE_CURL, 'virsh': FAKE_VIRSH, 'sleep': FAKE_LOGGER, 'apt-get': FAKE_LOGGER,
                       'fstrim': FAKE_LOGGER}.items():
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    fake = tmp_path / 'fake'
    (fake / 'domains').mkdir(parents=True)
    root = tmp_path / 'root'
    host_json = root / HOST_JSON_PATH.lstrip('/')
    host_json.parent.mkdir(parents=True)
    host_json.write_text(json.dumps({'guests': [{'name': 'web'}, {'name': 'desk'}, {'name': 'fw'}]}))
    for path in (MEDIA_DIR, RUN_DIR, STATE_DIR, WORK_DIR):
        (root / path.lstrip('/')).mkdir(parents=True)
        (root / path.lstrip('/') / 'leftover').write_text('x')
    script = tmp_path / 'agoge-nested-finalize'
    script.write_text(render_finalize_watcher())

    def run(nonce='nonce-1', states=None, stubborn='', polls=1):
        for guest, state in (states or {'web': 'running', 'desk': 'running', 'fw': 'shut off'}).items():
            (fake / 'domains' / f'{guest}.state').write_text(state + '\n')
        (fake / 'attributes.json').write_text(json.dumps({'agoge-nested-finalize': nonce} if nonce else {}))
        (fake / 'guest-attributes').write_text('')
        log = tmp_path / 'log'
        log.write_text('')
        env = {'PATH': f'{bin_dir}:/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin', 'FAKE_LOG': str(log),
               'FAKE_DIR': str(fake), 'FAKE_STUBBORN': stubborn, 'AGOGE_NESTED_ROOT': str(root),
               'AGOGE_NESTED_FINALIZE_POLLS': str(polls)}
        result = subprocess.run(['bash', str(script)], capture_output=True, text=True, env=env, timeout=60)
        return result, log.read_text(), (fake / 'guest-attributes').read_text().splitlines()

    run.root = root
    run.fake = fake
    return run


def _snapshots(fake, guest):
    path = fake / 'domains' / f'{guest}.snapshots'
    return path.read_text().split() if path.exists() else []


@needs_tools
def test_watcher_shuts_guests_down_snapshots_them_cleans_up_and_answers_ok(watcher):
    (watcher.fake / 'domains' / 'desk.snapshots').write_text('agoge-pristine\n')

    result, log, answers = watcher()

    assert result.returncode == 0, result.stderr
    assert answers == ['finalize-result=ok:nonce-1']
    commands = log.splitlines()
    # Only running guests are shut down, and every guest is snapshotted after all are off.
    assert 'virsh shutdown web' in commands and 'virsh shutdown desk' in commands
    assert 'virsh shutdown fw' not in commands
    first_snapshot = next(i for i, line in enumerate(commands) if 'snapshot-create-as' in line)
    assert all(i < first_snapshot for i, line in enumerate(commands) if line.startswith('virsh shutdown'))
    for guest in ('web', 'desk', 'fw'):
        assert f'virsh managedsave-remove {guest}' in commands
        assert f'virsh snapshot-create-as {guest} agoge-pristine --atomic' in commands
        assert _snapshots(watcher.fake, guest) == ['agoge-pristine']
        assert (watcher.fake / 'domains' / f'{guest}.state').read_text().strip() == 'shut off'
    assert 'virsh snapshot-delete desk agoge-pristine' in commands
    for path in (MEDIA_DIR, RUN_DIR, STATE_DIR, WORK_DIR):
        assert not (watcher.root / path.lstrip('/')).exists()
    # The runtime still needs host.json at the next boot.
    assert (watcher.root / HOST_JSON_PATH.lstrip('/')).exists()
    assert 'apt-get clean' in commands and 'fstrim -av' in commands
    assert not any(line.startswith('virsh start') for line in commands)
    assert 'wait_for_change=true' in log


@needs_tools
def test_a_guest_that_will_not_shut_down_fails_the_finalize_without_being_forced(watcher):
    result, log, answers = watcher(stubborn='desk')

    assert answers == ['finalize-result=error:nonce-1:desk: guest did not shut down']
    assert 'destroy' not in log
    assert 'snapshot-create-as' not in log
    # Nothing is cleaned up, so a retry after the instructor fixes the guest still has everything.
    assert (watcher.root / STATE_DIR.lstrip('/') / 'leftover').exists()
    # It waited the contract's 240 s before giving up.
    assert sum(int(line.split()[1]) for line in log.splitlines() if line.startswith('sleep ')) >= 240


@needs_tools
def test_a_nonce_is_answered_only_once(watcher):
    watcher()
    result, log, answers = watcher(states={'web': 'running', 'desk': 'shut off', 'fw': 'shut off'})

    assert result.returncode == 0
    assert answers == []
    assert 'virsh' not in log
    assert (watcher.root / FINALIZE_ANSWERED_PATH.lstrip('/')).read_text().strip() == 'nonce-1'


@needs_tools
def test_no_pending_nonce_does_nothing(watcher):
    result, log, answers = watcher(nonce=None)

    assert result.returncode == 0
    assert answers == [] and 'virsh' not in log


@needs_tools
def test_a_host_that_was_never_built_answers_an_error(watcher):
    (watcher.root / HOST_JSON_PATH.lstrip('/')).unlink()

    _, log, answers = watcher()

    assert len(answers) == 1 and answers[0].startswith('finalize-result=error:nonce-1:')
    assert 'virsh' not in log


@needs_tools
def test_the_long_poll_sends_back_the_etag_it_received(watcher):
    # Without it every poll returns at once and the watcher spins.
    result, log, answers = watcher(polls=2)

    polls = [line for line in log.splitlines() if 'wait_for_change=true' in line]
    assert result.returncode == 0
    assert len(polls) == 2
    assert 'last_etag=NONE' in polls[0] and 'last_etag=etag-1' in polls[1]
    assert answers == ['finalize-result=ok:nonce-1']
