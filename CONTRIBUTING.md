# Contributing to OpenInsure

Thank you for your interest in contributing to OpenInsure! This document provides guidelines for contributing to the project.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you agree to uphold this code.

## Development Setup

### Prerequisites

- Python 3.12+
- Git
- An IDE with Python support (VS Code recommended)

### Getting Started

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/openinsure.git
cd openinsure

# Install in development mode
pip install -e ".[dev]"

# Verify setup
pytest tests/ -v
ruff check src/ tests/
mypy src/openinsure/
```

## Development Workflow

### Branch Strategy

- `main` — Production-ready code. Protected branch.
- `feat/<issue>-<description>` — Feature branches
- `fix/<issue>-<description>` — Bug fix branches
- `docs/<description>` — Documentation changes

### Process

1. **Create an issue** describing the change
2. **Create a feature branch** from `main`
3. **Write tests first** (TDD approach)
4. **Implement the change**
5. **Ensure all quality gates pass**
6. **Submit a PR** with a clear description
7. **Wait for CI** to pass
8. **Address review feedback**

### Quality Gates

All PRs must pass these checks:

| Gate | Command | Requirement |
|------|---------|-------------|
| Tests | `pytest tests/ -v` | All passing |
| Lint | `ruff check src/ tests/` | No errors |
| Format | `ruff format --check src/ tests/` | Compliant |
| Types | `mypy src/openinsure/` | No errors |
| Security | `bandit -r src/openinsure/` | No high/critical |
| Coverage | `pytest --cov --cov-fail-under=80` | ≥80% |

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add cyber insurance rating engine
fix: correct premium calculation for multi-coverage policies
docs: update API documentation for submissions endpoint
test: add integration tests for policy binding workflow
refactor: extract common validation logic to base agent
```

## Architecture Guidelines

### Domain-Driven Design

- Domain entities live in `src/openinsure/domain/` (Pydantic models)
- Business logic in `src/openinsure/services/`
- Infrastructure adapters in `src/openinsure/infrastructure/`
- API layer in `src/openinsure/api/` (thin, delegates to services)

### Insurance Domain Conventions

- All monetary values: `Decimal` (never `float`)
- All entity IDs: `UUID`
- All timestamps: ISO 8601 UTC
- Domain events for every state change
- Decision records for every AI decision

### Agent Development

- All agents inherit from `InsuranceAgent` base class
- Every agent decision produces a `DecisionRecord`
- Agents must declare their capabilities
- Agents must respect authority limits
- Escalation below confidence threshold is automatic

## License

By contributing, you agree that your contributions will be licensed under AGPL-3.0.
