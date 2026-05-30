"""Configuration module for AWS Resource Cleanup."""

import os
import boto3
from dotenv import load_dotenv

load_dotenv()

# AWS Configuration
AWS_PROFILE = os.getenv("AWS_PROFILE", "default")
AWS_REGION = os.getenv("AWS_REGION", None)

# Cleanup behavior
SKIP_CONFIRMATION = os.getenv("SKIP_CONFIRMATION", "false").lower() == "true"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"


def get_session():
    """Create a boto3 session with configured profile and region."""
    kwargs = {}
    if AWS_PROFILE:
        kwargs["profile_name"] = AWS_PROFILE
    if AWS_REGION:
        kwargs["region_name"] = AWS_REGION
    return boto3.Session(**kwargs)


def get_client(service_name):
    """Get a boto3 client for the specified service."""
    return get_session().client(service_name)


def get_resource(service_name):
    """Get a boto3 resource for the specified service."""
    return get_session().resource(service_name)
