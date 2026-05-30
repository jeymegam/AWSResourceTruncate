# Exclusions for AWS Resource Cleanup Scripts

These IAM and KMS resources must be excluded from automated cleanup to prevent
breaking the AWSProject1 ETL pipeline.

---

## IAM Resources to Exclude

| Type | Name | Reason |
|------|------|--------|
| IAM Role | `s3-to-iceberg-lambda-role` | Lambda execution role. Deleting it causes KMS decryption failures and Lambda invocation errors. |
| Inline Policy | `s3-ingest-policy` (on above role) | Contains S3, Athena, Glue, LakeFormation, KMS permissions. |
| IAM User Policy | `AdministratorAccess` on `CodeDeploy` | Removing this blocks all deployment scripts. |

---

## KMS Keys to Exclude

| Key ID | Region | Reason |
|--------|--------|--------|
| `1c4b0282-d7e0-4b58-b0db-513199cd91ad` | eu-west-2 | Used by Lambda service to encrypt environment variables at rest. Modifying this key's policy or revoking access causes `KMSAccessDeniedException` and silently breaks the S3→Lambda trigger. |

---

## Errors Caused When These Were Affected

### 1. KMSAccessDeniedException (Lambda won't start)

```
Lambda was unable to decrypt the environment variables because KMS access was denied.
KMS key: arn:aws:kms:eu-west-2:416558142390:key/1c4b0282-d7e0-4b58-b0db-513199cd91ad
Role: arn:aws:sts::416558142390:assumed-role/s3-to-iceberg-lambda-role/s3-to-iceberg-ingest
```

**Cause:** KMS key policy was modified or the Lambda role lost `kms:Decrypt` permission.

**Impact:** Lambda silently fails — S3 events are dropped with no logs.

**Fix:** Delete and recreate the Lambda:
```powershell
aws lambda delete-function --function-name s3-to-iceberg-ingest --region eu-west-2
py 02_deploy_lambda.py
```

---

### 2. AccessDenied on IAM operations

```
User: arn:aws:iam::416558142390:user/CodeDeploy is not authorized to perform:
iam:CreateRole / s3tables:CreateTableBucket / s3:CreateBucket
```

**Cause:** `AdministratorAccess` policy detached from IAM user `CodeDeploy`.

**Fix:**
```powershell
aws iam attach-user-policy --user-name CodeDeploy --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

---

## Exclusion Config (for AWSResourceTruncate)

```json
{
  "exclude": {
    "iam_roles": ["s3-to-iceberg-lambda-role"],
    "kms_keys": ["1c4b0282-d7e0-4b58-b0db-513199cd91ad"]
  }
}
```
