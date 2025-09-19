# Module Dependency Packager

A Python script that performs comprehensive dependency analysis on specified modules and packages them into portable ZIP archives for deployment. Features multiple dependency resolution strategies and JSON-based configuration management.

## Features

- **Multiple Dependency Strategies**: AST-based imports analysis, metadata-based resolution, or automatic fallback
- **JSON Configuration**: Centralized configuration for virtual environments, module-specific extras, and exclusions
- **Transitive Dependencies**: Ensures no dependencies are missed by following the entire dependency tree
- **Module-Specific Extras**: Configure additional modules to include for specific packages
- **Exclusion Management**: Centrally manage excluded modules and standard library modules
- **Dependency Tree Visualization**: ASCII tree view of resolved dependencies with cycle detection
- **Portable ZIP Archives**: Creates self-contained deployment bundles
- **Cross-Environment Compatibility**: Simplifies distribution and ensures reproducibility

## Configuration

The packager uses a `mcp_packages.json` configuration file for centralized settings:

```json
{
  "venv_path": "/var/python3.11/silvaengine/env",
  "modules": {
    "mcp_hubspot_connector": {
      "include_extras": [
        "numpy.libs",
        "hubspot",
        "sklearn",
        "scikit_learn.libs",
        "scipy.libs",
        "threadpoolctl.py"
      ]
    },
    "requests": {
      "include_extras": ["urllib3", "certifi"]
    }
  },
  "excluded_modules": [
    "silvaengine_base",
    "silvaengine_authorizer",
    "pynamodb",
    "graphene"
  ],
  "stdlib_modules": [
    "os", "sys", "json", "logging", "datetime", "pathlib"
  ]
}
```

### Configuration Options

- **`venv_path`**: Default virtual environment path
- **`modules`**: Module-specific configuration with `include_extras` arrays
- **`excluded_modules`**: Modules to skip during packaging
- **`stdlib_modules`**: Standard library modules to ignore

### AWS Configuration (.env files)

AWS settings are stored in environment-specific files using lowercase variable names:

```bash
# .env.dev - Development environment
aws_access_key_id=your_dev_access_key_here
aws_secret_access_key=your_dev_secret_key_here
mcp_bucket=silvaengine-dev-packages
region_name=us-east-1
```

```bash
# .env.staging - Staging environment
aws_access_key_id=your_staging_access_key_here
aws_secret_access_key=your_staging_secret_key_here
mcp_bucket=silvaengine-staging-packages
region_name=us-east-1
```

```bash
# .env.prod - Production environment
aws_access_key_id=your_prod_access_key_here
aws_secret_access_key=your_prod_secret_key_here
mcp_bucket=silvaengine-prod-packages
region_name=us-east-1
```

**Setup Steps:**
1. Copy `.mcp.env.template` to environment-specific files (e.g., `.env.dev`, `.env.prod`)
2. Fill in your actual AWS credentials, bucket names, and regions for each environment
3. Ensure environment files are in your `.gitignore`
4. Use `--env-file` to specify which environment file to load

**Environment Variables:**
- **`aws_access_key_id`**: AWS access key for authentication
- **`aws_secret_access_key`**: AWS secret key for authentication
- **`mcp_bucket`**: S3 bucket name for package storage
- **`region_name`**: AWS region (e.g., "us-east-1")

**Environment File Usage:**
Each environment has its own file with the same variable names:
- **Development**: `--env-file .env.dev` (enables S3 sync to dev bucket)
- **Staging**: `--env-file .env.staging` (enables S3 sync to staging bucket)
- **Production**: `--env-file .env.prod` (enables S3 sync to prod bucket)
- **Custom**: `--env-file ./path/to/custom.env` (enables S3 sync to custom bucket)
- **No file**: Omit `--env-file` for local packaging only (no S3 sync)

## Usage

### Command Line Interface

```bash
# Package a module using config defaults
python module_packager.py mcp_hubspot_connector

# Override venv path
python module_packager.py mcp_hubspot_connector --venv-path /custom/venv/path

# Use custom config file
python module_packager.py mcp_hubspot_connector --config custom_config.json

# Specify output directory and strategy
python module_packager.py mcp_hubspot_connector --output-dir ./packages --strategy metadata

# Inspect dependencies without creating package
python module_packager.py mcp_hubspot_connector --inspect

# Include additional modules
python module_packager.py mcp_hubspot_connector --include-extras "extra1,extra2,extra3"

# Package without S3 sync (local only)
python module_packager.py mcp_hubspot_connector

# Package with custom settings (local only)
python module_packager.py mcp_hubspot_connector --output-dir ./dist --strategy metadata

# Package and sync to S3 using development environment file
python module_packager.py mcp_hubspot_connector --env-file .env.dev

# Package and sync to S3 using production environment file
python module_packager.py mcp_hubspot_connector --env-file .env.prod

# Package and sync to S3 using custom environment file path
python module_packager.py mcp_hubspot_connector --env-file ./environments/staging.env
```

### Dependency Resolution Strategies

- **`auto`** (default): Try metadata first, fallback to imports if no dependencies found
- **`metadata`**: Use pip-style Requires-Dist metadata only
- **`imports`**: Parse Python files with AST to discover imports

### Inspection Mode

Use `--inspect` to analyze dependencies without creating packages:

```bash
python module_packager.py mcp_hubspot_connector --inspect
```

This displays:
- Total distributions and top-level modules found
- List of all distributions and modules
- ASCII dependency tree with cycle detection
- Strategy used for resolution

### AWS S3 Sync

Use the `--env-file` option to automatically sync packages to S3 after creation:

```bash
# Sync to development environment
python module_packager.py mcp_hubspot_connector --env-file .env.dev

# Sync to production with specific output directory
python module_packager.py mcp_hubspot_connector --output-dir ./dist --env-file .env.prod

# Local packaging only (no S3 sync)
python module_packager.py mcp_hubspot_connector
```

**Prerequisites (for S3 sync only):**
- AWS CLI installed (`pip install awscli`)
- AWS settings configured in environment file (see AWS Configuration section above)
- Appropriate AWS permissions for S3 bucket access
- Use `--env-file` parameter to enable S3 sync

**Process:**
1. Package is created locally as normal
2. **If `--env-file` is specified:**
   - Environment variables are loaded from specified environment file
   - AWS settings are read from lowercase environment variables (`mcp_bucket`, `region_name`)
   - AWS credentials are applied from environment variables (`aws_access_key_id`, `aws_secret_access_key`)
   - AWS CLI uploads the ZIP file directly to the configured S3 bucket
   - Files are uploaded directly to the bucket root (no prefix subdirectories)
3. **If `--env-file` is not specified:**
   - Package is created locally only
   - No S3 sync is attempted

**Example output with S3 sync:**
```
2024-01-15 10:30:15,123 - INFO - Loaded environment variables from .env.dev
2024-01-15 10:30:15,124 - INFO - Package created: ./mcp_hubspot_connector.zip
2024-01-15 10:30:15,125 - INFO - Using AWS settings from environment file (bucket: silvaengine-dev-packages, region: us-east-1)
2024-01-15 10:30:15,126 - INFO - Syncing mcp_hubspot_connector.zip (15.3MB) to s3://silvaengine-dev-packages/mcp_hubspot_connector.zip...
| Uploading 15.3MB to S3... (2.1s)
✓ Successfully uploaded 15.3MB to S3: s3://silvaengine-dev-packages/mcp_hubspot_connector.zip
2024-01-15 10:30:17,456 - INFO - Successfully synced to S3: s3://silvaengine-dev-packages/mcp_hubspot_connector.zip
```

**Example output without S3 sync (local only):**
```
2024-01-15 10:30:15,123 - INFO - Package created: ./mcp_hubspot_connector.zip
2024-01-15 10:30:15,124 - INFO - Resolved 15 modules and 8 distributions.
```

### Programmatic Usage

```python
from module_packager import ModulePackager

# Initialize with config file
packager = ModulePackager(config_path='mcp_packages.json')

# Or override venv path
packager = ModulePackager(venv_path='/custom/path', config_path='mcp_packages.json')

# Use custom environment file
packager = ModulePackager(config_path='mcp_packages.json', env_file='./config/.env.prod')

# Package a module (automatically includes config extras)
zip_path = packager.create_package('mcp_hubspot_connector', output_dir='./packages')

# Inspect dependencies
mods, dists, tree, kind = packager.inspect_dependencies('mcp_hubspot_connector')
print(f"Found {len(mods)} modules using {kind} strategy")

# Get module-specific extras from config
extras = packager.get_module_extras('mcp_hubspot_connector')
print(f"Configured extras: {extras}")

# Package and sync to S3 (if environment file was loaded)
zip_path = packager.create_package('mcp_hubspot_connector', env_file_provided=True)

# Package locally only
zip_path = packager.create_package('mcp_hubspot_connector', env_file_provided=False)

# Check loaded environment variables
import os
print(f"Current S3 bucket: {os.environ.get('mcp_bucket')}")
print(f"Current AWS region: {os.environ.get('region_name')}")
```

## Examples

### Package MCP Connectors

```bash
# Package HubSpot connector with config extras
python module_packager.py mcp_hubspot_connector

# Package with custom strategy
python module_packager.py mcp_resolvepay_connector --strategy imports

# Inspect dependencies before packaging
python module_packager.py mcp_hubspot_connector --inspect --strategy metadata

# Package and sync to development S3
python module_packager.py mcp_hubspot_connector --env-file .env.dev

# Package and sync to production with custom output directory
python module_packager.py mcp_resolvepay_connector --output-dir ./production-packages --env-file .env.prod

# Local packaging only (no S3 sync)
python module_packager.py mcp_hubspot_connector
python module_packager.py mcp_resolvepay_connector --output-dir ./local-packages
```

### Sample Inspection Output

```
============================================================
DEPENDENCY ANALYSIS FOR: mcp_hubspot_connector
============================================================
Strategy Used: metadata
Total Distributions: 15
Total Top-level Modules: 18
Extra Modules Included: 6 (numpy.libs, hubspot, sklearn, scikit_learn.libs, scipy.libs, threadpoolctl.py)

📦 DISTRIBUTIONS:
  • hubspot-api-client
  • mcp-hubspot-connector
  • numpy
  • scikit-learn
  • scipy

🐍 TOP-LEVEL MODULES:
  • hubspot
  • mcp_hubspot_connector
  • numpy
  • sklearn
  • scipy

🌳 DEPENDENCY TREE:
mcp_hubspot_connector
├── hubspot-api-client
│   ├── requests
│   └── urllib3
├── numpy
└── scikit-learn
    ├── numpy (already shown)
    ├── scipy
    └── threadpoolctl
```

### Output Structure

The generated ZIP file contains all dependencies with proper structure:
```
mcp_hubspot_connector.zip
├── mcp_hubspot_connector/
│   ├── __init__.py
│   ├── handlers/
│   └── ...
├── hubspot/
│   └── ...
├── numpy/
│   └── ...
├── sklearn/
│   └── ...
├── numpy.libs/           # From config extras
│   └── ...
├── package_metadata.dist-info/
│   └── ...
└── ...
```

## How It Works

1. **Configuration Loading**: Reads JSON config for venv path, module extras, exclusions, and AWS settings
2. **Strategy Selection**: Chooses between metadata, imports, or auto resolution
3. **Module Discovery**: Starts with target module and resolves dependencies
4. **Extras Integration**: Automatically includes module-specific extras from config
5. **Import Analysis**: For imports strategy, parses Python files using AST
6. **Metadata Resolution**: For metadata strategy, follows Requires-Dist recursively
7. **Tree Building**: Constructs dependency graph with cycle detection
8. **File Collection**: Gathers all Python files for resolved modules
9. **ZIP Creation**: Packages everything into compressed archive
10. **S3 Sync** (optional): Uploads package to configured S3 bucket using AWS CLI

## Requirements

- Python 3.6+
- Standard library modules only (no external dependencies)
- Optional: `packaging` library for robust Requires-Dist parsing
- Optional: AWS CLI for S3 sync functionality (`pip install awscli`)

## Supported Module Types

- Directory-based modules (packages)
- Single-file modules
- Nested package structures
- Modules with complex dependency trees
- Distribution packages with metadata
- Modules with optional extras

## Configuration Management

- **Centralized Config**: Single JSON file for all settings
- **Module-Specific Extras**: Configure additional dependencies per module
- **Exclusion Lists**: Manage excluded and stdlib modules centrally
- **Environment Flexibility**: Override venv path per invocation
- **Backward Compatibility**: Works with or without config file

## Error Handling

- Gracefully handles missing modules and distributions
- Logs warnings for unresolvable dependencies
- Continues processing even if some dependencies fail
- Provides detailed error messages and strategy fallback
- Config file errors fall back to defaults with warnings

## Advanced Features

- **Cycle Detection**: Identifies and handles circular dependencies in tree view
- **Multiple Roots**: Supports dependency trees with multiple entry points
- **Strategy Fallback**: Auto strategy tries metadata first, falls back to imports
- **Size Filtering**: Automatically skips oversized binary files (>50MB)
- **Cross-Platform**: Handles Windows, macOS, and Linux virtual environments
- **S3 Integration**: Seamless AWS S3 sync with environment-specific configurations
- **Secure Credential Management**: Environment-specific AWS credentials via .env files
- **AWS CLI Integration**: Leverages existing AWS CLI setup for reliable uploads
- **Upload Progress**: Real-time progress indicator with file size and elapsed time during S3 uploads

## Security

- **Complete Environment Isolation**: All AWS settings (credentials, buckets, regions) are stored in `.env` files
- **No Config Dependencies**: AWS configuration is completely separated from JSON config files
- **Environment Separation**: Different settings for dev, staging, and production environments
- **Version Control Safe**: Environment files should be gitignored and never committed
- **Template Provided**: Use `.mcp.env.template` as a reference for required environment variables
- **Flexible Configuration**: Use custom environment files with `--env-file` for different projects or scenarios
- **Simplified Structure**: Direct S3 uploads without prefix subdirectories for cleaner bucket organization