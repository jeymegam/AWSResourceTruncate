"""
AWS Resource Cleanup - Legacy Entry Point

This file is kept for backward compatibility.
Use main.py for the full-featured CLI interface.

Usage:
    python main.py                     # Interactive with confirmation
    python main.py --dry-run           # Preview without deleting
    python main.py --services ec2 s3   # Target specific services
    python main.py --yes               # Skip confirmation
"""

from main import main

if __name__ == "__main__":
    main()
