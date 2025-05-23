#!/bin/bash

# Check for environment file argument
if [ -z "$1" ]; then
  echo "Usage: $0 <env_file_path>"
  exit 1
fi

ENV_FILE="$1"

### Private modules.
echo "y" | pip uninstall ai_knowledge_engine && pip install git+ssh://git@github.com/ideabosque/ai_knowledge_engine.git@main#egg=ai_knowledge_engine

python3.11 cloudformation_stack.py "$ENV_FILE" silvaengine-microcore-ai-knowledge