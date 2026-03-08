# Testing Documentation for Agoge API

This document serves as a comprehensive guide to help you understand, write, run, and debug tests in the `main_app/api/tests` directory using Pytest and PyCharm. It covers various aspects of testing, including fixtures, authentication overrides, using the test client, and more.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Running and Debugging Tests from PyCharm Configurations](#running-and-debugging-tests-from-pycharm-configurations)
3. [Getting Started with Your First Test](#getting-started-with-your-first-test)
4. [Understanding Fixtures](#understanding-fixtures)
5. [Overriding Authentication](#overriding-authentication)
6. [Using the Test Client Against APIs](#using-the-test-client-against-apis)
7. [Order of Testing Labs](#order-of-testing-labs)
8. [Connecting to Google Cloud Project](#connecting-to-google-cloud-project)
9. [Valid Test Projects](#valid-test-projects)
10. [Reading Test Output for Success and Failure](#reading-test-output-for-success-and-failure)
11. [Reading Logs When Running Tests](#reading-logs-when-running-tests)
12. [Other Aspects of Testing](#other-aspects-of-testing)

---

## Prerequisites

- **Python 3.9+**
- **Pytest** installed from requirements.txt
- **PyCharm IDE** (recommended for debugging)
- Access to **Google Cloud Platform** with the necessary permissions
- Environment variable `GOOGLE_IMPERSONATED_SERVICE_ACCOUNT` set up for GCP authentication

---

## Running and Debugging Tests from PyCharm Configurations

### Running Tests

1. **Create a PyCharm Run Configuration**:
   - Go to **Run > Edit Configurations**.
   - Click the **+** button and select **Python tests > pytest**.
   - Set the **Target** module name to the test you wish to run (e.g. main_app.api.tests.test_simple_lab)
   - You can add additional Pytest command-line options in the **Additional Arguments** field of the configuration.

2. **Ensure you have account impersonation set up correctly**:  
   The application automatically uses the account impersonation specified in `main_app/api/.env`. To change this (or set it up for the first time), run the setup script and follow the impersonation prompts, then select **Exit**. This script also authenticates you with the correct Google account authorized for impersonation and sets the needed Google API authentication token on your local machine. For new cloud projects, run `setup.py` to create a new service account, enable impersonation, and then add the project details to `build_files/cloud_deployment/environments.json`.

3. **Run the Configuration**:
   - Click the **Run** button or press **Shift+F10**.

### Debugging Tests

1. **Set Breakpoints**:
   - Click in the gutter next to the line numbers to set breakpoints in your test code.

2. **Debug the Configuration**:
   - Right-click on the test or configuration and select **Debug**.
   - Alternatively, press **Shift+F9**.

3. **Use the Debugger**:
   - Step through the code using **Step Over (F8)**, **Step Into (F7)**, or **Step Out (Shift+F8)**.
   - Inspect variables and evaluate expressions in the **Debug** tool window.

---

## Getting Started with Your First Test

1. **Create a Test File**: All test files should be named with the prefix `test_`, for example, `test_my_feature.py`.

2. **Import Required Modules**: Import `pytest` and any other modules you need for your tests.

   ```python
   import pytest
   ```

3. **Write Test Functions**: Define functions that start with `test_`. Each function represents a test case.

   ```python
   def test_example():
       assert 1 + 1 == 2
   ```

4. **Run the Test**: Execute the test using the command line:

   ```bash
   pytest path/to/test_my_feature.py
   ```

---

## Understanding Fixtures

**Fixtures** are a way to provide test functions with data or objects they need to run. They can set up state before a test runs and clean up after the test completes.

- **Defining a Fixture**: Use the `@pytest.fixture` decorator.

  ```python
  @pytest.fixture
  def sample_data():
      return {"key": "value"}
  ```

- **Using Fixtures in Tests**: Include the fixture name as a parameter in your test function.

  ```python
  def test_using_fixture(sample_data):
      assert sample_data["key"] == "value"
  ```

- **Fixture Scopes**: You can define the scope of a fixture (`function`, `module`, `class`, `package`, `session`) to control its lifespan.

---

## Using Fixtures in `conftest.py` for authentication and database setup

The `conftest.py` file in this project contains reusable fixtures for setting up shared resources and configurations during tests. Fixtures help streamline test preparation by defining preconditions and providing clean, reusable test data. Here’s an overview of some fundamental fixtures in this file:

1. **`env_dict`**  
   - Provides an environment dictionary derived from the Google Cloud environment using `CloudEnv`.  
   - This is useful for sharing environment-specific configuration across tests.

2. **`db`**  
   - Creates and provides a Firestore database instance using `DocumentDatabaseFactory`.  
   - Centralizes database access for tests that require Firestore interactions.

3. **`check_test_project_id`**  
   - Validates that tests are executed on a permitted Google Cloud project (`VALID_TEST_PROJECTS`).  
   - Prevents accidental operations on non-test environments by asserting the project ID.

4. **`test_client`**  
   - Sets up a FastAPI `TestClient` with necessary dependency overrides.  
   - Mocks the `get_current_user` dependency to impersonate an admin user for secure test execution.  
   - Ensures clean-up of overridden dependencies after each session.

5. **`override_get_current_user_admin`**  
   - Overrides the `get_current_user` dependency to simulate an authenticated admin user.  
   - Configures permissions and settings to match admin roles for tests that require elevated access.

By using these fixtures, tests can focus on verifying functionality without duplicating setup logic. The use of `scope='session'` ensures that resources like the database and environment configurations are initialized only once per test session.

---

## Using the Test Client Against APIs

FastAPI provides a `TestClient` for testing API endpoints that is setup in the conftest.py file at the session scope. This client allows you to make requests to your API endpoints and assert the responses.

- **Make API Calls in Tests**:

  ```python
  def stop_workout_helper(test_client, workout_id: str):
    """
    Helper that stops a workout using the test client.
    """
    json_payload = {"action": "stop"}
    response = test_client.put(
        f"/workouts/{workout_id}",
        json=json_payload,
        headers={"Host": "127.0.0.1"},
    )
    assert response.status_code == 200, f"Failed to stop workout {workout_id}."
  ```

---

## Order of Testing Labs

Tests can depend on the results of previous tests. Pytest allows you to specify dependencies using the `pytest-dependency` plugin.

- **Mark Test Dependencies**:

  ```python
  import pytest

  @pytest.mark.dependency()
  def test_first():
      assert True

  @pytest.mark.dependency(depends=["test_first"])
  def test_second():
      assert True
  ```

In the context of lab tests, ensure that resource creation tests run before tests that depend on those resources.

---

## Valid Test Projects

Tests should only run against valid test projects to prevent accidental modification of production data.

- **List of Valid Projects**: Defined in `conftest.py` under `VALID_TEST_PROJECTS`.

  ```python
  VALID_TEST_PROJECTS = ['test-project-1', 'test-project-2']
  ```

- **Assertion in Fixtures**: A fixture checks that the current project is valid.

  ```python
  assert env.project in VALID_TEST_PROJECTS, "Invalid test project ID."
  ```

- **Adding New Test Projects**: Update the `VALID_TEST_PROJECTS` list as needed.

---
---

## Reading Test Output for Success and Failure

Understanding the output of your tests is crucial for diagnosing issues and ensuring your code behaves as expected. This section will guide you through interpreting Pytest output to determine which tests have passed or failed, and why.

### Basic Pytest Output

When you run tests using Pytest, the output in the console provides a concise summary of the test execution. Here's an example of what the output might look like:

```bash
============================= test session starts =============================
collected 5 items

test_lab.py .....                                                      [100%]

============================== 5 passed in 2.34s ==============================
```

#### Explanation:

- **Collected 5 items**: Pytest has found and is running 5 tests.
- **Dots (`.`)**: Each dot represents a passed test.
- **Percentage Indicator (`[100%]`)**: Shows the progress of the test run.
- **Final Summary**: Indicates that all 5 tests have passed and shows the total execution time.

### Interpreting Test Results

#### Symbols Used:

- **`.` (Dot)**: Test passed.
- **`F`**: Test failed.
- **`E`**: An error occurred outside of an assertion (e.g., exception in setup code).
- **`s`**: Test was skipped.
- **`x`**: Test was expected to fail and did fail (expected failure).
- **`X`**: Test was expected to fail but passed (unexpected success).

#### Example of Failures:

```bash
============================= test session starts =============================
collected 5 items

test_lab.py ..F..                                                      [100%]

================================== FAILURES ===================================
________________________________ test_example _________________________________

    def test_example():
>       assert 1 == 2
E       assert 1 == 2

test_lab.py:10: AssertionError
========================== 1 failed, 4 passed in 2.50s =========================
```

#### Explanation:

- **`F`**: Indicates that `test_example` has failed.
- **Failure Details**: Pytest provides the traceback, showing where the assertion failed.
- **AssertionError**: The specific error that caused the test to fail.

### Detailed Failure Reports

When a test fails, Pytest provides a detailed report including:

- **Test Name**: The function name of the failed test.
- **Location**: File name and line number where the failure occurred.
- **Captured Output**: Any output that was printed to the console during the test.
- **Traceback**: The stack trace showing the sequence of calls that led to the error.
- **Error Message**: The specific assertion or exception that caused the failure.

#### Example with Captured Log Output:

```bash
================================== FAILURES ===================================
________________________________ test_connection ______________________________

env_dict = {...}, built_workout = 'workout123'

    @pytest.mark.dependency(depends=["test_student_join"])
    def test_connection(env_dict, built_workout):
        logger.info("Testing connection for workout %s", built_workout)
        # Test code that fails
>       assert connect_to_server(built_workout) == True
E       AssertionError: assert False == True

test_lab.py:45: AssertionError
---------------------------- Captured log call -----------------------------
INFO     test_lab:test_lab.py:42 Testing connection for workout workout123
========================== 1 failed, 4 passed in 3.10s =========================
```

#### Explanation:

- **Captured Log Call**: Shows any logs that were emitted during the test execution.
- **AssertionError Details**: Indicates that `connect_to_server` returned `False` instead of `True`.

### Skipped and XFailed Tests

Tests can be skipped or marked as expected failures.

#### Skipped Test Example:

```bash
test_lab.py ..s..                                                      [100%]

========================== 1 skipped, 4 passed in 2.00s ========================
```

- **`s`**: Indicates that a test was skipped.
- **Reason for Skipping**: Pytest can display the reason if provided in the test.

#### Expected Failure (XFail) Example:

```bash
test_lab.py ..x..                                                      [100%]

===================== 1 xfailed, 4 passed in 2.00s ============================
```

- **`x`**: Test was expected to fail and did fail.

### Summary of Test Outcomes

At the end of the test run, Pytest provides a summary:

- **`X passed`**: Number of tests that passed successfully.
- **`X failed`**: Number of tests that failed.
- **`X errors`**: Number of tests that had errors.
- **`X skipped`**: Number of tests that were skipped.
- **`X xfailed`**: Number of expected failures.
- **`X xpassed`**: Number of unexpected passes.

### Tips for Analyzing Failures

1. **Read the Traceback Carefully**: It shows the exact point of failure.
2. **Check Captured Output**: Logs and print statements can provide context.
3. **Look at Variable Values**: Use logging or debugging to inspect variable states at failure points.
4. **Use Verbose Mode**: Run tests with the `-v` flag for more detailed output.

   ```bash
   pytest -v test_lab.py
   ```

   **Verbose Output Example**:

   ```bash
   test_lab.py::test_build_unit PASSED                                    [ 20%]
   test_lab.py::test_student_join PASSED                                  [ 40%]
   test_lab.py::test_student_connection FAILED                            [ 60%]
   test_lab.py::test_stop_workout SKIPPED                                 [ 80%]
   test_lab.py::test_delete_unit SKIPPED                                  [100%]
   ```

5. **Run a Specific Test**: Focus on a failing test by running it directly.

   ```bash
   pytest test_lab.py::test_student_connection
   ```
   
---


## Reading Logs When Running Tests

Proper logging helps in diagnosing test failures and understanding test execution flow.

- **Configure Logging in Tests**:

  ```python
  import logging

  logger = logging.getLogger(__name__)
  logging.basicConfig(level=logging.INFO)
  ```

- **Use Logging Statements**:

  ```python
  logger.info("Starting test for feature X")
  logger.debug("Variable Y has value: %s", y)
  ```

- **View Logs**: When running tests, logs will be printed to the console or can be configured to write to a file.

---

## Other Aspects of Testing

### Assertions

- **Basic Assertion**:

  ```python
  assert condition, "Optional failure message"
  ```

- **Comparing Values**:

  ```python
  assert actual == expected
  ```

### Handling Failures

- **Fail a Test Manually**:

  ```python
  pytest.fail("Test failed due to unexpected condition")
  ```

### Yield Statements in Fixtures

- **Using `yield` for Setup and Teardown**:

  ```python
  @pytest.fixture
  def resource():
      # Setup code
      yield resource_instance
      # Teardown code
  ```

### Helper Functions

- **Define Reusable Functions**: Place common logic in helper functions within the test module or a utilities module.

  ```python
  def create_test_user():
      return User(name="Test User")
  ```

### Cleanup Functions

- **Ensure Resources Are Cleaned Up**: Use fixtures or teardown methods to delete resources created during tests.

  ```python
  @pytest.fixture
  def temporary_resource():
      resource = create_resource()
      yield resource
      delete_resource(resource)
  ```

---

## Conclusion

This guide provides an overview of how to effectively write, run, and debug tests in the `main_app/api/tests` directory. By following the practices outlined above, you can ensure that your tests are robust, maintainable, and efficient.

For any further questions or clarifications, please refer to the [Pytest documentation](https://docs.pytest.org/) or reach out to the development team.**