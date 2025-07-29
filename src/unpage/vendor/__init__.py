"""
Vendored dependencies for unpage.
"""

# Re-export vendored packages
import sys
from pathlib import Path

# Add the vendor directory to sys.path
vendor_dir = Path(__file__).parent
if str(vendor_dir) not in sys.path:
    sys.path.insert(0, str(vendor_dir))
