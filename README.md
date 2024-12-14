# Terraform AWS Detector

**Terraform AWS Detector** is a tool designed to audit AWS resources and identify which ones are not managed by Terraform. It compares resources defined in Terraform state files against the actual resources found in your AWS account, helping you maintain proper resource management and avoid resource drift.

## Features

- **Terraform State Integration**:  
  Reads Terraform state files (local or S3-backed) to determine which AWS resources should be under Terraform’s control.

- **Comprehensive AWS Resource Discovery**:  
  Uses a pluggable architecture with multiple collectors to fetch resources from numerous AWS services, including:
  - Compute: EC2, ECS
  - Database: RDS, DynamoDB, ElastiCache
  - Network: APIGateway, APIGatewayV2, Route53, CloudFront
  - Security: IAM, KMS, Secrets Manager
  - Storage: S3, EFS, EBS

- **Unmanaged Resource Detection**:  
  Identifies resources present in AWS but missing from the Terraform state, helping you maintain consistent infrastructure definitions.

- **Flexible Output Formats**:  
  Provides both JSON and human-readable text output, allowing easy integration into CI pipelines or direct inspection.

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

	2.	Install the package:

pip install .



Usage

Run the tool by specifying the directory that contains your Terraform configuration and state files:

terraform_aws_detector --tf-dir path/to/terraform --output json

Command-line options:
	•	--tf-dir: The directory containing Terraform files and state.
	•	--output: The desired output format (text or json). Defaults to text.
	•	--output-file: Optional path to write the results instead of printing to stdout.

Example

terraform_aws_detector --tf-dir ./terraform-code --output json --output-file unmanaged_resources.json

This command will:
	•	Scan your Terraform directory for state files.
	•	Retrieve AWS resources using various AWS service collectors.
	•	Identify which AWS resources are unmanaged.
	•	Output the result in JSON format to unmanaged_resources.json.

Project Structure
	•	terraform_aws_detector/:
Core implementation files:
	•	auditor.py: Main logic for auditing and comparing Terraform-managed vs. AWS-discovered resources.
	•	state_reader.py: Reads Terraform state (local or S3) and extracts managed resource IDs.
	•	collectors/: Contains AWS service-specific collectors (e.g., aws_compute.py, aws_database.py).
	•	formatters/output_formatter.py: Formats the final report output.
	•	main.py: Entry point for the CLI.
	•	requirements.txt:
Lists Python dependencies for easy setup.
	•	setup.py:
Enables installation as a Python package.

Contributing

Contributions are welcome! To contribute:
	1.	Fork this repository.
	2.	Create a feature branch.
	3.	Submit a pull request with your changes.

We appreciate feedback on code quality, performance improvements, or suggestions for additional AWS services and Terraform integrations.

License

This project is licensed under the MIT License.

Contact

For questions or suggestions, please open an issue or reach out to the maintainer at kahlua.dane@gmail.com.

