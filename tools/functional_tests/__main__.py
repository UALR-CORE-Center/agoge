"""Run the predeployment lab scenarios without cloud credentials or resources."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SUITES = {
    'community': (
        'cloud_functions/tests/test_community_shared_proxy.py',
        'common/tests/test_shared_guacamole_api.py',
        'common/tests/test_community_guacamole.py',
        'common/tests/test_community_guacamole_startup.py',
        'cloud_functions/tests/test_community_proxy_bootstrap.py',
        'cloud_functions/tests/test_community_proxy_compute_lifecycle.py',
        'cloud_functions/tests/test_unit_dhcp_service.py',
    ),
    'solo': ('tools/functional_tests/test_solo_workout.py',),
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog='python -m tools.functional_tests',
        description=(
            'Validate community and solo lab lifecycles locally. These scenarios '
            'run application code with fake cloud services and Guacamole transport; '
            'they do not create resources or require GCP credentials.'
        ),
    )
    result.add_argument('--suite', choices=('all', *SUITES), default='all',
                        help='Choose the scenarios to run (default: all).')
    result.add_argument('--verbose', action='store_true', help='Show each scenario name.')
    result.add_argument('--list', action='store_true', dest='list_scenarios',
                        help='List the selected scenario files without running them.')
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    names = tuple(SUITES) if args.suite == 'all' else (args.suite,)
    scenarios = tuple(dict.fromkeys(path for name in names for path in SUITES[name]))
    print('Offline functional tests: ' + ', '.join(names), flush=True)
    print('Real lab lifecycle and Guacamole configuration; fake cloud and HTTP transport.', flush=True)
    print('No GCP credentials, resources, deployment, or remote WireGuard peer are required.', flush=True)
    if args.list_scenarios:
        print('\n'.join(scenarios))
        return 0

    for scenario in scenarios:
        if not (REPOSITORY_ROOT / scenario).is_file():
            print(f'Missing functional scenario: {scenario}', file=sys.stderr)
            return 2

    # Match the application's existing source layout while keeping this entry point
    # independent of debug_lab.load_backend (which intentionally talks to real GCP).
    for relative in ('', 'api', 'cloud_functions', 'build_files'):
        directory = str(REPOSITORY_ROOT / relative)
        if directory not in sys.path:
            sys.path.insert(0, directory)
    try:
        import pytest
    except ImportError:
        print('Install the repository requirements first: python -m pip install -r requirements.txt',
              file=sys.stderr)
        return 2

    result = pytest.main([
        '--rootdir', str(REPOSITORY_ROOT),
        '-c', str(REPOSITORY_ROOT / 'pytest.ini'),
        '-v' if args.verbose else '-q',
        *(str(REPOSITORY_ROOT / scenario) for scenario in scenarios),
    ])
    if result == 0:
        print('Offline functional scenarios passed. Live GCP deployment and guest startup remain separate checks.',
              flush=True)
    else:
        print('Offline functional scenarios failed; review the failures before deploying.',
              file=sys.stderr, flush=True)
    return int(result)


if __name__ == '__main__':
    raise SystemExit(main())
