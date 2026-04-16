import os
import sys
from pathlib import Path

# Add app to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.api.metrics import get_metrics
from fastapi import Header

try:
    print("Testing get_metrics(user_id=None)...")
    res = get_metrics(user_id=None)
    print("Success:", res.keys())
except Exception as e:
    import traceback
    print("Caught Exception:")
    traceback.print_exc()
