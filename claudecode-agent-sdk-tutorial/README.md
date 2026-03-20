# CC Agent Tutorial

A tutorial project for building agents with Claude Code.

## Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) package manager

## Setup

1. **Create virtual environment and install dependencies**

```bash
uv venv
uv sync
```

2. **Configure environment variables**

```bash
cp .env.example .env
```

Edit `.env` and add your API keys and configuration.

3. **Run the application**

```bash
uv run main.py
```

## Project Structure

- `main.py` - Main application entry point
- `tools.py` - Tool definitions and utilities
- `.env.example` - Example environment configuration
- `pyproject.toml` - Project dependencies and metadata
