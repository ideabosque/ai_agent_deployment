#!/bin/bash

# Check for environment file argument
if [ -z "$1" ]; then
  echo "Usage: $0 <env_file_path>"
  exit 1
fi

ENV_FILE="$1"

echo "y" | pip uninstall slack_bolt && pip install slack_bolt
echo "y" | pip uninstall silvaengine_resource && pip install git+https://github.com/ideabosque/silvaengine_resouces.git@main#egg=silvaengine_resource
echo "y" | pip uninstall slack_bot_engine && pip install git+ssh://git@github.com/ideabosque/slack_bot_engine.git@main#egg=slack_bot_engine

python3.11 cloudformation_stack.py "$ENV_FILE" silvaengine-microcore-slack