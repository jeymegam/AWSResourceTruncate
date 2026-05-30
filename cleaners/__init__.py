"""AWS Resource Cleaners package."""

from cleaners.ec2 import EC2Cleaner
from cleaners.s3 import S3Cleaner
from cleaners.s3_tables import S3TablesCleaner
from cleaners.iam import IAMCleaner
from cleaners.dynamodb import DynamoDBCleaner
from cleaners.glue import GlueCleaner
from cleaners.athena import AthenaCleaner
from cleaners.lambda_cleaner import LambdaCleaner
from cleaners.cloudformation import CloudFormationCleaner
from cleaners.rds import RDSCleaner
from cleaners.ecs import ECSCleaner
from cleaners.sns import SNSCleaner
from cleaners.sqs import SQSCleaner
from cleaners.cloudwatch import CloudWatchCleaner

ALL_CLEANERS = [
    CloudFormationCleaner,
    ECSCleaner,
    RDSCleaner,
    LambdaCleaner,
    EC2Cleaner,
    DynamoDBCleaner,
    GlueCleaner,
    AthenaCleaner,
    S3TablesCleaner,
    S3Cleaner,
    SNSCleaner,
    SQSCleaner,
    CloudWatchCleaner,
    IAMCleaner,
]
