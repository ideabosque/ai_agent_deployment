#!/bin/bash

# Check for environment file argument
if [ -z "$1" ]; then
  echo "Usage: $0 <env_file_path>"
  exit 1
fi

ENV_FILE="$1"
BRANCH="${2:-main}"

echo "y" | pip uninstall httpx[http2] && pip install httpx[http2]
echo "y" | pip uninstall silvaengine_resource && pip install git+https://github.com/ideabosque/silvaengine_resouces.git@main#egg=silvaengine_resource
echo "y" | pip uninstall ai_mcp_daemon_engine && pip install git+ssh://git@github.com/ideabosque/ai_mcp_daemon_engine.git@$BRANCH#egg=ai_mcp_daemon_engine

python3.12 cloudformation_stack.py "$ENV_FILE" silvaengine-microcore-mcp