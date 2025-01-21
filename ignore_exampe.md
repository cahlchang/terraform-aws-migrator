# Setting up .tfignore

## Initial Setup

1. Rename the example file to .tfignore:
```bash
mv ignore_exampe.md .tfignore
```

2. If you're on Windows and having trouble with the rename:
```cmd
ren ignore_exampe.md .tfignore
```

## File Location

Place the .tfignore file in one of these locations:
- In your Terraform project root directory (recommended)
- In the same directory where you run terraform_aws_migrator
- Specify a custom path using the --ignore-file flag:
  ```bash
  terraform_aws_migrator --tf-dir ./terraform --ignore-file /path/to/.tfignore
  ```

## Example Configuration

Here's a recommended .tfignore configuration:

```
# Terraform AWS Resource Exclusions
# Format: 
# - aws_<service>_<resource>:<identifier> (Terraform resource type format)
# - <service>:<resource_type>/* (AWS service format)
# - Direct resource IDs or ARNs
# - Name tag values (full value or pattern)
# - <service>:<name-tag-value> (Service with Name tag format)

# EC2 Resources
aws_instance:i-0123456789abcdef0     # Specific test instance by ID
aws_instance:test-*                  # Instances with Name tag starting with "test-"
prod-backup-*                        # Any resource with Name tag starting with "prod-backup-"
ec2:staging-*                        # EC2 instances with Name tag starting with "staging-"

# VPC Resources with Name Tags
aws_vpc:prod-vpc-*                   # VPCs with Name tag starting with "prod-vpc-"
vpc:test-network-*                   # VPCs with Name tag starting with "test-network-"

# Load Balancer Resources
aws_lb:internal-*                    # Load balancers with Name tag starting with "internal-"
lb:test-alb-*                        # Load balancers with Name tag starting with "test-alb-"

# Lambda Resources
aws_lambda_function:maintenance-*     # Maintenance functions (by ID or Name tag)
lambda:backup-*                       # Backup functions (by ID or Name tag)

# Database Resources
aws_dynamodb_table:audit-*           # Audit tables (by ID or Name tag)
aws_db_instance:*-snapshot           # RDS instances with "-snapshot" suffix (ID or Name tag)
rds:dev-*                            # RDS instances with Name tag starting with "dev-"

# IAM Resources
aws_iam_role:service-*               # Service roles
aws_iam_user:system-*                # System users
aws_iam_group:readonly-*             # Read-only groups
aws_iam_policy:AWS*                  # AWS managed policies
```

## Pattern Formats

The .tfignore file supports these pattern formats:

1. Terraform Resource Type Format (Recommended):
   ```
   aws_iam_role:role-name*
   aws_lambda_function:function-name*
   ```

2. AWS Service Format:
   ```
   iam:role/role-name*
   lambda:function/function-name*
   ```

3. Name Tag Format:
   ```
   prod-*              # Match any resource with Name tag starting with "prod-"
   ec2:test-*          # Match EC2 resources with Name tag starting with "test-"
   aws_instance:dev-*  # Match EC2 instances with Name tag starting with "dev-"
   ```

4. Direct ARN Format:
   ```
   arn:aws:iam::*:role/role-name*
   arn:aws:lambda:*:*:function:function-name*
   ```

## Pattern Matching Rules

1. Resource ID Matching:
   - Patterns match against resource IDs directly
   - Example: `i-1234567890abcdef0`, `vpc-12345678`

2. Name Tag Matching:
   - Patterns match against the value of the "Name" tag
   - Can be used with or without service/resource type prefix
   - More flexible for resources that follow naming conventions

3. Service-Specific Matching:
   - Prefix patterns with service name for more targeted exclusions
   - Example: `ec2:prod-*` only matches EC2 resources

4. Full Resource Type Matching:
   - Most specific matching using complete AWS resource type
   - Example: `aws_instance:prod-*`

## Usage Tips

- Use # for comments
- Patterns are case-sensitive
- * matches any number of characters
- Blank lines are ignored
- Each pattern should be on a new line
- More specific patterns should be listed before general patterns
- When using aws_ prefix format, match the exact Terraform resource type name
- Name tag patterns can be used with or without service/type prefixes
- Service-specific patterns (e.g., ec2:prod-*) are more precise than general patterns (prod-*)

## Command Line Usage

```bash
# Use default .tfignore in current directory
terraform_aws_migrator --tf-dir ./terraform

# Specify custom ignore file location
terraform_aws_migrator --tf-dir ./terraform --ignore-file /path/to/.tfignore
```

## Best Practices

1. Start with specific exclusions:
   ```
   # Specific instance
   aws_instance:i-0123456789abcdef0
   ```

2. Add service-prefixed patterns:
   ```
   # All test EC2 instances
   ec2:test-*
   ```

3. Use Name tag patterns for groups of resources:
   ```
   # All resources tagged as production backups
   prod-backup-*
   ```

4. Document your exclusions with comments:
   ```
   # Development environment resources
   dev-*                  # All dev resources
   ec2:dev-*             # Dev EC2 instances
   aws_rds_cluster:dev-* # Dev RDS clusters
   ```
