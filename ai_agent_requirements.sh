echo "y" | pip uninstall openai && pip install openai
echo "y" | pip uninstall toml && pip install toml
echo "y" | pip uninstall tiktoken && pip install tiktoken
echo "y" | pip uninstall ShopifyAPI && pip install ShopifyAPI
echo "y" | pip uninstall shopify_connector && pip install git+https://github.com/ideabosque/shopify_connector.git@main#egg=shopify_connector
echo "y" | pip uninstall silvaengine_resource && pip install git+https://github.com/ideabosque/silvaengine_resouces.git@main#egg=silvaengine_resource
echo "y" | pip uninstall ai_agent_core_engine && pip install git+https://github.com/ideabosque/ai_agent_core_engine.git@main#egg=ai_agent_core_engine
echo "y" | pip uninstall ai_agent_funct_base && pip install git+https://github.com/ideabosque/ai_agent_funct_base.git@main#egg=ai_agent_funct_base
echo "y" | pip uninstall ai_marketing_engine && pip install git+https://github.com/ideabosque/ai_marketing_engine.git@main#egg=ai_marketing_engine
echo "y" | pip uninstall ai_coordination_engine && pip install git+https://github.com/ideabosque/ai_coordination_engine.git@main#egg=ai_coordination_engine
echo "y" | pip uninstall ai_agent_handler && pip install git+https://github.com/ideabosque/ai_agent_handler.git@main#egg=ai_agent_handler
echo "y" | pip uninstall openai_agent_handler && pip install git+https://github.com/ideabosque/openai_agent_handler.git@main#egg=openai_agent_handler

### Private modules.
echo "y" | pip uninstall ai_knowledge_engine && pip install git+ssh://git@github.com/ideabosque/ai_knowledge_engine.git@main#egg=ai_knowledge_engine

python3.11 cloudformation_stack.py ideabosque.env silvaengine-microcore-ai-agent