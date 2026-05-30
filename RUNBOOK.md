# AWS Resource Cleanup - Runbook

## Purpose

This runbook provides step-by-step instructions for executing a complete AWS account resource cleanup. Use this when decommissioning a sandbox/dev account, resetting a test environment, or removing all provisioned resources after a project ends.

---

## Resource Exclusions

The following resources are **protected from deletion** to avoid breaking the AWSProject1 ETL pipeline and shared deployment infrastructure. See `RESOURCE_EXCLUSIONS.md` for full context.

| Resource | Type | Reason |
|----------|------|--------|
| `s3-to-iceberg-lambda-role` | IAM Role | Lambda execution role for S3→Iceberg ETL. Deletion causes KMSAccessDeniedException. |
| `s3-ingest-policy` | Inline Policy (on above role) | Contains S3, Athena, Glue, LakeFormation, KMS permissions. |
| `CodeDeploy` | IAM User | Deployment user. `AdministratorAccess` policy is never detached. |
| `1c4b0282-d7e0-4b58-b0db-513199cd91ad` | KMS Key (eu-west-2) | Encrypts Lambda environment variables. Modifying it silently breaks the S3→Lambda trigger. |

Exclusions are configured in `exclusions.py`. To add or remove protected resources, edit that file.

### What happens if exclusions are violated

| Error | Cause | Impact |
|-------|-------|--------|
| `KMSAccessDeniedException` | KMS key policy modified or role lost `kms:Decrypt` | Lambda silently fails, S3 events dropped with no logs |
| `AccessDenied` on IAM operations | `AdministratorAccess` detached from `CodeDeploy` | All deployment scripts blocked |

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
- [ ] **Exclusions reviewed**: Confirm `exclusions.py` is up to date with protected resources
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

**Expected output**: A list of all resources that would be deleted, prefixed with `[DRY RUN] Would delete`. Excluded resources will show as `Skipped ... (excluded)`.

**Review the output carefully.** Look for:
- Resources you did NOT expect to see
- Resources that belong to shared services
- Excluded resources are properly skipped (look for "excluded" in the log)
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

# Clean only data layer (tables + query results)
python main.py --dry-run --services s3tables athena
```

Available service names:
```
cloudformation, ecs, rds, lambda, ec2, dynamodb,
glue, athena, s3tables, s3, sns, sqs, cloudwatch, kms, iam
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
4. Lambda (functions, layers — skips functions using excluded roles)
5. EC2 (instances, volumes, security groups)
6. DynamoDB (tables)
7. Glue (databases, tables, jobs)
8. Athena (query result files, workgroups, named queries, result buckets)
9. S3 Tables (table metadata, namespaces, AND underlying data buckets)
10. S3 (buckets and all objects)
11. SNS (topics and subscriptions)
12. SQS (queues)
13. CloudWatch (log groups, alarms, dashboards)
14. KMS (customer-managed keys scheduled for 7-day deletion — skips excluded keys)
15. IAM (roles, policies, users — skips excluded roles/users, always last)

### Step 4: Review Logs

After execution, check the generated log file:

```bash
# Log files are created in the project root
# Format: cleanup_YYYYMMDD_HHMMSS.log
dir cleanup_*.log

# Review the latest log
type cleanup_20260530_143022.log
```

**Verify exclusions were respected:**
```bash
# Search for "excluded" or "Skipped" in the log
findstr /i "excluded" cleanup_*.log
findstr /i "Skipped" cleanup_*.log
```

---

## Post-Execution Verification

### Verify Resources Are Deleted

```bash
# Check EC2 instances
aws ec2 describe-instances --query "Reservations[].Instances[?State.Name!='terminated']"

# Check S3 buckets
aws s3 ls

# Check S3 Tables data is gone
aws s3 ls | findstr "s3tablescatalog"

# Check Athena query results are gone
aws s3 ls | findstr "athena"

# Check DynamoDB tables
aws dynamodb list-tables

# Check Lambda functions
aws lambda list-functions

# Check IAM roles (should only show AWS-managed + excluded)
aws iam list-roles --query "Roles[?!starts_with(RoleName,'AWS')]"

# Verify excluded resources still exist
aws iam get-role --role-name s3-to-iceberg-lambda-role
aws kms describe-key --key-id 1c4b0282-d7e0-4b58-b0db-513199cd91ad --region eu-west-2
aws iam list-attached-user-policies --user-name CodeDeploy
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
| S3 Tables data still present | Backing bucket name doesn't match known prefixes | Manually check `aws s3 ls` for remaining table data buckets |
| Athena results still present | Custom output location not matching patterns | Check workgroup config for non-standard output paths |
| Security group deletion fails | SG referenced by another SG | Script revokes cross-references first; re-run if needed |
| CloudFormation stack stuck in `DELETE_FAILED` | Resource can't be deleted | Manually check the stack events in AWS Console |
| RDS instance won't delete | Deletion protection enabled | Script disables protection automatically |
| IAM role deletion fails | Role is in use by a running service | Delete the dependent service first, then re-run |
| KMS key still active after cleanup | Key is in the exclusion list | Expected behavior — check `exclusions.py` |
| Lambda function not deleted | Function uses an excluded IAM role | Expected behavior — function is protected by association |

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

If an excluded resource was accidentally deleted (e.g., `exclusions.py` was modified):
- **KMS key**: If within the 7-day pending deletion window, cancel with `aws kms cancel-key-deletion --key-id <key-id>`
- **IAM role**: Re-run the deployment script (`py 02_deploy_lambda.py`)
- **CodeDeploy user policy**: `aws iam attach-user-policy --user-name CodeDeploy --policy-arn arn:aws:iam::aws:policy/AdministratorAccess`

---

## Service-Specific Notes

### S3
- Versioned buckets: All object versions are deleted before bucket removal
- Bucket policies that deny deletion are removed first
- Cross-region replication destinations are NOT cleaned (run in each region)

### S3 Tables
- Deletes table metadata via the S3 Tables API (tables, namespaces, table buckets)
- **Also deletes underlying data**: Finds and empties backing S3 buckets (`s3tablescatalog-*`, `s3-tables-*`, `table-bucket-*`) that store the actual Iceberg/Parquet files
- If your table data bucket uses a non-standard name, it will be caught by the general S3 cleaner

### Athena
- **Cleans query result files**: Reads each workgroup's `OutputLocation` and empties all objects at that S3 path
- **Deletes result buckets**: Finds buckets matching `aws-athena-query-results-*`, `athena-results-*`, or containing `athena-output`/`athena-query`
- Handles versioned objects in result buckets
- Deletes named queries and non-primary workgroups
- The `primary` workgroup is never deleted (AWS default)

### KMS
- Only customer-managed keys are affected (AWS-managed keys like `aws/s3`, `aws/ebs` are never touched)
- Keys are scheduled for deletion with a **7-day waiting period** (minimum allowed by AWS)
- During the 7-day window, deletion can be cancelled: `aws kms cancel-key-deletion --key-id <key-id>`
- Excluded keys are skipped entirely (not disabled, not modified)

### IAM
- **Never deletes**: AWS-managed roles, service-linked roles, the current caller's user
- **Excluded**: `s3-to-iceberg-lambda-role`, `CodeDeploy` user (see exclusions)
- Detaches all policies and removes from groups before user/role deletion
- Customer-managed policies are deleted after detaching from all entities
- Instance profiles containing excluded roles are skipped

### Lambda
- Functions using excluded IAM roles are automatically skipped
- This protects the S3→Iceberg ETL function without needing to hardcode function names

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

## Managing Exclusions

To add a new resource to the exclusion list:

1. Edit `exclusions.py`
2. Add the resource to the appropriate list:
   ```python
   EXCLUDED_IAM_ROLES = [
       "s3-to-iceberg-lambda-role",
       "your-new-role-to-protect",  # Add here
   ]
   ```
3. Run a dry run to verify: `python main.py --dry-run`
4. Confirm the resource shows as "Skipped ... (excluded)" in the output
5. Document the reason in `RESOURCE_EXCLUSIONS.md`
6. Commit and push the change

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
| 2026-05-30 | 1.1.0 | Added resource exclusions (IAM, KMS) to protect shared infrastructure |
| 2026-05-30 | 1.2.0 | Added S3 Tables underlying data cleanup and Athena query result file deletion |
