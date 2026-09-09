"""Resolve tenant Firebase configuration before compiling the frontend."""

import re
from urllib.parse import urlsplit

import requests
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import GoogleAuthError
from google.cloud import resourcemanager_v3

from common.constants.database import ADMIN_INFO_DOCUMENT, DbCollections
from common.exceptions import AgogeValidationError


FIREBASE_PROJECT_CONFIG_URL = 'https://identitytoolkit.googleapis.com/v1/projects'


def _app_origin(env) -> str:
    # Shared routing uses the parent app host even if a legacy main_app_url
    # override remains in the environment document.
    if env.project_path and env.parent_dns_suffix:
        return f'https://app{env.parent_dns_suffix}'
    url = urlsplit(env.main_app_url)
    return f'{url.scheme}://{url.netloc}'


def _firebase_project_config(api_key: str, app_origin: str) -> dict:
    """Read the same public project configuration used by the browser SDK."""
    try:
        # Keep the key out of URLs, command lines and exception messages.
        # Supply the deployed app origin for browser-key referrer restrictions.
        with requests.get(
            FIREBASE_PROJECT_CONFIG_URL,
            headers={'X-Goog-Api-Key': api_key, 'Referer': f'{app_origin}/'},
            timeout=(5, 15),
            allow_redirects=False,
        ) as response:
            if response.status_code != 200:
                raise AgogeValidationError(
                    f'Firebase could not validate api_key (HTTP {response.status_code}). '
                    'Check that this is the selected project\'s Firebase Web API key, '
                    f'Authentication is configured, and its API/referrer restrictions allow {app_origin}.'
                )
            config = response.json()
    except (requests.RequestException, ValueError):
        raise AgogeValidationError(
            'Could not read Firebase project configuration. Check network access and retry the build.'
        ) from None
    if not isinstance(config, dict) or not config.get('projectId'):
        raise AgogeValidationError('Firebase returned no project ID. Cannot verify api_key before building.')
    return config


def validate_firebase_project(env) -> None:
    """Reject a copied API key even when authDomain/projectId look correct."""
    api_key = env.api_key
    if not isinstance(api_key, str) or not api_key.strip():
        raise AgogeValidationError(
            f'Missing Firebase api_key in {env.project}. Set it through '
            'Synchronize Environment Variables → Specific → api_key.'
        )

    # Read the real project number; a copied environment can contain an old
    # project_number as well as an old key, so comparing those is insufficient.
    try:
        with resourcemanager_v3.ProjectsClient() as client:
            project = client.get_project(name=f'projects/{env.project}', retry=None, timeout=20)
    except (GoogleAPICallError, GoogleAuthError):
        raise AgogeValidationError(
            f'Cannot verify project metadata for {env.project}. Refresh setup credentials '
            'and check resourcemanager.projects.get permission before retrying.'
        ) from None
    project_number = project.name.removeprefix('projects/')
    if project.project_id != env.project or not project_number.isdigit():
        raise AgogeValidationError(f'Unexpected GCP project metadata for {env.project}. Build stopped.')

    config = _firebase_project_config(api_key, _app_origin(env))
    actual_project = str(config['projectId'])
    if actual_project not in (env.project, project_number):
        raise AgogeValidationError(
            f'Firebase api_key selects project {actual_project}, but the deployment target is '
            f'{env.project} ({project_number}). Replace api_key in {env.project} using '
            'Synchronize Environment Variables → Specific → api_key with the Firebase Web API key '
            'from that child project, then rebuild React. Changing authDomain or load-balancer '
            'routing does not change the project selected by an API key.'
        )
    print(f'Firebase API key verified for {env.project} ({project_number}).')


def prepare_firebase_auth(env) -> None:
    """Migrate missing/obsolete domains while allowing working custom domains."""
    default_domain = f'{env.project}.firebaseapp.com'
    current_domain = (env.env_dict.get('firebase_auth_domain') or '').strip()
    domain = default_domain
    if current_domain and current_domain != default_domain:
        print(f'Firebase authentication for {env.project} currently uses {current_domain}.')
        while True:
            choice = input(
                f'[Enter] Use {default_domain} / [K] Keep the configured custom domain / '
                '[C] Cancel deployment: '
            ).strip().upper()
            if choice == 'C':
                raise AgogeValidationError('Deployment cancelled before building applications.')
            if choice in ('', 'K'):
                domain = current_domain if choice == 'K' else default_domain
                break
            print('Choose Enter, K, or C.')

    if len(domain) > 253 or any(
        not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', label)
        for label in domain.split('.')
    ) or '.' not in domain:
        raise AgogeValidationError(
            'firebase_auth_domain must be a hostname without a scheme, port, or path. '
            'Use the default Firebase domain or correct the custom domain in setup.'
        )

    validate_firebase_project(env)

    if env.env_dict.get('firebase_auth_domain') != domain:
        env.db.update(
            collection_name=DbCollections.ADMIN_INFO,
            doc_id=ADMIN_INFO_DOCUMENT,
            data={'firebase_auth_domain': domain},
        )
        env.env_dict['firebase_auth_domain'] = domain
    env.firebase_auth_domain = domain
    env._auth_config = None

    app_host = urlsplit(_app_origin(env)).hostname
    print(
        f'Building React with Firebase project {env.project} and auth domain {domain}.\n'
        f'In Firebase Authentication for {env.project}, enable Google and authorize {app_host}.\n'
        f'Google OAuth callback: https://{domain}/__/auth/handler\n'
        'These settings are compiled into React. Rebuild React after changing them.'
    )
