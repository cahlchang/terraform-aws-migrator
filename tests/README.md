# Test Directory Structure Guidelines

## Overview

This document outlines the rules and conventions for organizing test files in the terraform-aws-migrator project.

## Directory Structure

```
tests/
├── README.md
├── conftest.py              # Shared pytest fixtures and configuration
├── fixtures/                # Test data files
│   ├── lb_test.tfstate
│   ├── lb_unmanaged_test.tfstate
│   └── test.tfstate
├── integration/            # Integration tests
│   └── ...
└── unit/                  # Unit tests
    ├── collectors/        # Tests for collectors package
    │   ├── aws_iam/      # Tests for IAM collectors
    │   ├── aws_network/  # Tests for network collectors
    │   └── aws_storage/  # Tests for storage collectors
    ├── formatters/       # Tests for formatters package
    ├── generators/       # Tests for generators package
    └── utils/           # Tests for utils package
```

## Rules and Conventions

### Directory Structure

1. Test files should mirror the structure of the source code:
   - For each source file in `terraform_aws_migrator/`, there should be a corresponding test file in `tests/unit/`
   - Example: `terraform_aws_migrator/collectors/aws_network/network.py` → `tests/unit/collectors/aws_network/test_network.py`

2. Test types should be separated:
   - `unit/`: Unit tests that test individual components in isolation
   - `integration/`: Tests that verify multiple components working together

### File Naming

1. Test files should be prefixed with `test_`:
   - Example: `test_network.py`, `test_vpc.py`

2. Test classes should be suffixed with `Test`:
   - Example: `class NetworkCollectorTest`

3. Test methods should be prefixed with `test_`:
   - Example: `def test_collect_resources()`

### Fixtures

1. Common fixtures should be placed in `conftest.py`
2. Test data files should be placed in the `fixtures/` directory
3. Fixture files should be named descriptively:
   - Example: `lb_test.tfstate` for Load Balancer test state

### Test Organization

1. Tests should be organized by functionality:
   ```python
   class NetworkCollectorTest:
       """Tests for NetworkCollector class."""
       
       def test_collect_resources(self):
           """Test normal resource collection."""
           pass
           
       def test_collect_resources_error(self):
           """Test error handling during collection."""
           pass
   ```

2. Group related tests in classes:
   - One test class per source class/module
   - Use descriptive class names

### Documentation

1. Each test file should have a module docstring explaining what it tests
2. Test classes should have class docstrings
3. Complex test methods should have method docstrings

### Best Practices

1. Use meaningful test names that describe the scenario being tested:
   ```python
   def test_collect_resources_with_empty_response():
   def test_collect_resources_with_invalid_credentials():
   ```

2. Follow the Arrange-Act-Assert pattern:
   ```python
   def test_collect_resources():
       # Arrange
       collector = NetworkCollector()
       mock_response = {...}
       
       # Act
       result = collector.collect()
       
       # Assert
       assert len(result) == 1
   ```

3. Use appropriate assertions:
   - Use `assert` statements with meaningful messages
   - Use pytest's built-in assertions when appropriate

4. Mock external dependencies:
   ```python
   @pytest.fixture
   def mock_aws_client():
       with mock.patch('boto3.client') as mock_client:
           yield mock_client
   ```

### Coverage

1. Aim for high test coverage (>90% for new code)
2. Test both success and error cases
3. Include edge cases in test scenarios

## Example

```python
"""Tests for the NetworkCollector class."""

import pytest
from unittest.mock import MagicMock

from terraform_aws_migrator.collectors.aws_network.network import NetworkCollector

class TestNetworkCollector:
    """Test cases for NetworkCollector."""
    
    def test_collect_resources(self, mock_collector):
        """Test successful collection of network resources."""
        # Test implementation
        
    def test_collect_resources_error(self, mock_collector):
        """Test error handling during resource collection."""
        # Test implementation
```

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/collectors/aws_network/test_network.py

# Run with coverage
pytest --cov=terraform_aws_migrator
