### Private modules.
echo "y" | pip uninstall ai_knowledge_engine && pip install git+ssh://git@github.com/ideabosque/ai_knowledge_engine.git@dev#egg=ai_knowledge_engine
echo "y" | pip uninstall shopify_connector && pip install git+ssh://git@github.com/ideabosque/shopify_connector.git@main#egg=shopify_connector

python3.11 cloudformation_stack.py .env silvaengine-microcore-ai-knowledge