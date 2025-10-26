#!/bin/bash

# Check for environment file argument
if [ -z "$1" ]; then
  echo "Usage: $0 <env_file_path>"
  exit 1
fi

ENV_FILE="$1"
BRANCH="${2:-main}"

echo "y" | pip uninstall toml && pip install toml
echo "y" | pip uninstall tiktoken && pip install tiktoken==0.11.0
echo "y" | pip uninstall openai && pip install openai
echo "y" | pip uninstall httpx[http2] && pip install httpx[http2]
echo "y" | pip uninstall shopify_connector && pip install git+https://github.com/ideabosque/shopify_connector.git@main#egg=shopify_connector
echo "y" | pip uninstall silvaengine_resource && pip install git+https://github.com/ideabosque/silvaengine_resouces.git@main#egg=silvaengine_resource
echo "y" | pip uninstall ai_agent_core_engine && pip install git+https://github.com/ideabosque/ai_agent_core_engine.git@$BRANCH#egg=ai_agent_core_engine
echo "y" | pip uninstall ai_marketing_engine && pip install git+https://github.com/ideabosque/ai_marketing_engine.git@$BRANCH#egg=ai_marketing_engine
echo "y" | pip uninstall ai_coordination_engine && pip install git+https://github.com/ideabosque/ai_coordination_engine.git@$BRANCH#egg=ai_coordination_engine
echo "y" | pip uninstall ai_agent_handler && pip install git+https://github.com/ideabosque/ai_agent_handler.git@$BRANCH#egg=ai_agent_handler
echo "y" | pip uninstall openai_agent_handler && pip install git+https://github.com/ideabosque/openai_agent_handler.git@$BRANCH#egg=openai_agent_handler
echo "y" | pip uninstall gemini_agent_handler && pip install git+https://github.com/ideabosque/gemini_agent_handler.git@$BRANCH#egg=gemini_agent_handler
echo "y" | pip uninstall anthropic_agent_handler && pip install git+https://github.com/ideabosque/anthropic_agent_handler.git@$BRANCH#egg=anthropic_agent_handler
echo "y" | pip uninstall ollama_agent_handler && pip install git+https://github.com/ideabosque/ollama_agent_handler.git@$BRANCH#egg=ollama_agent_handler
echo "y" | pip uninstall mcp_http_client && pip install git+https://github.com/ideabosque/mcp_http_client.git@$BRANCH#egg=mcp_http_client
echo "y" | pip uninstall app_core_engine && pip install git+https://github.com/ideabosque/app_core_engine.git@$BRANCH#egg=app_core_engine
echo "y" | pip uninstall shopify_app_engine && pip install git+https://github.com/ideabosque/shopify_app_engine.git@$BRANCH#egg=shopify_app_engine
echo "y" | pip uninstall mcp_proxy_engine && pip install git+https://github.com/ideabosque/mcp_proxy_engine.git@$BRANCH#egg=mcp_proxy_engine

python3.11 cloudformation_stack.py "$ENV_FILE" silvaengine-microcore-ai-agent
