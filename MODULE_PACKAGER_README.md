# Module Dependency Packager

A Python script that performs full dependency analysis on specified modules and packages them into portable ZIP archives for deployment.

## Features

- **Automatic Dependency Discovery**: Traces and collects all required modules and libraries
- **Transitive Dependencies**: Ensures no dependencies are missed by following the entire dependency tree
- **Local Module Focus**: Specifically targets modules within the project structure
- **Portable ZIP Archives**: Creates self-contained deployment bundles
- **Cross-Environment Compatibility**: Simplifies distribution and ensures reproducibility

## Usage

### Command Line Interface

```bash
# Package a module (venv_path is required)
python module_packager.py mcp_hubspot_connector /var/python3.11/silvaengine/env

# Specify output directory
python module_packager.py mcp_hubspot_connector /var/python3.11/silvaengine/env --output-dir ./packages
```

### Programmatic Usage

```python
from module_packager import ModulePackager

# Initialize packager (venv_path is required)
packager = ModulePackager('/var/python3.11/silvaengine/env')

# Package a module
zip_path = packager.create_package('mcp_hubspot_connector', output_dir='./packages')

print(f"Package created: {zip_path}")
print(f"Local dependencies: {packager.dependencies}")
print(f"External dependencies: {packager.external_deps}")
```

## Examples

### Package MCP Connectors

```bash
# Package HubSpot connector
python module_packager.py mcp_hubspot_connector /var/python3.11/silvaengine/env

# Package ResolvePay connector
python module_packager.py mcp_resolvepay_connector /var/python3.11/silvaengine/env
```

### Output Structure

The generated ZIP file will contain all dependencies at the same level as the target module:
```
mcp_hubspot_connector.zip
├── mcp_hubspot_connector/
│   ├── __init__.py
│   ├── handlers/
│   └── ...
├── silvaengine_base/
│   └── ...
├── requests/
│   └── ...
├── urllib3/
│   └── ...
├── other_local_dependencies/
│   └── ...
└── package_metadata.dist-info/
    └── ...
```

## How It Works

1. **Module Discovery**: Starts with the target module and recursively discovers dependencies
2. **Import Analysis**: Parses Python files using AST to find import statements
3. **Local Module Detection**: Identifies which imports are local modules within the project
4. **File Collection**: Gathers all Python files for the module and its dependencies
5. **ZIP Creation**: Packages everything into a compressed archive with proper directory structure

## Requirements

- Python 3.6+
- Standard library modules only (no external dependencies)

## Supported Module Types

- Directory-based modules (packages)
- Single-file modules
- Nested package structures
- Modules with complex dependency trees

## Output

- Creates `{module_name}.zip` in the specified output directory
- Logs all included dependencies and files
- Maintains original directory structure within the ZIP

## Error Handling

- Gracefully handles missing modules
- Logs warnings for unresolvable dependencies
- Continues processing even if some dependencies fail
- Provides detailed error messages for troubleshooting