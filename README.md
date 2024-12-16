# Terraform AWS Detector

**Terraform AWS Detector** is a tool designed to audit AWS resources and identify which ones are not managed by Terraform. It compares resources defined in Terraform state files against the actual resources found in your AWS account, helping you maintain proper resource management and avoid resource drift.

## Features

- **Seamless Terraform State Integration**  
  Automatically reads local and remote (S3-backed) Terraform state files to determine which AWS resources are currently under Terraform's control, ensuring consistency and accuracy in your infrastructure management.

- **Extensive AWS Resource Coverage**  
  Employing a pluggable architecture, the tool uses multiple collectors to discover and map a wide array of AWS services:

  - **Application**:
    - Step Functions State Machines
  - **Compute**:
    - EC2 Instances
    - ECS Clusters and Services
    - Lambda Functions
    - EBS Volumes
    - Virtual Private Clouds (VPC)
    - Security Groups
  - **Database**:
    - RDS Database Instances and Clusters
    - DynamoDB Tables
    - ElastiCache Clusters and Replication Groups
  - **Network**:
    - API Gateway REST APIs
    - API Gateway HTTP/WebSocket APIs
    - CloudFront Distributions
    - Legacy Load Balancers (ELB)
    - Application/Network Load Balancers (ALB/NLB)
    - LB Listeners and Listener Rules
    - LB Target Groups
    - Route 53 Hosted Zones
  - **Security**:
    - IAM Users, Groups, and Roles
    - KMS Customer-Managed Keys
    - Secrets Manager Secrets
  - **Storage**:
    - S3 Buckets
    - EFS File Systems
    - EBS Volumes

- **Unmanaged Resource Detection**  
  Identifies AWS resources not currently represented in your Terraform state, making it easy to bring these unmanaged components under Infrastructure as Code for streamlined operations.

- **Flexible Output Formats**  
  Outputs findings as both JSON and human-readable text, enabling effortless integration into CI/CD pipelines or direct review, ensuring that results are accessible and actionable.

## Getting Started

### Prerequisites

- Python 3.8+
- AWS credentials configured (e.g., via `aws configure` or environment variables)
- Terraform state files locally or accessible via S3

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/cahlchang/terraform_aws_detector.git
   cd terraform_aws_detector
   ```

2. Install the package:
   ```bash
   pip install .
   ```

## Usage

Run the tool by specifying the directory that contains your Terraform configuration and state files:

```bash
terraform_aws_detector --tf-dir path/to/terraform --output json
```

Command-line options:

- `--tf-dir`: The directory containing Terraform files and state.
- `--output`: The desired output format (text or json). Defaults to text.
- `--output-file`: Optional path to write the results instead of printing to stdout.
- `--list-resources`: List all supported AWS resource types.

### Example

```bash
terraform_aws_detector --tf-dir ./terraform-code --output json --output-file unmanaged_resources.json
```

This command will:

- Scan your Terraform directory for state files.
- Retrieve AWS resources using various AWS service collectors.
- Identify which AWS resources are unmanaged.
- Output the result in JSON format to unmanaged_resources.json.

## Project Structure

- `terraform_aws_detector/`:
  Core implementation files:
  - `auditor.py`: Main logic for auditing and comparing Terraform-managed vs. AWS-discovered resources.
  - `state_reader.py`: Reads Terraform state (local or S3) and extracts managed resource IDs.
  - `collectors/`: Contains AWS service-specific collectors (e.g., aws_compute.py, aws_database.py).
  - `formatters/output_formatter.py`: Formats the final report output.
  - `main.py`: Entry point for the CLI.
- `requirements.txt`:
  Lists Python dependencies for easy setup.
- `setup.py`:
  Enables installation as a Python package.

## Contributing

Contributions are welcome! To contribute:

1. Fork this repository.
2. Create a feature branch.
3. Submit a pull request with your changes.

We appreciate feedback on code quality, performance improvements, or suggestions for additional AWS services and Terraform integrations.

## License

This project is licensed under the MIT License.

## Contact

For questions or suggestions, please open an issue or reach out to the maintainer at kahlua.dane@gmail.com.
