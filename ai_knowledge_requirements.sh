#!/bin/bash

# Check for environment file argument
if [ -z "$1" ]; then
  echo "Usage: $0 <env_file_path>"
  exit 1
fi

ENV_FILE="$1"
BRANCH="${2:-main}"

echo "y" | pip uninstall ShopifyAPI && pip install ShopifyAPI
echo "y" | pip uninstall redis && pip install redis
echo "y" | pip uninstall neo4j && pip install neo4j 
echo "y" | pip uninstall redis_stack_connector && pip install git+https://github.com/ideabosque/redis_stack_connector.git@main#egg=redis_stack_connector
echo "y" | pip uninstall neo4j_graph_connector && pip install git+https://github.com/ideabosque/neo4j_graph_connector.git@main#egg=neo4j_graph_connector
### Private modules.
echo "y" | pip uninstall ai_knowledge_engine && pip install git+ssh://git@github.com/ideabosque/ai_knowledge_engine.git@$BRANCH#egg=ai_knowledge_engine

python3.11 cloudformation_stack.py "$ENV_FILE" silvaengine-microcore-ai-knowledge