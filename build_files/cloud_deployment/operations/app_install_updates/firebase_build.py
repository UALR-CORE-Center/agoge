"""Resolve tenant Firebase configuration before compiling the frontend."""

import re
from urllib.parse import urlsplit

from common.constants.database import ADMIN_INFO_DOCUMENT, DbCollections
from common.exceptions import AgogeValidationError


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

    if env.env_dict.get('firebase_auth_domain') != domain:
        env.db.update(
            collection_name=DbCollections.ADMIN_INFO,
            doc_id=ADMIN_INFO_DOCUMENT,
            data={'firebase_auth_domain': domain},
        )
        env.env_dict['firebase_auth_domain'] = domain
    env.firebase_auth_domain = domain
    env._auth_config = None

    app_host = urlsplit(env.main_app_url).hostname
    print(
        f'Building React with Firebase project {env.project} and auth domain {domain}.\n'
        f'In Firebase Authentication for {env.project}, enable Google and authorize {app_host}.\n'
        f'Google OAuth callback: https://{domain}/__/auth/handler\n'
        'These settings are compiled into React. Rebuild React after changing them.'
    )
