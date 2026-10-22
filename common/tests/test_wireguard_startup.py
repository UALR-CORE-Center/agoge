"""Hermetic contract tests for the actual Python shipped to Ubuntu metadata."""
import base64
import contextlib
import io
import json
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from common.services.wireguard_startup import GUEST_AGENT, render_wireguard_startup


def guest_module():
    module = types.ModuleType('agoge_wireguard_guest')
    exec(compile(GUEST_AGENT, '<embedded WireGuard agent>', 'exec'), module.__dict__)
    return module


def payload():
    return {
        'private_key': base64.b64encode(bytes(range(32))).decode(),
        'peer_public_key': base64.b64encode(bytes(range(1, 33))).decode(),
        'gateway_address': '10.254.254.1/30',
        'peer_address': '10.254.254.2/32',
        'equipment_subnet': '172.30.0.0/24',
        'student_subnets': ['10.20.0.0/24'],
        'listen_port': 51820,
        'callback_token': 'one-time-generated-callback-token',
        'health_url': 'https://api.example.edu/site/wireguard/gateways/abcdefghij/health/',
        'unit_id': 'abcdefghij',
    }


class StartupRendererTests(unittest.TestCase):
    def test_bash_and_embedded_python_parse_without_network_or_cloud_sdk(self):
        script = render_wireguard_startup(
            'projects/test-project/secrets/wg-abcdefghij/versions/1', 'a' * 32)
        result = subprocess.run(['bash', '-n'], input=script, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        embedded = script.split("<<'AGOGE_WIREGUARD_AGENT'\n", 1)[1].split('\nAGOGE_WIREGUARD_AGENT', 1)[0]
        compile(embedded, '<embedded guest>', 'exec')
        self.assertIn('systemctl enable --now agoge-wireguard-health.timer', script)
        self.assertIn('wg-quick@wg0.service.d/agoge-guard.conf', script)
        self.assertIn('ExecStartPre=/usr/bin/python3 /usr/local/lib/agoge-wireguard/agent.py guard', script)
        self.assertNotIn(payload()['private_key'], script)
        self.assertNotIn(payload()['callback_token'], script)
        self.assertNotIn('startup-script-url', script)
        self.assertNotIn('curl ', script)
        self.assertNotIn('set -x', script)

    def test_references_and_nonces_cannot_inject_shell_code(self):
        bad = ['projects/p/secrets/s/versions/latest; reboot', 'http://evil/script',
               'projects/p/secrets/s/versions/0', 'projects/p/secrets/s/versions/latest\nexit']
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                render_wireguard_startup(value, 'a' * 32)
        with self.assertRaises(ValueError):
            render_wireguard_startup('projects/p/secrets/s/versions/1', 'a\nreboot')

    def test_secret_access_uses_metadata_identity_and_never_follows_redirects(self):
        agent = guest_module()
        with self.assertRaisesRegex(RuntimeError, 'redirect_rejected'):
            agent.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.example')
        with tempfile.TemporaryDirectory() as directory:
            agent.ROOT = Path(directory)
            (agent.ROOT / 'secret-version').write_text('projects/p/secrets/s/versions/1')
            responses = [
                {'access_token': 'metadata-token'},
                {'payload': {'data': base64.b64encode(json.dumps(payload()).encode()).decode()}},
            ]
            with patch.object(agent, 'request_json', side_effect=responses) as request:
                config = agent.secret_payload()
            self.assertEqual(config['equipment_subnet'], '172.30.0.0/24')
            self.assertEqual(request.call_args_list[0].args[1], {'Metadata-Flavor': 'Google'})
            self.assertEqual(request.call_args_list[1].args[1], {'Authorization': 'Bearer metadata-token'})
            self.assertTrue(request.call_args_list[1].args[0].startswith('https://secretmanager.googleapis.com/'))


class GuestConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.agent = guest_module()

    def test_configuration_has_one_authorized_peer_and_only_its_equipment_routes(self):
        config = self.agent.validate(payload())
        result = self.agent.configuration(config)
        self.assertEqual(result.count('[Interface]'), 1)
        self.assertEqual(result.count('[Peer]'), 1)
        self.assertIn('AllowedIPs = 10.254.254.2/32, 172.30.0.0/24', result)
        self.assertNotIn('0.0.0.0/0', result)
        self.assertNotIn('PostUp', result)
        self.assertNotIn('SaveConfig', result)

    def test_invalid_keys_addresses_and_arbitrary_routes_are_rejected(self):
        bad_values = [
            ('private_key', 'a' * 44),
            ('peer_public_key', payload()['peer_public_key'] + '\nPostUp = reboot'),
            ('gateway_address', '10.254.254.1/24'),
            ('peer_address', '10.254.254.1/32'),
            ('peer_address', '10.254.254.3/32'),
            ('equipment_subnet', '10.20.0.0/24'),
            ('equipment_subnet', '10.254.254.0/30'),
            ('equipment_subnet', '0.0.0.0/0'),
            ('student_subnets', ['::/0']),
            ('student_subnets', []),
            ('listen_port', True),
            ('listen_port', 0),
            ('health_url', 'http://api.example.edu/health'),
            ('health_url', 'https://token@api.example.edu/health'),
            ('callback_token', 'bad\nheader'),
        ]
        for field, value in bad_values:
            config = payload()
            config[field] = value
            with self.subTest(field=field, value=value), self.assertRaises((ValueError, TypeError)):
                self.agent.validate(config)

    def test_forwarding_permits_only_student_to_equipment_and_established_replies(self):
        rules = self.agent.forwarding_rules(self.agent.validate(payload()))
        self.assertEqual(rules[-1], ['-j', 'DROP'])
        self.assertEqual(rules[0], ['-o', 'wg0', '-s', '10.20.0.0/24', '-d', '172.30.0.0/24', '-j', 'ACCEPT'])
        self.assertIn('ESTABLISHED,RELATED', rules[1])
        self.assertIn('172.30.0.0/24', rules[1])
        self.assertEqual(len(rules), 3)

    def test_atomic_config_is_root_only_and_replaces_instead_of_appending(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'wg0.conf'
            self.agent.atomic_write(target, 'first')
            self.agent.atomic_write(target, 'second')
            self.assertEqual(target.read_text(), 'second')
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(target.parent.iterdir()), [target])

    def test_configuration_restart_is_idempotent_and_keys_do_not_reach_command_arguments(self):
        config = self.agent.validate(payload())
        desired = self.agent.configuration(config)
        fake_target = types.SimpleNamespace(exists=lambda: True, read_text=lambda: desired)
        with patch.object(self.agent, 'Path', return_value=fake_target), \
             patch.object(self.agent, 'atomic_write') as write, \
             patch.object(self.agent, 'configure_forwarding'), \
             patch.object(self.agent, 'report'), \
             patch.object(self.agent, 'command') as command:
            self.agent.configure(config)
        self.assertEqual(write.call_args.args[1], desired)
        commands = [call.args[0] for call in command.call_args_list]
        self.assertIn(['systemctl', 'start', 'wg-quick@wg0'], commands)
        self.assertNotIn(['systemctl', 'restart', 'wg-quick@wg0'], commands)
        self.assertNotIn(config['private_key'], json.dumps(commands))

    def test_health_separates_service_readiness_from_recent_authorized_peer_handshake(self):
        config = self.agent.validate(payload())
        with tempfile.TemporaryDirectory() as directory:
            self.agent.ROOT = Path(directory)
            (self.agent.ROOT / 'boot-id').write_text('cloud-nonce')
            for handshake, expected in ((950, True), (700, False), (0, False)):
                with self.subTest(handshake=handshake), \
                     patch.object(self.agent, 'service_ready', return_value=True), \
                     patch.object(self.agent.time, 'time', return_value=1000), \
                     patch.object(self.agent, 'command', return_value=types.SimpleNamespace(stdout=config['peer_public_key'] + '\t' + str(handshake))), \
                     patch.object(self.agent, 'request_json') as request:
                    self.agent.report(config)
                body = json.loads(request.call_args.args[2])
                self.assertTrue(body['service_ready'])
                self.assertEqual(body['tunnel_ready'], expected)
                self.assertEqual(body['boot_id'], 'cloud-nonce')
                self.assertEqual(body['latest_handshake'], handshake)
                self.assertNotIn(config['private_key'], json.dumps(body))

    def test_service_readiness_checks_real_interface_key_routes_and_forwarding(self):
        config = self.agent.validate(payload())
        public = base64.b64encode(b'P' * 32).decode()
        outputs = {
            ('wg', 'show', 'wg0', 'listen-port'): '51820\n',
            ('wg', 'pubkey'): public + '\n',
            ('wg', 'show', 'wg0', 'public-key'): public + '\n',
            ('wg', 'show', 'wg0', 'peers'): config['peer_public_key'] + '\n',
            ('wg', 'show', 'wg0', 'allowed-ips'): config['peer_public_key'] + '\t10.254.254.2/32, 172.30.0.0/24\n',
            ('ip', '-j', '-4', 'address', 'show', 'dev', 'wg0'): json.dumps([{'addr_info': [{'local': '10.254.254.1', 'prefixlen': 30}]}]),
        }
        def run(args, input_text=None, check=True):
            guarded = args[:3] == ['iptables', '-w', '-C'] and 'AGOGE-WG-BOOT' in args
            return types.SimpleNamespace(returncode=1 if guarded else 0, stdout=outputs.get(tuple(args), ''))
        with patch.object(self.agent, 'command', side_effect=run), \
             patch.object(self.agent, 'Path', return_value=types.SimpleNamespace(read_text=lambda: '1\n')):
            self.assertTrue(self.agent.service_ready(config))
            outputs[('wg', 'show', 'wg0', 'allowed-ips')] = config['peer_public_key'] + '\t0.0.0.0/0'
            self.assertFalse(self.agent.service_ready(config))

    def test_boot_guard_is_installed_atomically_without_fetching_secrets(self):
        calls = []
        def run(args, input_text=None, check=True):
            calls.append((args, input_text))
            return types.SimpleNamespace(returncode=1, stdout='')
        with patch.object(self.agent, 'command', side_effect=run), \
             patch.object(self.agent, 'secret_payload') as fetch, \
             patch.object(self.agent.sys, 'argv', ['agent.py', 'guard']):
            self.assertEqual(self.agent.main(), 0)
        fetch.assert_not_called()
        restore = [item for item in calls if item[0][0] == 'iptables-restore']
        self.assertEqual(len(restore), 1)
        self.assertIn('--noflush', restore[0][0])
        self.assertIn('-A AGOGE-WG-BOOT -j DROP', restore[0][1])
        self.assertIn('-I FORWARD 1 -i wg0 -j AGOGE-WG-BOOT', restore[0][1])
        self.assertIn('-I FORWARD 1 -o wg0 -j AGOGE-WG-BOOT', restore[0][1])
        self.assertIn('-I INPUT 1 -i wg0 -j DROP', restore[0][1])
        self.assertTrue(restore[0][1].endswith('COMMIT\n'))

    def test_forwarding_policy_replacement_uses_one_table_transaction(self):
        config = self.agent.validate(payload())
        calls = []
        def run(args, input_text=None, check=True):
            calls.append((args, input_text))
            return types.SimpleNamespace(returncode=1, stdout='')
        with patch.object(self.agent, 'command', side_effect=run), \
             patch.object(self.agent, 'atomic_write'):
            self.agent.configure_forwarding(config)
        restore = [item for item in calls if item[0][0] == 'iptables-restore']
        self.assertEqual(len(restore), 1)
        self.assertIn('--noflush', restore[0][0])
        transaction = restore[0][1]
        self.assertIn('-F AGOGE-WG\n-A AGOGE-WG ', transaction)
        self.assertIn('-A AGOGE-WG -j DROP', transaction)
        self.assertIn('-I FORWARD 1 -i wg0 -j AGOGE-WG-BOOT', transaction)
        self.assertTrue(transaction.endswith('COMMIT\n'))
        self.assertFalse(any(args[:3] == ['iptables', '-w', '-F'] for args, _ in calls))

    def test_start_or_restart_precedes_allowlist_and_guard_removal(self):
        config = self.agent.validate(payload())
        events = []
        target = types.SimpleNamespace(exists=lambda: True, read_text=lambda: 'old config')
        with patch.object(self.agent, 'Path', return_value=target), \
             patch.object(self.agent, 'atomic_write'), \
             patch.object(self.agent, 'install_boot_guard', side_effect=lambda: events.append('guard')), \
             patch.object(self.agent, 'command', side_effect=lambda args: events.append(args[1])), \
             patch.object(self.agent, 'configure_forwarding', side_effect=lambda _: events.append('policy')), \
             patch.object(self.agent, 'remove_boot_guard', side_effect=lambda: events.append('unguard')), \
             patch.object(self.agent, 'report', side_effect=lambda _: events.append('report')):
            self.agent.configure(config)
        self.assertEqual(events, ['guard', 'enable', 'restart', 'policy', 'unguard', 'report'])

    def test_secret_failure_keeps_cached_configuration_guarded_and_redacts_errors(self):
        events = []
        stderr = io.StringIO()
        with patch.object(self.agent.sys, 'argv', ['agent.py', 'configure']), \
             patch.object(self.agent, 'install_boot_guard', side_effect=lambda: events.append('guard')), \
             patch.object(self.agent, 'secret_payload', side_effect=RuntimeError(payload()['private_key'])), \
             patch.object(self.agent, 'remove_boot_guard') as unguard, \
             contextlib.redirect_stderr(stderr):
            self.assertEqual(self.agent.main(), 1)
        self.assertEqual(events, ['guard'])
        unguard.assert_not_called()
        self.assertNotIn(payload()['private_key'], stderr.getvalue())
        self.assertIn('lease authorization', stderr.getvalue())

    def test_policy_failure_does_not_remove_reboot_guard(self):
        config = self.agent.validate(payload())
        target = types.SimpleNamespace(exists=lambda: False)
        with patch.object(self.agent, 'Path', return_value=target), \
             patch.object(self.agent, 'atomic_write'), \
             patch.object(self.agent, 'install_boot_guard'), \
             patch.object(self.agent, 'command'), \
             patch.object(self.agent, 'configure_forwarding', side_effect=RuntimeError('restore failed')), \
             patch.object(self.agent, 'remove_boot_guard') as unguard, \
             self.assertRaises(RuntimeError):
            self.agent.configure(config)
        unguard.assert_not_called()

    def test_health_rejects_cached_interface_while_reboot_guard_is_installed(self):
        config = self.agent.validate(payload())
        with patch.object(self.agent, 'command', return_value=types.SimpleNamespace(returncode=0)):
            self.assertFalse(self.agent.service_ready(config))

    def test_health_failure_is_unready_and_does_not_expose_exception_text(self):
        config = self.agent.validate(payload())
        with tempfile.TemporaryDirectory() as directory:
            self.agent.ROOT = Path(directory)
            (self.agent.ROOT / 'boot-id').write_text('cloud-nonce')
            with patch.object(self.agent, 'service_ready', side_effect=RuntimeError(config['private_key'])), \
                 patch.object(self.agent, 'request_json') as request:
                self.agent.report(config)
            body = json.loads(request.call_args.args[2])
        self.assertFalse(body['service_ready'])
        self.assertFalse(body['tunnel_ready'])
        self.assertEqual(body['error'], 'wireguard_service_unready')
        self.assertNotIn(config['private_key'], json.dumps(body))


if __name__ == '__main__':
    unittest.main()
