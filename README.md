# AI Agent Serverless Framework Deployment

## Introduction

The `ai_agent_deployment` repository streamlines the deployment of AI Agent Core services within the SilvaEngine ecosystem, enabling efficient setup and management of AI Agent capabilities by leveraging SilvaEngine's cloud-native architecture and AWS services.

## Modules
1. [**AI Core Engine Engine**](https://github.com/ideabosque/ai_agent_core_engine): Effortlessly run and scale intelligent agents across multiple LLMs with the capability to manage state or sessions. Powered by the SilvaEngine serverless framework, the platform offers a unified, AI-native control plane that integrates rolling context memory, modular function calling, and real-time conversation monitoring for seamless orchestration and performance.
2. [**AI Agent Funct Base**](https://github.com/ideabosque/ai_agent_funct_base): A foundational framework for developing and implementing function-calling modules, enabling seamless interaction and integration with each LLM’s advanced capabilities.

## Prerequisites

Before proceeding with the installation, ensure you have the following:

- **Docker**: Install Docker and Docker Compose to run containerized services.
- **Python 3.11**: The deployment uses Python 3.11, so ensure it is installed.
- **AWS CLI**: Set up the AWS CLI with access credentials that have permissions to create S3 buckets, IAM roles, and Lambda functions.
- **Git**: Required to clone the necessary repositories.
- **AWS Account**: You'll need an AWS account to create resources such as S3 buckets, IAM roles, and Lambda functions.

## Installation and Configuration

### Step 1: Clone Repositories

1. Create a main project directory named `silvaengine`.
2. Within this folder, clone the following repositories:
   - [silvaengine\_aws](https://github.com/ideabosque/silvaengine_aws)
   - [ai\_agent_\_deployment](https://github.com/ideabosque/ai_agent_deployment)

### Step 2: Download and Set Up Docker

1. Clone the [silvaengine\_docker](https://github.com/ideabosque/silvaengine_docker) project.

2. Create the necessary directories within the Docker setup:

   ```bash
   $ mkdir -p www/logs
   $ mkdir -p www/projects
   $ mkdir -p python/.ssh
   ```

3. Place your SSH private and public key files in the `python/.ssh` directory (optional for future customization).

4. Set up a `.env` file in the root directory, using the provided `.env.example` for reference. Here’s a sample configuration:

   ```bash
   PIP_INDEX_URL=https://pypi.org/simple/ # Or use <https://mirrors.aliyun.com/pypi/simple/> for users in China
   PROJECTS_FOLDER={path to your projects directory}
   PYTHON=python3.11 # Python version
   DEBUGPY=/var/www/projects/silvaengine_aws/deployment/cloudformation_stack.py # Debug Python file path
   ```

5. Build the Docker image:

   ```bash
   $ docker compose build
   ```

6. Start the Docker container:

   ```bash
   $ docker compose up -d
   ```

### Step 3: Setup and Deployment

1. **Create an S3 Bucket**: Ensure versioning is enabled (e.g., `xyz-silvaengine-aws`).
2. **Configure the ********`.env`******** File**: Place this file inside the `ai_agent_deployment` folder with the following settings:
   ```bash
   #### Stack Deployment Settings
   root_path=../silvaengine_aws # Root path of the stack
   site_packages=/var/python3.11/silvaengine/env/lib/python3.11/site-packages # Python packages path

   #### CloudFormation Settings
   bucket=silvaengine-aws # S3 bucket for zip packages
   region_name=us-west-2 # AWS region
   aws_access_key_id=XXXXXXXXXXXXXXXXXXX # AWS Access Key ID
   aws_secret_access_key=XXXXXXXXXXXXXXXXXXX # AWS Secret Access Key
   iam_role_name=silvaengine_exec (optional) # IAM role for SilvaEngine Base.
   microcore_iam_role_name=silvaengine_microcore_dw_exec (optional) # IAM role for silvaEngine microcore.

   # AWS Lambda Function Variables
   REGIONNAME=us-west-2 # AWS region for resources
   EFSMOUNTPOINT=/mnt # EFS mount point (optional)
   PYTHONPACKAGESPATH=pypackages # Folder for large packages (optional)
   runtime=python3.11 # Lambda function runtime (optional)
   security_group_ids=sg-XXXXXXXXXXXXXXXXXXX # Security group IDs (optional)
   subnet_ids=subnet-XXXXXXXXXXXXXXXXXXX,subnet-XXXXXXXXXXXXXXXXXXX # Subnet IDs (optional)
   efs_access_point=fsap-XXXXXXXXXXXXXXXXXXX # EFS access point (optional)
   efs_local_mount_path=/mnt/pypackages # EFS local mount path (optional)
   {function name or layer name}_version=XXXXXXXXXXXXXXXXXXX # Function or layer version (optional)
   ```

    **Example Configuration:**

    ```bash
    #### Setting for the stack deployment
    root_path=../silvaengine_aws                                                # The root path of the stack.
    site_packages=/var/python3.11/silvaengine/env/lib/python3.11/site-packages    # The path of the python packages.

    ### ideabosque dev: dw
    bucket=silvaengine-aws                                              # The S3 bucket to store the zip packages.
    region_name=us-west-2                                               # The AWS region.
    aws_access_key_id=XXXXXXXXXXXXXXXXXXX                              # AWS ACCESS KEY ID.
    aws_secret_access_key=XXXXXXXXXXXXXXXXXXX                          # AWS SECRET ACCESS KEY.
    # Variables for aws lambda functions
    REGIONNAME=us-west-2                                                # Region for resources, tasks, and workers.
    runtime=python3.11
    ```

### Step 4: Deploy SilvaEngine Base

1. Run the following command to access the container:

   ```bash
   $ docker exec -it container-aws-suites-311 /bin/bash
   ```

2. Activate the virtual environment:

   ```bash
   source /var/python3.11/silvaengine/env/bin/activate
   ```

3. Navigate to the deployment directory and deploy the SilvaEngine stack:

   ```bash
   cd ./ai_agent_deployment
   ./silvaengine_requirements.sh .env
   ```

### Step 5: Deploy AI Agent Add-On Management Framework

1. Add entries into the `se-endpoints` (DynamoDB Table) collection, using the `endpoint_id` such as `openai` from the `lambda_config.json` file located in the `ai_agent_deployment` directory. The format for each entry should be as follows:

   ```json
   {
       "endpoint_id": {endpoint_id},
       "code": 0,
       "special_connection": true
   }
   ```

2. For each `endpoint_id` in the `lambda_config.json` file within `datawald_deployment`, insert two separate records into `se-connections` (DynamoDB table):

   - One record using the static `api_key` value '#####':

     ```json
     {
         "endpoint_id": {endpoint_id},
         "api_key": "#####",
         "functions": []
     }
     ```

   - Another record with the actual `api_key` associated with the deployed AWS API Gateway:

     ```json
     {
         "endpoint_id": {endpoint_id},
         "api_key": {api_key},
         "functions": []
     }
     ```

3. To access the container, execute the following command:

   ```bash
   $ docker exec -it container-aws-suites-311 /bin/bash
   ```

4. Activate the Python virtual environment by running:

   ```bash
   source /var/python3.11/silvaengine/env/bin/activate
   ```

5. Navigate to the `ai_agent_deployment` directory and execute the CloudFormation stack setup script:

   ```bash
   cd ./ai_agent_deployment
   ./ai_agent_requirements.sh .env
   ./ai_knowledge_requirements.sh .env
   ./slack_requirements.sh .env
   ```

## Deployment Verification

After deploying SilvaEngine Base, you can verify the deployment by:

1. **AWS Management Console**: Check the CloudFormation stack status in the AWS Management Console to confirm that all resources were created successfully.
2. **Docker Containers**: Use `docker ps` to ensure all necessary containers are running.
3. **Logs**: Check the log files inside the `www/logs` directory for any error messages or issues that occurred during deployment.

## Troubleshooting

- **AWS Credentials**: Double-check the AWS credentials (`aws_access_key_id` and `aws_secret_access_key`) if you face authentication errors during deployment.
- **Python Version Conflicts**: Make sure Python 3.11 is installed and is the default version used within the Docker container.

## Conclusion

The `ai_agent_deployment` repository is a crucial component of the SilvaEngine project, enabling easy integration of OpenAI services into cloud infrastructure. Ensure all steps are followed carefully for a successful deployment.

For further assistance, refer to the SilvaEngine documentation or reach out to the development team.

