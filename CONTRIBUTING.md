# Contributing to vMiner

First off, thank you for considering contributing to vMiner! It's people like you that make vMiner such a great tool for the VMware community.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps to reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed and what behavior you expected**
* **Include screenshots if relevant**
* **Include your environment details:**
  - vMiner version
  - Python version
  - Operating system
  - vCenter version

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* **Use a clear and descriptive title**
* **Provide a detailed description of the suggested enhancement**
* **Explain why this enhancement would be useful**
* **List any similar features in other tools**

### Pull Requests

* Fill in the required template
* Follow the Python style guide (PEP 8)
* Include appropriate test cases
* Update documentation as needed
* Ensure all tests pass

## Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/yourusername/vminer.git
   cd vminer
   ```

3. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # If available
   ```

5. Create a branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Coding Standards

* Follow PEP 8 style guide
* Write meaningful commit messages
* Add docstrings to functions and classes
* Keep functions focused and small
* Write unit tests for new features

## Testing

Before submitting a pull request, ensure:

* All existing tests pass
* New features have test coverage
* Code is properly formatted

```bash
# Run tests
pytest

# Check code style
flake8 .

# Format code
black .
```

## Documentation

* Update README.md if needed
* Add docstrings to new functions/classes
* Update relevant documentation in docs/
* Include code examples for new features

## Commit Messages

* Use the present tense ("Add feature" not "Added feature")
* Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
* Limit the first line to 72 characters
* Reference issues and pull requests

Example:
```
Add natural language support for datastore queries

- Implement fuzzy matching for datastore names
- Add support for capacity-based filters
- Update query engine tests

Fixes #123
```

## Questions?

Feel free to contact the maintainer:

**Vivek Yemky**
- Email: [vivek.yemky@gmail.com](mailto:vivek.yemky@gmail.com)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
