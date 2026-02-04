# Testing Guide

This directory contains the comprehensive test suite for the Network Configuration Management System.

## Test Structure

```
tests/
├── __init__.py                    # Test package initialization
├── conftest.py                    # Shared pytest fixtures
├── fixtures/                      # Test data files
│   ├── test_inventory.yaml       # Sample inventory for testing
│   ├── test_template.j2          # Sample Jinja2 template
│   └── test_backup.cfg           # Sample backup configuration
├── integration/                   # Integration tests
│   ├── __init__.py
│   └── test_full_workflow.py     # End-to-end workflow tests
├── test_inventory_loader.py       # Inventory module tests
├── test_template_engine.py        # Template engine tests
├── test_utils.py                  # Utility functions tests
├── test_connection_manager.py     # Connection manager tests (mocked)
├── test_backup.py                 # Backup module tests
├── test_deployment.py             # Deployment module tests
└── test_rollback.py               # Rollback module tests
```

## Running Tests

### Prerequisites

Install testing dependencies:

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_inventory_loader.py
```

### Run Specific Test Class

```bash
pytest tests/test_inventory_loader.py::TestInventoryLoader
```

### Run Specific Test Method

```bash
pytest tests/test_inventory_loader.py::TestInventoryLoader::test_load_inventory
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Extra Verbose Output (shows test docstrings)

```bash
pytest -vv
```

## Test Categories

Tests are organized using pytest markers:

### Unit Tests

Fast, isolated tests with mocked dependencies:

```bash
pytest -m unit
```

### Integration Tests

Tests that integrate multiple components:

```bash
pytest -m integration
```

### Slow Tests

Long-running tests (integration, end-to-end):

```bash
pytest -m slow
```

### Tests Requiring Lab Environment

Tests that need Containerlab running:

```bash
pytest -m requires_lab
```

### Exclude Specific Markers

```bash
# Run all tests except slow ones
pytest -m "not slow"

# Run all tests except those requiring lab
pytest -m "not requires_lab"
```

## Coverage Reports

### Generate Coverage Report

```bash
pytest --cov=src --cov-report=term
```

### Generate HTML Coverage Report

```bash
pytest --cov=src --cov-report=html
```

Then open `htmlcov/index.html` in your browser.

### Generate Coverage with Missing Lines

```bash
pytest --cov=src --cov-report=term-missing
```

### Combined Coverage Report

```bash
pytest --cov=src --cov-report=html --cov-report=term-missing
```

## Test Organization

### Unit Tests

- **test_inventory_loader.py**: Tests for inventory loading, device filtering, settings
- **test_template_engine.py**: Tests for Jinja2 template rendering, validation
- **test_utils.py**: Tests for utility functions (timestamps, file operations, formatting)
- **test_connection_manager.py**: Tests for SSH connection handling with mocked connections
- **test_backup.py**: Tests for backup operations with mocked SSH
- **test_deployment.py**: Tests for configuration deployment with mocked SSH
- **test_rollback.py**: Tests for rollback operations with mocked SSH

### Integration Tests

- **test_full_workflow.py**: End-to-end tests combining multiple modules

## Writing New Tests

### Test File Naming

- Test files must start with `test_`
- Example: `test_new_module.py`

### Test Class Naming

- Test classes must start with `Test`
- Example: `TestNewModule`

### Test Method Naming

- Test methods must start with `test_`
- Use descriptive names: `test_<function>_<scenario>`
- Examples:
  - `test_connect_success`
  - `test_connect_timeout_failure`
  - `test_backup_device_connection_failure`

### Using Fixtures

Shared fixtures are defined in `conftest.py`:

```python
def test_example(test_inventory_file, temp_dir, mock_device):
    """Test using shared fixtures."""
    # test_inventory_file: Path to test inventory YAML
    # temp_dir: Temporary directory (auto-cleanup)
    # mock_device: Mock device dictionary
    pass
```

### Mocking External Dependencies

Always mock SSH connections and network operations:

```python
from unittest.mock import patch, MagicMock

@patch('src.connection_manager.ConnectHandler')
def test_with_mock_connection(mock_connect_handler, mock_device):
    """Test with mocked SSH connection."""
    mock_connection = MagicMock()
    mock_connection.send_command.return_value = "output"
    mock_connect_handler.return_value = mock_connection

    # Your test code here
```

### Test Structure

Follow the Arrange-Act-Assert pattern:

```python
def test_example():
    """Test description explaining what this tests."""
    # Arrange: Set up test data and mocks
    device = {'name': 'test', 'ip': '192.168.1.1'}

    # Act: Execute the code being tested
    result = function_to_test(device)

    # Assert: Verify expected outcomes
    assert result['success'] is True
    assert result['device_name'] == 'test'
```

### Adding Test Markers

```python
import pytest

@pytest.mark.unit
def test_unit_example():
    """Fast unit test."""
    pass

@pytest.mark.integration
def test_integration_example():
    """Integration test combining modules."""
    pass

@pytest.mark.slow
def test_slow_example():
    """Long-running test."""
    pass

@pytest.mark.requires_lab
def test_with_lab():
    """Test requiring Containerlab environment."""
    pass
```

## Testing Best Practices

### 1. Test Independence

Tests should be independent and repeatable:

```python
# Good: Uses fixtures with cleanup
def test_with_fixture(temp_dir):
    filepath = os.path.join(temp_dir, 'test.txt')
    # temp_dir is automatically cleaned up

# Bad: Creates files without cleanup
def test_without_fixture():
    filepath = 'test.txt'
    # File persists after test
```

### 2. Descriptive Test Names

```python
# Good: Clear what is being tested
def test_connect_fails_with_invalid_credentials()

# Bad: Unclear purpose
def test_connect_2()
```

### 3. One Assertion Per Test (When Practical)

```python
# Good: Tests one specific behavior
def test_device_name_extracted():
    device = {'name': 'router1', 'ip': '10.0.0.1'}
    assert device['name'] == 'router1'

def test_device_ip_extracted():
    device = {'name': 'router1', 'ip': '10.0.0.1'}
    assert device['ip'] == '10.0.0.1'
```

### 4. Test Both Success and Failure Cases

```python
def test_backup_device_success():
    """Test successful backup."""
    # Test happy path

def test_backup_device_connection_failure():
    """Test backup with connection failure."""
    # Test error handling

def test_backup_device_invalid_device():
    """Test backup with invalid device."""
    # Test validation
```

### 5. Mock External Dependencies

```python
# Good: Mocks SSH connection
@patch('src.backup.ConnectionManager')
def test_backup_with_mock(mock_conn):
    # No real SSH connection

# Bad: Tries to make real SSH connection
def test_backup_real_connection():
    # Fails if device not reachable
```

### 6. Use Fixtures for Common Setup

```python
# Good: Reusable fixture
@pytest.fixture
def test_device():
    return {'name': 'test', 'ip': '192.168.1.1'}

def test_a(test_device):
    # Use fixture

def test_b(test_device):
    # Reuse same fixture

# Bad: Duplicate setup
def test_a():
    device = {'name': 'test', 'ip': '192.168.1.1'}

def test_b():
    device = {'name': 'test', 'ip': '192.168.1.1'}  # Duplicated
```

## Common Issues and Solutions

### Import Errors

If you get import errors, ensure you're running pytest from the project root:

```bash
# From project root
pytest

# Not from tests directory
cd tests  # Don't do this
pytest    # Will fail with import errors
```

### Fixture Not Found

Ensure fixtures are defined in `conftest.py` or imported correctly.

### Mock Not Working

Ensure you're patching the correct location:

```python
# Patch where it's used, not where it's defined
@patch('src.backup.ConnectionManager')  # Correct
# not
@patch('netmiko.ConnectHandler')  # Wrong location
```

---
