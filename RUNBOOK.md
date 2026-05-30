# AWS Resource Cleanup - Runbook

## Purpose

This runbook provides step-by-step instructions for executing a complete AWS account resource cleanup. Use this when decommissioning a sandbox/dev account, resetting a test environment, or removing all provisioned resources after a project ends.

---

## Prerequisites

### 1. Access Requirements

- AWS IAM credentials with **AdministratorAccess** or equivalent permissions
- Credentials configured via one of:
  - AWS CLI profile (`aws configure`)
  - Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
  - IAM instance profile (if running on EC2)

### 2. Software Requirements

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.9+ | Runtime |
| pip | Latest | Package manager |
| AWS CLI | 2.x | Credential configuration |
| Git | Any | (Optional) Version control |

### 3. Environment Setup

```bash
# Clone or navigate to the project
cd AWSResourceTruncate

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configuration

```bash
# Copy the example environment file
cp .env.example .env
```

Edit `.env` with your settings:

```ini
AWS_PROFILE=default          # AWS CLI profile name
AWS_REGION=us-east-1         # Target region
SKIP_CONFIRMATION=false      # Set true for automation pipelines
DRY_RUN=false                # Set true to preview only
```

---

## Pre-Execution Checklist

Before running the cleanup, verify the following:

- [ ] **Correct account**: Run `aws sts get-caller-identity` and confirm the account ID
- [ ] **Correct region**: Confirm `AWS_REGION` in `.env` matches your target
- [ ] **No production workloads**: Verify this is NOT a production account
- [ ] **Backups taken**: Export any data, configs, or snapshots you need to retain
- [ ] **Team notified**: Inform stakeholders that resources will be destroyed
- [ ] **Billing reviewed**: Check for any resources with ongoing costs you want to track
- [ ] **Dry run completed**: Always run `--dry-run` first (see Step 1 below)

---

## Execution Steps

### Step 1: Dry Run (Required)

Always start with a dry run to review what will be deleted.

```bash
python main.py --dry-run
```

**Expected output**: A list of all resources that would be deleted, prefixed with `[DRY RUN] Would delete`.

**Review the output carefully.** Look for:
- Resources you did NOT expect to see
- Resources that belong to shared services
- Any AWS-managed resources that shouldn't be touched

### Step 2: Targeted Cleanup (Optional)

If you only need to clean specific services, use the `--services` flag:

```bash
# Clean only EC2 and S3
python main.py --dry-run --services ec2 s3

# Clean only database services
python main.py --dry-run --services dynamodb rds

# Clean only serverless resources
python main.py --dry-run --services lambda sns sqs
```

Available service names:
```
cloudformation, ecs, rds, lambda, ec2, dynamodb,
glue, athena, s3tables, s3, sns, sqs, cloudwatch, iam
```

### Step 3: Execute Live Deletion

Once satisfied with the dry run output:

```bash
python main.py
```

When prompted, type exactly: `DELETE ALL`

The script will process services in dependency order:
1. CloudFormation (removes stacks that manage other resources)
2. ECS (clusters, services, tasks)
3. RDS (instances, clusters, snapshots)
4. Lambda (functions, layers)
5. EC2 (instances, volumes, security groups)
6. DynamoDB (tables)
7. Glue (databases, tables, jobs)
8. Athena (workgroups, queries)
9. S3 Tables (table buckets, namespaces)
10. S3 (buckets and all objects)
11. SNS (topics and subscriptions)
12. SQS (queues)
13. CloudWatch (log groups, alarms, dashboards)
14. IAM (roles, policies, users — last because other services depend on them)

### Step 4: Review Logs

After execution, check the generated log file:

```bash
# Log files are created in the project root
# Format: cleanup_YYYYMMDD_HHMMSS.log
dir cleanup_*.log

# Review the latest log
type cleanup_20260530_143022.log
```

---

## Post-Execution Verification

### Verify Resources Are Deleted

```bash
# Check EC2 instances
aws ec2 describe-instances --query "Reservations[].Instances[?State.Name!='terminated']"

# Check S3 buckets
aws s3 ls

# Check DynamoDB tables
aws dynamodb list-tables

# Check Lambda functions
aws lambda list-functions

# Check IAM roles (should only show AWS-managed)
aws iam list-roles --query "Roles[?!starts_with(RoleName,'AWS')]"
```

### Handle Remaining Resources

Some resources may not be deleted on the first pass due to:
- **Dependency conflicts**: Resource B depends on Resource A which was deleted after B was attempted
- **Eventual consistency**: AWS hasn't propagated the deletion yet
- **Permission issues**: The caller lacks permission for specific resources

**Resolution**: Run the script again. The second pass will catch resources that were blocked by dependencies.

```bash
python main.py --yes
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Resolution |
|-------|-------|------------|
| `Could not connect to AWS` | Invalid credentials or expired session | Run `aws sts get-caller-identity` to verify access |
| `AccessDenied` on specific resources | Insufficient permissions | Ensure IAM user/role has `AdministratorAccess` |
| S3 bucket deletion fails | Bucket policy denies delete | Script handles this automatically by removing policy first |
| Security group deletion fails | SG referenced by another SG | Script revokes cross-references first; re-run if needed |
| CloudFormation stack stuck in `DELETE_FAILED` | Resource can't be deleted | Manually check the stack events in AWS Console |
| RDS instance won't delete | Deletion protection enabled | Script disables protection automatically |
| IAM role deletion fails | Role is in use by a running service | Delete the dependent service first, then re-run |

### Timeout Issues

Some resources take time to delete (EC2 instances, CloudFormation stacks, RDS instances). The script includes waiters for critical resources, but if it appears stuck:

1. Check AWS Console for the resource status
2. Wait for the operation to complete
3. Re-run the script to catch remaining resources

### Multi-Region Cleanup

This script operates on a **single region**. To clean all regions:

```bash
# List all enabled regions
aws ec2 describe-regions --query "Regions[].RegionName" --output text

# Run for each region
for region in us-east-1 us-west-2 eu-west-1; do
    echo "Cleaning region: $region"
    AWS_REGION=$region python main.py --yes
done
```

On Windows PowerShell:
```powershell
$regions = @("us-east-1", "us-west-2", "eu-west-1")
foreach ($region in $regions) {
    Write-Host "Cleaning region: $region"
    $env:AWS_REGION = $region
    python main.py --yes
}
```

---

## Automation / CI Pipeline Usage

For automated environments (CI/CD, scheduled cleanup):

```bash
# Set environment variables instead of .env file
export AWS_REGION=us-east-1
export AWS_PROFILE=sandbox
export SKIP_CONFIRMATION=true

# Run with --yes to skip interactive prompt
python main.py --yes
```

Or use CLI flags:
```bash
python main.py --yes --services ec2 s3 lambda dynamodb
```

**Exit codes:**
- `0` — Cleanup completed (some individual resource errors may still have occurred)
- `1` — Fatal error (could not connect to AWS, invalid configuration)

---

## Rollback

**There is no rollback.** Deleted resources cannot be recovered.

If you need to recreate resources:
- Redeploy from Infrastructure-as-Code (Terraform, CloudFormation, CDK)
- Restore from backups (RDS snapshots, S3 cross-region replicas)
- Re-run provisioning scripts

---

## Service-Specific Notes

### S3
- Versioned buckets: All object versions are deleted before bucket removal
- Bucket policies that deny deletion are removed first
- Cross-region replication destinations are NOT cleaned (run in each region)

### IAM
- **Never deletes**: AWS-managed roles, service-linked roles, the current caller's user
- Detaches all policies and removes from groups before user/role deletion
- Customer-managed policies are deleted after detaching from all entities

### EC2
- Termination protection is disabled automatically
- Instances are terminated and the script waits for completion
- Only unattached (available) EBS volumes are deleted
- Snapshots owned by the account are deleted

### CloudFormation
- Termination protection is disabled automatically
- Nested stacks are deleted with their parent
- Stacks in `DELETE_FAILED` state are retried

### RDS
- Deletion protection is disabled automatically
- Final snapshots are skipped (no backup created on delete)
- Automated backups are deleted with the instance

---

## Emergency Stop

If you need to abort during execution:
- Press `Ctrl+C` to interrupt the script
- Resources already deleted cannot be recovered
- Resources in progress may be left in a transitional state
- Re-run the script after resolving any issues

---

## Contacts

| Role | Responsibility |
|------|---------------|
| Script Owner | Maintaining and updating the cleanup tool |
| Cloud Admin | AWS account access and permissions |
| Team Lead | Approval for production-adjacent account cleanup |

---

## Revision History

| Date | Version | Change |
|------|---------|--------|
| 2026-05-30 | 1.0.0 | Initial runbook creation |
