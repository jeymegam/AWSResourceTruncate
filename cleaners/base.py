"""Base class for all resource cleaners."""

from abc import ABC, abstractmethod
from logger import setup_logger
from config import get_client, get_resource, DRY_RUN


class BaseCleaner(ABC):
    """Abstract base class for AWS resource cleaners."""

    service_name = ""
    display_name = ""

    def __init__(self):
        self.logger = setup_logger()
        self.dry_run = DRY_RUN

    def get_client(self, service=None):
        """Get a boto3 client for this cleaner's service."""
        return get_client(service or self.service_name)

    def get_resource(self, service=None):
        """Get a boto3 resource for this cleaner's service."""
        return get_resource(service or self.service_name)

    def log_delete(self, resource_type, resource_id):
        """Log a deletion action."""
        prefix = "[DRY RUN] Would delete" if self.dry_run else "Deleted"
        self.logger.info(f"{prefix} {resource_type}: {resource_id}")

    def log_error(self, message, error):
        """Log an error."""
        self.logger.error(f"{message}: {error}")

    def log_skip(self, resource_type, resource_id, reason):
        """Log a skipped resource."""
        self.logger.warning(f"Skipped {resource_type} {resource_id}: {reason}")

    @abstractmethod
    def clean(self):
        """Execute the cleanup. Must be implemented by subclasses."""
        pass

    def run(self):
        """Run the cleaner with error handling."""
        self.logger.info(f"--- Cleaning {self.display_name} ---")
        try:
            self.clean()
        except Exception as e:
            self.log_error(f"{self.display_name} cleanup failed", e)
        self.logger.info(f"--- Finished {self.display_name} ---\n")
