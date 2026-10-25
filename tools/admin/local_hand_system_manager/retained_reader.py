"""Compatibility import for the packaged read-only filesystem recovery reader.

Existing deployed standalone copies retain their original bytes. New callers
use the one implementation included in the verified runtime wheel.
"""
import sys
from local_hand_jobs import retained_filesystem

sys.modules[__name__] = retained_filesystem
