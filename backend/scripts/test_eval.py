r = {"scheduled_at": None, "updated_at": None, "email_status": "APPROVED", "email_approved_by": None}
print("updated_at:", r.get("updated_at", "").isoformat() if r.get("updated_at") and hasattr(r.get("updated_at"), 'isoformat') else str(r.get("updated_at")) if r.get("updated_at") else "")
print("scheduled_at:", r.get("scheduled_at").isoformat() + "Z" if r.get("scheduled_at") and hasattr(r.get("scheduled_at"), 'isoformat') else str(r.get("scheduled_at")) if r.get("scheduled_at") else "")
print("Success!")
