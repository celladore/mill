# Contributing Guidelines

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/mill.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Run tests: `make test`
6. Run linting: `make lint`
7. Commit your changes: `git commit -m "Add feature: description"`
8. Push to your fork: `git push origin feature/your-feature-name`
9. Create a Pull Request

## Code Style

### Python

- Follow PEP 8 style guide
- Use Black for formatting: `black xtox/`
- Use isort for imports: `isort xtox/`
- Maximum line length: 88 characters
- Type hints required for all functions

### JavaScript/React

- Use ESLint configuration
- Follow React best practices
- Use functional components with hooks
- Prefer named exports

## Commit Messages

Follow conventional commits format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Build process or auxiliary tool changes

Example:
```
feat(audio): add batch conversion API

Implements POST /api/batch/convert-audio endpoint for
converting multiple audio files in a single request.

Closes #123
```

## Testing

- Write tests for all new features
- Maintain or improve test coverage
- Run tests before submitting PR: `make test`
- Include integration tests for API endpoints

## Pull Request Process

1. Update documentation if needed
2. Add tests for new functionality
3. Ensure all tests pass
4. Update CHANGELOG.md
5. Request review from maintainers

## Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] No security vulnerabilities introduced
- [ ] Error handling is appropriate
- [ ] Performance considerations addressed

## Reporting Issues

Use GitHub Issues with:
- Clear description
- Steps to reproduce
- Expected vs actual behavior
- Environment details
- Relevant logs/error messages

## Security Issues

Report security vulnerabilities privately to security@example.com
Do not create public issues for security vulnerabilities.

