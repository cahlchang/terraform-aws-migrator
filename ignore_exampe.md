# AWS Resources to exclude
# Format: resource_id, ARN, or type:id

# EC2 Instances
i-0123456789abcdef0     # Specific test instance
i-test*                 # All test instances

# Network resources
vpc-*          # All VPCs
subnet-prod-*  # Production subnets

# Lambda functions
arn:aws:lambda:*:*:function:maintenance-*  # Maintenance functions
lambda:backup-*                           # Backup functions

# Databases
dynamodb:audit-*        # Audit tables
rds:*-snapshot         # All DB snapshots

# Security groups
security-group:sg-monitoring-*  # Monitoring security groups

# IAM Resources
iam:role/service-*           # Service-linked roles
iam:role/aws-service-role/* # AWS service-linked roles
iam:user/system-*           # System users
iam:group/readonly-*        # Read-only access groups
arn:aws:iam::*:role/aws-reserved/*  # AWS reserved roles
arn:aws:iam::*:role/service-role/*  # AWS service roles
arn:aws:iam::*:policy/AWS*         # AWS managed policies

# Service-specific exclusions
ec2:*-backup    # All EC2 backup resources
s3:logs-*       # Log buckets
