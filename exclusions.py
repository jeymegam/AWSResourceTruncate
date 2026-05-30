"""
Resource Exclusions Configuration

Resources listed here are PROTECTED from deletion. They support shared
infrastructure (AWSProject1 ETL pipeline) and deleting them causes
KMS decryption failures, Lambda invocation errors, and deployment blocks.

See RESOURCE_EXCLUSIONS.md for full context on why these are excluded.
"""

# IAM roles that must NOT be deleted
EXCLUDED_IAM_ROLES = [
    "s3-to-iceberg-lambda-role",
]

# Inline policies on excluded roles that must NOT be deleted
EXCLUDED_INLINE_POLICIES = {
    "s3-to-iceberg-lambda-role": ["s3-ingest-policy"],
}

# IAM users whose policies must NOT be detached or modified
EXCLUDED_IAM_USERS = [
    "CodeDeploy",
]

# Specific managed policies that must NOT be detached from specific users
# Format: { "UserName": ["PolicyArn", ...] }
EXCLUDED_USER_POLICIES = {
    "CodeDeploy": ["arn:aws:iam::aws:policy/AdministratorAccess"],
}

# KMS Key IDs that must NOT be scheduled for deletion or have policies modified
EXCLUDED_KMS_KEYS = [
    "1c4b0282-d7e0-4b58-b0db-513199cd91ad",
]
