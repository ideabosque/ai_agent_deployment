### Private modules.
echo "y" | pip uninstall ai_knowledge_engine && pip install git+ssh://git@github.com/ideabosque/ai_knowledge_engine.git@dev#egg=ai_knowledge_engine

python3.11 cloudformation_stack.py .env silvaengine-microcore-ai-knowledge