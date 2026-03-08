import pytest
import glob
import logging
from typing import Optional
from fastapi import Security, Request
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.main import app
from api.dependencies import get_current_user, teacher_required
from common.constants.build_constants import BuildConstants
from common.models.users import AgogeUser, UserGroups
from common.utilities.gcp.cloud_env import CloudEnv
from common.document_database.factory import DocumentDatabaseFactory
from common.constants.database import DatabaseTypes, DATABASE_NAME
from common.constants.enumerators import ValidTestProjects


security = HTTPBearer()
logger = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def env_dict():
    """
    Fixture to provide environment dictionary from CloudEnv.
    """
    env = CloudEnv()
    return env.get_env()


@pytest.fixture(scope='session')
def fake_admin():
    """
    Fixture to provide a fake admin user.
    """
    # Construct the settings dictionary based on LMS
    settings = {
        BuildConstants.LMS.CANVAS.value: {
            'api': None,
            'url': None,
            'secret': None
        }
    }

    # Define the permissions
    permissions = {
        UserGroups.ADMIN.value: True,
        UserGroups.INSTRUCTOR.value: True,
    }

    # Instantiate the AgogeUser
    return AgogeUser(
        uid="admin-uid",
        email="admin@example.com",
        name="Admin User",
        permissions=permissions,
        settings=settings,
        timezone="UTC"
    )


@pytest.fixture(scope='session')
def db():
    """
    Fixture to provide a Firestore database instance.
    """
    db = DocumentDatabaseFactory.create_db_object(
        db_type=DatabaseTypes.firestore,
        database_name=DATABASE_NAME
    )
    return db


@pytest.fixture(scope='session', autouse=True)
def check_test_project_id():
    """
    Fixture to check that the test is running on a valid test project.
    """
    env = CloudEnv()
    assert env.project in {project.value for project in ValidTestProjects}, (
        f"The project ID '{env.project}' is not found in the list of valid test projects."
    )
    print(f"Using Google Cloud Project: {env.project}")


@pytest.fixture(scope="session")
def test_client():
    """
    Fixture to initialize and return a FastAPI TestClient instance with dependency overrides.
    """
    app.state.cloud_env = CloudEnv()
    app.dependency_overrides[get_current_user] = fake_admin
    client = TestClient(app)
    yield client
    # Clean up after test
    app.dependency_overrides = {}
    app.state.cloud_env = None


def setup_test_logging():
    """
    Configure logging for the tests (shared logger config).
    """
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


@pytest.fixture(scope='session', autouse=True)
def configure_logging():
    """
    Fixture to configure logging for the test session.
    Automatically runs at the start of the test session.
    """
    setup_test_logging()
    logger.info("Test logging configured.")


def pytest_addoption(parser):
    parser.addoption(
        "--agoge-debug",
        action="store_true",
        default=False,
        help="Enable debug mode (default: False)"
    )


@pytest.fixture(scope="module")
def debug(request):
    return request.config.getoption("--agoge-debug")
