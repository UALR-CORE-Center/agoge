import os
from typing import List


class AppConfig:
    DOMAIN_KEY = 'DOMAIN'
    PARENT_DOMAIN_KEY = 'PARENT_DOMAIN'
    SUB_DOMAIN_KEY = 'SUB_DOMAIN'
    DEFAULT_SUB_DOMAIN = 'app'

    def __init__(self) -> None:
        self.domain = None
        self.parent_domain = None
        self.sub_domain = None
        self._load()
        development = os.environ.get('DEVELOPMENT', 'False')
        self.is_development = bool(development.lower() == 'true')

    def origins(self) -> List:
        if self.is_development:
            return self._origins()
        else:
            return self._origins(self.domain, self.sub_domain, self.parent_domain)

    def hosts(self) -> List:
        if self.is_development:
            return self._hosts()
        else:
            return self._hosts(self.domain, self.parent_domain)

    def _load(self) -> None:
        self.domain = os.environ.get(self.DOMAIN_KEY, None)
        self.parent_domain = os.environ.get(self.PARENT_DOMAIN_KEY, None)
        self.sub_domain = os.environ.get(self.SUB_DOMAIN_KEY, self.DEFAULT_SUB_DOMAIN)

    def _origins(self, domain: str = None, sub: str = None, parent: str = None) -> List:
        if self.is_development:
            return [
                "http://localhost",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1"
            ]
        else:
            return [
                f'https://{domain}',
                f'https://app.{domain}',
                f'https://auth.{domain}',
                f'https://{sub}.{domain}',
                f'https://{parent}',
                f'https://app.{parent}',
                f'https://auth.{parent}',
                f'https://{sub}.{parent}'
            ]

    @staticmethod
    def _hosts(domain: str = None, parent: str = None) -> List:
        if domain:
            return [
                domain,
                f"*.{domain}",
                parent,
                f"*.{parent}"
            ]
        else:
            return ['localhost', '127.0.0.1']
