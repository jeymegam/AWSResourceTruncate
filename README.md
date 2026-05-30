# AWS Resource Cleanup

Complete AWS account resource deletion tool. Deletes all resources across multiple services with safety features including dry-run mode, confirmation prompts, and detailed logging.

## Supported Services

| Service | Resources Deleted |
|---------|-------------------|
| CloudFormation | Stacks (with termination protection override) |
| ECS | Clusters, services, tasks, task definitions |
| RDS | Instances, clusters, snapshots, subnet groups |
| Lambda | Functions, layers, event source mappings |
| EC2 | Instances, NAT gateways, EIPs, volumes, snapshots, security groups, key pairs, launch templates |
| DynamoDB | Tables (with deletion protection override) |
| Glue | Databases, tables, jobs, crawlers |
| Athena | Workgroups, named queries |
| S3 Tables | Table buckets, namespaces, tables |
| S3 | Buckets (empties versioned objects first) |
| SNS | Topics and subscriptions |
| SQS | Queues |
| CloudWatch | Log groups, alarms, dashboards |
| IAM | Roles, policies, users, instance profiles (skips AWS-managed) |

## Setup

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

## Usage

```bash
# Preview what would be deleted (safe)
python main.py --dry-run

# Delete all resources (with confirmation prompt)
python main.py

# Delete only specific services
python main.py --services ec2 s3 dynamodb

# Skip confirmation (for automation)
python main.py --yes

# Combine flags
python main.py --dry-run --services lambda ecs
```

## Safety Features

- **Dry-run mode**: Lists all resources that would be deleted without making changes
- **Confirmation prompt**: Requires typing `DELETE ALL` before live execution
- **Logging**: All actions logged to timestamped file (`cleanup_YYYYMMDD_HHMMSS.log`)
- **Protected resources**: Skips AWS-managed IAM roles, service-linked roles, default security groups
- **Ordered deletion**: Resources deleted in dependency order (CloudFormation first, IAM last)

## Project Structure

```
AWSResourceTruncate/
├── main.py                 # CLI entry point
├── config.py               # AWS session and configuration
├── logger.py               # Logging setup
├── cleaners/
│   ├── __init__.py         # Cleaner registry
│   ├── base.py             # Abstract base cleaner
│   ├── ec2.py              # EC2 resources
│   ├── s3.py               # S3 buckets
│   ├── s3_tables.py        # S3 Tables
│   ├── iam.py              # IAM resources
│   ├── dynamodb.py         # DynamoDB tables
│   ├── glue.py             # Glue resources
│   ├── athena.py           # Athena resources
│   ├── lambda_cleaner.py   # Lambda functions
│   ├── cloudformation.py   # CloudFormation stacks
│   ├── rds.py              # RDS resources
│   ├── ecs.py              # ECS resources
│   ├── sns.py              # SNS topics
│   ├── sqs.py              # SQS queues
│   └── cloudwatch.py       # CloudWatch resources
├── requirements.txt
├── .env.example
└── README.md
```

## Warning

This tool performs **irreversible deletions**. Always run with `--dry-run` first to verify what will be removed. Use in development/sandbox accounts only.
