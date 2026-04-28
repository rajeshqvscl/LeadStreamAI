import sys
import os

sys.path.append(os.getcwd())

from app.api.gmail import poll_all_users_for_replies

if __name__ == "__main__":
    print("Force polling for lead replies...")
    poll_all_users_for_replies()
    print("Done.")
