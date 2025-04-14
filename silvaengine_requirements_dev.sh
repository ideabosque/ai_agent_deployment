echo "y" | pip uninstall silvaengine_utility && pip install git+https://github.com/ideabosque/silvaengine_utility.git@main#egg=silvaengine_utility
echo "y" | pip uninstall event_triggers && pip install git+https://github.com/ideabosque/event_triggers.git@main#egg=event_triggers
echo "y" | pip uninstall silvaengine_base && pip install git+https://github.com/ideabosque/silvaengine_base.git@dev#egg=silvaengine_base
echo "y" | pip uninstall silvaengine_resource && pip install git+https://github.com/ideabosque/silvaengine_resouces.git@main#egg=silvaengine_resource
echo "y" | pip uninstall silvaengine_authorizer && pip install git+https://github.com/ideabosque/silvaengine_authorizer.git@dev#egg=silvaengine_authorizer
echo "y" | pip uninstall silvaengine_dynamodb_base && pip install git+https://github.com/ideabosque/silvaengine_dynamodb_base.git@main#egg=silvaengine_dynamodb_base
echo "y" | pip uninstall event_recorder && pip install git+https://github.com/ideabosque/event_recorder.git@main#egg=event_recorder
echo "y" | pip uninstall mutex_engine && pip install git+https://github.com/ideabosque/mutex_engine.git@main#egg=mutex_engine

python3.11 cloudformation_stack.py .env silvaengine