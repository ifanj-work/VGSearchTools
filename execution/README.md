# Execution

This directory contains deterministic Python scripts that **do the work**.

## Purpose

Execution scripts handle:

- API calls
- Data processing
- File operations
- Database interactions

## Principles

- **Deterministic**: Same input = same output
- **Reliable**: Proper error handling
- **Testable**: Well-commented and modular
- **Fast**: Optimized for performance

## Environment

- Environment variables and API tokens are stored in `.env` (root directory)
- Scripts should be called by the orchestration layer (AI agent) based on directives
- Never hardcode credentials or sensitive data

## Best Practices

- Use clear function names
- Add comprehensive comments
- Handle errors gracefully
- Log important operations
- Return structured data
