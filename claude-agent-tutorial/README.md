🛠️ Environment Setup
This project uses uv for fast Python package management.

1. Install uv
# MacOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
2. Create Virtual Environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
3. Install Dependencies
uv sync
