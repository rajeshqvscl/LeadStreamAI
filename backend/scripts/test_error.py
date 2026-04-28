import sys
sys.path.append('.')
from app.api.drafts import get_pending_drafts
import traceback

try:
    print("Testing get_pending_drafts...")
    get_pending_drafts(page=1)
    print("Success")
except Exception as e:
    traceback.print_exc()
