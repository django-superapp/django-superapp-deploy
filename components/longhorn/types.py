"""
Longhorn Component Types

Type definitions for Longhorn component configuration.
"""
from typing import Dict, List, Literal, TypedDict


class LonghornDisk(TypedDict, total=False):
    """Configuration for a Longhorn disk."""
    name: str  # Required name for the disk
    node_selector: Dict[str, str]
    disk_id: str  # Disk ID from /dev/disk/by-id/ for stable identification (required)
    tags: List[str]
    allow_scheduling: bool


class LonghornStorageClass(TypedDict, total=False):
    """Configuration for a Longhorn storage class."""
    name: str
    replica_count: int
    disk_selector: List[str]
    node_selector: List[str]
    is_default: bool
    reclaim_policy: Literal["Delete", "Retain"]
    fs_type: str