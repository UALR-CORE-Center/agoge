"""The external API credentials that a tenant may explicitly share with its parent."""

SHARED_API_SECRET_NAMES = ('sendgrid_api_key', 'openai_api_key', 'shodan_api_key')


def shared_api_secret_names(env: dict) -> tuple[str, ...]:
    selected = env.get('shared_api_secrets', [])
    if not isinstance(selected, list) or any(
        name not in SHARED_API_SECRET_NAMES for name in selected
    ):
        raise ValueError(
            'shared_api_secrets must be a list containing only '
            'sendgrid_api_key, openai_api_key, and shodan_api_key'
        )
    if selected and (
        not env.get('parent_project') or env['parent_project'] == env.get('project')
    ):
        raise ValueError('Shared API secrets require a different parent_project')
    return tuple(name for name in SHARED_API_SECRET_NAMES if name in selected)
