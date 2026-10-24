"""Frontend-only Cloud Build contexts carry the repository Markdown source."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_deployment.operations.app_install_updates.agoge_app import AgogeApp, Commands
from common.exceptions import AgogeValidationError


@pytest.mark.parametrize('result', [True, False, RuntimeError('build interrupted')])
def test_frontend_submission_contains_current_markdown_and_restores_staging(tmp_path, monkeypatch, result):
    monkeypatch.chdir(tmp_path)
    Path('docs/guides').mkdir(parents=True)
    Path('docs/README.md').write_text('# Documentation')
    Path('docs/guides/start.md').write_text('# Current guide')
    staged = Path('frontend/.help-docs')
    staged.mkdir(parents=True)
    (staged / 'previous.txt').write_text('prior staged content')
    app = object.__new__(AgogeApp)
    app.commands = Commands(SimpleNamespace())

    def submit(**kwargs):
        assert kwargs['target_dir'] == 'frontend/'
        assert (staged / 'README.md').read_text() == '# Documentation'
        assert (staged / 'guides/start.md').read_text() == '# Current guide'
        assert not (staged / 'previous.txt').exists()
        if isinstance(result, Exception):
            raise result
        return result

    app._deploy_cloud_run = Mock(side_effect=submit)
    if isinstance(result, Exception):
        with pytest.raises(RuntimeError, match='interrupted'):
            app._deploy_react()
    else:
        assert app._deploy_react() is result
    assert (staged / 'previous.txt').read_text() == 'prior staged content'
    assert not (staged / 'README.md').exists()


def test_missing_markdown_stops_before_cloud_build(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = object.__new__(AgogeApp)
    app.commands = Commands(SimpleNamespace())
    app._deploy_cloud_run = Mock()
    with pytest.raises(AgogeValidationError, match='docs/'):
        app._deploy_react()
    app._deploy_cloud_run.assert_not_called()
