"""
AWS Resource Cleanup - Complete Account Resource Deletion Tool

This script deletes ALL resources in an AWS account. Use with extreme caution.
Supports dry-run mode to preview what would be deleted without making changes.

Usage:
    python main.py                  # Run with confirmation prompt
    python main.py --dry-run        # Preview deletions without executing
    python main.py --yes            # Skip confirmation prompt
    python main.py --services ec2 s3  # Only clean specific services
"""

import sys
import argparse
from config import get_session, DRY_RUN, SKIP_CONFIRMATION
from logger import setup_logger
from cleaners import ALL_CLEANERS


SERVICE_MAP = {
    "cloudformation": "CloudFormationCleaner",
    "ecs": "ECSCleaner",
    "rds": "RDSCleaner",
    "lambda": "LambdaCleaner",
    "ec2": "EC2Cleaner",
    "dynamodb": "DynamoDBCleaner",
    "glue": "GlueCleaner",
    "athena": "AthenaCleaner",
    "s3tables": "S3TablesCleaner",
    "s3": "S3Cleaner",
    "sns": "SNSCleaner",
    "sqs": "SQSCleaner",
    "cloudwatch": "CloudWatchCleaner",
    "iam": "IAMCleaner",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="AWS Resource Cleanup - Delete all resources in an AWS account"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=DRY_RUN,
        help="Preview what would be deleted without making changes",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        default=SKIP_CONFIRMATION,
        help="Skip the confirmation prompt",
    )
    parser.add_argument(
        "--services",
        nargs="+",
        choices=list(SERVICE_MAP.keys()),
        help="Only clean specific services (space-separated)",
    )
    return parser.parse_args()


def get_account_info():
    """Get current AWS account and region info for display."""
    session = get_session()
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    return {
        "account_id": identity["Account"],
        "user_arn": identity["Arn"],
        "region": session.region_name,
    }


def confirm_execution(account_info, dry_run):
    """Display warning and get user confirmation."""
    print("\n" + "=" * 70)
    print("  AWS RESOURCE CLEANUP - COMPLETE DELETION")
    print("=" * 70)
    print(f"\n  Account:  {account_info['account_id']}")
    print(f"  Region:   {account_info['region']}")
    print(f"  Caller:   {account_info['user_arn']}")
    print(f"  Mode:     {'DRY RUN (no changes)' if dry_run else 'LIVE DELETION'}")
    print("\n" + "=" * 70)

    if not dry_run:
        print("\n  WARNING: This will PERMANENTLY DELETE all resources in this account.")
        print("  This action is IRREVERSIBLE.\n")
        response = input("  Type 'DELETE ALL' to confirm: ")
        if response != "DELETE ALL":
            print("\n  Aborted. No resources were deleted.")
            sys.exit(0)
    else:
        print("\n  Running in DRY RUN mode. No resources will be deleted.\n")
        input("  Press Enter to continue...")

    print()


def main():
    args = parse_args()
    logger = setup_logger()

    # Override config with CLI args
    if args.dry_run:
        import config
        config.DRY_RUN = True

    try:
        account_info = get_account_info()
    except Exception as e:
        logger.error(f"Could not connect to AWS: {e}")
        logger.error("Check your AWS credentials and region configuration.")
        sys.exit(1)

    if not args.yes:
        confirm_execution(account_info, args.dry_run)

    logger.info("Starting AWS resource cleanup...")
    if args.dry_run:
        logger.info("DRY RUN MODE - No resources will be deleted.")

    # Determine which cleaners to run
    if args.services:
        cleaner_names = [SERVICE_MAP[s] for s in args.services]
        cleaners = [c for c in ALL_CLEANERS if c.__name__ in cleaner_names]
    else:
        cleaners = ALL_CLEANERS

    # Run each cleaner
    success_count = 0
    error_count = 0

    for cleaner_class in cleaners:
        try:
            cleaner = cleaner_class()
            cleaner.run()
            success_count += 1
        except Exception as e:
            logger.error(f"Fatal error in {cleaner_class.display_name}: {e}")
            error_count += 1

    # Summary
    logger.info("=" * 50)
    logger.info("CLEANUP COMPLETE")
    logger.info(f"  Services processed: {success_count + error_count}")
    logger.info(f"  Successful: {success_count}")
    logger.info(f"  Errors: {error_count}")
    if args.dry_run:
        logger.info("  Mode: DRY RUN (no changes were made)")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
