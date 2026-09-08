import psycopg2

conn = psycopg2.connect(
    "postgresql://neondb_owner:npg_GVClz25KyMSj@ep-snowy-dew-a1t9xre3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require",
    connect_timeout=10,
)
cur = conn.cursor()

# Check Palak's user_id
cur.execute("SELECT id, username, full_name, role FROM users WHERE LOWER(username) LIKE '%%palak%%'")
print("=== PALAK USER ===")
for r in cur.fetchall():
    print(r)

# Check leads with drafts but NULL user_id
cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_draft IS NOT NULL AND user_id IS NULL")
print(f"\nLeads with draft + user_id=NULL: {cur.fetchone()[0]}")

# Check leads with drafts + user_id=5 (Palak)
cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_draft IS NOT NULL AND user_id = 5")
print(f"Leads with draft + user_id=5 (Palak): {cur.fetchone()[0]}")

# Check pending approval drafts with user_id=5
cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_draft IS NOT NULL AND email_status IN ('PENDING_APPROVAL','SCHEDULED') AND user_id = 5")
print(f"Pending drafts for Palak (user_id=5): {cur.fetchone()[0]}")

# Check all pending approval drafts user_id distribution
cur.execute("SELECT user_id, COUNT(*) FROM leads_raw WHERE email_draft IS NOT NULL AND email_status IN ('PENDING_APPROVAL','SCHEDULED') GROUP BY user_id ORDER BY user_id")
print("\nPending draft distribution by user_id:")
for r in cur.fetchall():
    print(f"  user_id={r[0]}: {r[1]} drafts")

# Check if Palak has drafts but wrong email_status
cur.execute("SELECT email_status, COUNT(*) FROM leads_raw WHERE email_draft IS NOT NULL AND user_id = 5 GROUP BY email_status")
print("\nPalak drafts by status:")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

# Check Palak leads with NULL email_status but have draft
cur.execute("SELECT COUNT(*) FROM leads_raw WHERE email_draft IS NOT NULL AND user_id = 5 AND email_status IS NULL")
print(f"\nPalak drafts with NULL status: {cur.fetchone()[0]}")

# Sample: first 5 Palak pending drafts
cur.execute("SELECT id, first_name, last_name, email, email_status, user_id, draft_template_used FROM leads_raw WHERE email_draft IS NOT NULL AND user_id = 5 LIMIT 5")
print("\nSample Palak drafts:")
for r in cur.fetchall():
    print(f"  id={r[0]}, name={r[1]} {r[2]}, email={r[3]}, status={r[4]}, uid={r[5]}, template={r[6]}")

cur.close()
conn.close()
