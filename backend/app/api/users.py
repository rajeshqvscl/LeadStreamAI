from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional
import hashlib
import os
import logging
from app.database import get_db_connection
import psycopg2
import psycopg2.extras
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

class UserBase(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    role: str = "USER"
    is_active: bool = True
    is_approved: bool = True
    has_db_access: bool = False
    job_title: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_approved: Optional[bool] = None
    has_db_access: Optional[bool] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    password: Optional[str] = None

class ReportRequest(BaseModel):
    target_user_id: Optional[int] = None

@router.get("/users/")
def list_users(role: Optional[str] = None):
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = "SELECT id, username, email, full_name, role, is_active, is_approved, has_db_access, created_at, updated_at, job_title, phone, linkedin_url FROM users"
    params = []
    if role:
        query += " WHERE role = %s"
        params.append(role)
    
    query += " ORDER BY COALESCE(updated_at, created_at) DESC"
    cur.execute(query, params)
    users = cur.fetchall()
    
    cur.close()
    conn.close()
    return {"users": users, "total": len(users)}

@router.post("/users/")
def create_user(user: UserCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Hash password
    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    
    try:
        cur.execute("""
            INSERT INTO users (username, email, full_name, password_hash, role, is_active, is_approved, has_db_access, job_title, phone, linkedin_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, username, email, full_name, role, is_active, is_approved, has_db_access, created_at, updated_at, job_title, phone, linkedin_url
        """, (user.username, user.email, user.full_name, password_hash, user.role, user.is_active, user.is_approved, user.has_db_access, user.job_title, user.phone, user.linkedin_url))
        
        new_user = cur.fetchone()
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Username or email already exists")
    finally:
        cur.close()
        conn.close()
        
    return new_user

@router.put("/users/{user_id}")
def update_user(user_id: int, user: UserUpdate):
    conn = get_db_connection()
    cur = conn.cursor()
    
    update_data = user.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    if "password" in update_data:
        update_data["password_hash"] = hashlib.sha256(update_data.pop("password").encode()).hexdigest()
        
    set_clause = ", ".join([f"{k} = %s" for k in update_data.keys()])
    params = list(update_data.values())
    params.append(user_id)
    
    cur.execute(f"UPDATE users SET {set_clause}, updated_at = NOW() WHERE id = %s RETURNING id, username, email, full_name, role, is_active, is_approved, has_db_access, created_at, updated_at, job_title, phone, linkedin_url", params)
    updated_user = cur.fetchone()
    
    if not updated_user:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
        
    conn.commit()
    cur.close()
    conn.close()
    return updated_user

@router.delete("/users/{user_id}")
def delete_user(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Actually deactivate instead of delete for safety
    cur.execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user_id,))
    
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
        
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "User suspended successfully"}

@router.post("/users/{user_id}/resume")
def resume_user(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("UPDATE users SET is_active = TRUE WHERE id = %s", (user_id,))
    
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
        
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "User resumed successfully"}

@router.delete("/users/{user_id}/hard")
def hard_delete_user(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
        
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "User record permanently deleted"}

def normalize_user_id(user_id: Optional[str]) -> str:
    """Normalizes the user ID from the header to a valid database ID."""
    if not user_id or user_id.strip() == "" or user_id.lower() == "admin":
        return "1"
    return user_id

@router.get("/users/productivity")
def get_user_productivity(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Returns work volume stats for each user (Admin only, REAL DATA)."""
    uid = normalize_user_id(user_id)
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Verify Admin Privilege
        cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
        caller = cur.fetchone()
        if not caller or caller['role'] != 'ADMIN':
            raise HTTPException(status_code=403, detail="Unauthorized: Admin access required")
            
        # 1. Count actual leads from leads_raw
        cur.execute("""
            SELECT u.username, u.full_name, u.credits_used, COUNT(l.id) as count
            FROM users u
            LEFT JOIN leads_raw l ON u.id = l.user_id
            WHERE l.created_at > NOW() - INTERVAL '30 days'
            GROUP BY u.username, u.full_name, u.credits_used
        """)
        lead_rows = cur.fetchall()
        
        # 2. Count other activities from activity_log
        cur.execute("""
            SELECT u.username, u.full_name, al.action, COUNT(*) as count
            FROM activity_log al
            JOIN users u ON al.user_id = u.id
            WHERE al.created_at > NOW() - INTERVAL '30 days'
            AND al.action NOT IN ('LEAD_SEARCH', 'BULK_INGESTION', 'LEAD_INGESTED')
            GROUP BY u.username, u.full_name, al.action
        """)
        activity_rows = cur.fetchall()
        
        stats = {}
        
        # Initialize with lead counts
        for r in lead_rows:
            uname = r['full_name'] or r['username']
            stats[uname] = {"name": uname, "leads": r['count'], "outreach": 0, "valid": 0, "credits": r.get('credits_used') or 0}
            
        # Add activity counts
        for r in activity_rows:
            uname = r['full_name'] or r['username']
            if uname not in stats:
                stats[uname] = {"name": uname, "leads": 0, "outreach": 0, "valid": 0, "credits": 0}
            
            action = r['action']
            count = r['count']
            
            if action in ('BULK_DRAFT_GENERATE', 'SENT', 'EMAIL_SENT'):
                stats[uname]['outreach'] += count
            elif action in ('BULK_DOMAIN_APPROVE'):
                stats[uname]['valid'] += count
            
        return list(stats.values())
    finally:
        cur.close()
        conn.close()

@router.get("/users/active")
def get_active_users(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Returns users who have been active in the last 24 hours (Admin only)."""
    uid = normalize_user_id(user_id)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cur.execute("SELECT role FROM users WHERE id = %s", (uid,))
        caller = cur.fetchone()
        if not caller or caller['role'] != 'ADMIN':
            raise HTTPException(status_code=403, detail="Unauthorized")

        cur.execute("""
            SELECT DISTINCT u.id, u.username, u.full_name, u.email, MAX(al.created_at) as last_active
            FROM users u
            JOIN activity_log al ON u.id = al.user_id
            WHERE al.created_at > NOW() - INTERVAL '15 minutes'
            GROUP BY u.id, u.username, u.full_name, u.email
            ORDER BY last_active DESC
        """)
        active_users = [dict(r) for r in cur.fetchall()]
        
        # Format dates
        for u in active_users:
            u['last_active'] = u['last_active'].isoformat()
            
        return active_users
    finally:
        cur.close()
        conn.close()

@router.post("/users/report")
def trigger_admin_report(req: ReportRequest, user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Manually triggers the activity report email to the admin with detailed metrics."""
    from app.services.email_service import send_admin_report
    uid = normalize_user_id(user_id)
    target_user_id = req.target_user_id
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cur.execute("SELECT email, role FROM users WHERE id = %s", (uid,))
        admin = cur.fetchone()
        if not admin or admin['role'] != 'ADMIN':
            raise HTTPException(status_code=403, detail="Unauthorized")

        # Determine filtering scope
        where_filter = ""
        params = []
        target_name = "Full System"

        if target_user_id:
            where_filter = "AND al.user_id = %s"
            params.append(target_user_id)
            cur.execute("SELECT username, full_name FROM users WHERE id = %s", (target_user_id,))
            tu = cur.fetchone()
            if tu:
                target_name = tu['full_name'] or tu['username']

        # Aggregate specific user actions (last 30 days for MIS scope) using direct leads_raw count
        stats_query = """
            SELECT u.username, 
                   (SELECT COUNT(*) FROM leads_raw l WHERE l.user_id = u.id AND l.created_at > NOW() - INTERVAL '30 days') as leads_count,
                   (SELECT COUNT(*) FROM activity_log al WHERE al.user_id = u.id AND al.action IN ('SENT', 'EMAIL_SENT') AND al.created_at > NOW() - INTERVAL '30 days') as sent_count,
                   (SELECT COUNT(*) FROM activity_log al WHERE al.user_id = u.id AND al.created_at > NOW() - INTERVAL '30 days') as total_count
            FROM users u
            WHERE 1=1
        """
        if target_user_id:
            stats_query += " AND u.id = %s"
            cur.execute(stats_query, (target_user_id,))
        else:
            cur.execute(stats_query)
            
        user_stats = [dict(r) for r in cur.fetchall()]

        # Fetch last 10 actions for this scope
        cur.execute(f"""
            SELECT u.username, al.action, al.created_at
            FROM activity_log al
            JOIN users u ON al.user_id = u.id
            WHERE 1=1 {where_filter}
            ORDER BY al.created_at DESC
            LIMIT 10
        """, params)
        recent_logs = []
        for r in cur.fetchall():
            log = dict(r)
            if log.get('created_at'):
                log['created_at'] = log['created_at'].isoformat()
            recent_logs.append(log)
        
        report_data = {
            "user_stats": user_stats,
            "recent_logs": recent_logs,
            "target_user": target_name,
            "environment": os.getenv("ENVIRONMENT", "Production")
        }
        
        # Build comprehensive Excel file with Charts
        import io
        import base64
        import xlsxwriter
        
        lead_query = """
            SELECT l.first_name, l.last_name, l.email, l.company_name, l.validation_status, 
                   l.persona, l.email_status, l.manual_entry, l.created_at, u.username as owner, u.full_name
            FROM leads_raw l
            LEFT JOIN users u ON l.user_id = u.id
            WHERE 1=1
        """
        lead_params = []
        if target_user_id:
            lead_query += " AND l.user_id = %s"
            lead_params.append(target_user_id)
            
        cur.execute(lead_query + " ORDER BY l.created_at DESC LIMIT 5000", lead_params)
        leads = cur.fetchall()
        
        if leads:
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet('Leads Data')
            
            headers = ['Owner', 'First Name', 'Last Name', 'Email', 'Company', 'Validation Status', 'Persona', 'Outreach Status', 'Manual Entry', 'Created At']
            header_format = workbook.add_format({'bold': True, 'bg_color': '#4F46E5', 'font_color': 'white'})
            
            for col_num, data in enumerate(headers):
                worksheet.write(0, col_num, data, header_format)
                
            status_counts = {'NOT STARTED': 0, 'PENDING_APPROVAL': 0, 'APPROVED': 0, 'SENT': 0, 'SCHEDULED': 0}
            
            for row_num, l in enumerate(leads, 1):
                owner_name = l.get('full_name') or l.get('owner') or 'System'
                worksheet.write(row_num, 0, owner_name)
                worksheet.write(row_num, 1, l.get('first_name') or '')
                worksheet.write(row_num, 2, l.get('last_name') or '')
                worksheet.write(row_num, 3, l.get('email') or '')
                worksheet.write(row_num, 4, l.get('company_name') or '')
                worksheet.write(row_num, 5, l.get('validation_status') or 'PENDING')
                worksheet.write(row_num, 6, l.get('persona') or 'UNKNOWN')
                
                raw_status = l.get('email_status') or 'NOT STARTED'
                if raw_status in ('', 'PENDING'): status = 'NOT STARTED'
                else: status = raw_status
                
                worksheet.write(row_num, 7, status)
                
                if status in status_counts:
                    status_counts[status] += 1
                    
                worksheet.write(row_num, 8, 'YES' if l.get('manual_entry') else 'NO')
                worksheet.write(row_num, 9, l['created_at'].strftime('%Y-%m-%d %H:%M') if l.get('created_at') else '')

            worksheet.set_column(0, 4, 20)
            worksheet.set_column(5, 7, 18)
            worksheet.set_column(9, 9, 20)
            
            # Analytics Chart Sheet
            chart_sheet = workbook.add_worksheet('Analytics')
            chart_sheet.write_column('A1', ['Not Started', 'Drafts Ready', 'Approved', 'Sent', 'Scheduled'])
            chart_sheet.write_column('B1', [
                status_counts['NOT STARTED'],
                status_counts['PENDING_APPROVAL'],
                status_counts['APPROVED'],
                status_counts['SENT'],
                status_counts['SCHEDULED']
            ])
            
            chart = workbook.add_chart({'type': 'column'})
            chart.add_series({
                'name': 'Outreach Pipeline',
                'categories': ['Analytics', 0, 0, 4, 0],
                'values':     ['Analytics', 0, 1, 4, 1],
                'data_labels': {'value': True},
                'fill':   {'color': '#6366f1'}
            })
            chart.set_title({'name': f"Pipeline Analytics for {target_name}"})
            chart.set_x_axis({'name': 'Current Status'})
            chart.set_y_axis({'name': 'Number of Leads'})
            
            chart_sheet.insert_chart('D2', chart, {'x_scale': 1.5, 'y_scale': 1.5})
            
            workbook.close()
            xlsx_content = output.getvalue()
            xlsx_b64 = base64.b64encode(xlsx_content).decode('utf-8')
            
            report_data["attachments"] = [
                {
                    "content": xlsx_b64,
                    "filename": f"MIS_Report_{target_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                }
            ]

        
        try:
            success = send_admin_report(admin['email'], report_data)
            if success:
                return {"message": f"System activity report dispatched to {admin['email']}"}
            else:
                return {
                    "message": "Report generation bypassed dispatch.",
                    "detail": "SMTP configuration not found or failed. Check logs.",
                    "is_warning": True
                }
        except Exception as e:
            logger.error(f"Report Dispatch Error: {str(e)}")
            return {"message": f"Dispatch failure: {str(e)}", "error": True}
    finally:
        cur.close()
        conn.close()

@router.get("/users/my-history")
def get_my_history(user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """Retrieves personal activity log for the current user."""
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Normalize ID (handles 'admin' string etc if needed, but endpoint is for users)
    real_uid = user_id if user_id and user_id.isdigit() else "1"
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cur.execute("""
            SELECT 
                al.*, 
                l.first_name || ' ' || l.last_name as lead_name,
                l.email as lead_email,
                l.company_name as lead_company
            FROM activity_log al
            LEFT JOIN leads_raw l ON al.lead_id = l.id
            WHERE al.user_id = %s
            ORDER BY al.created_at DESC
            LIMIT 200
        """, (real_uid,))
        
        logs = [dict(r) for r in cur.fetchall()]
        
        # Serialization fix
        for log in logs:
            if log.get("created_at"):
                log["created_at"] = log["created_at"].isoformat()
                
        return logs
    finally:
        cur.close()
        conn.close()
        cur.close()
        conn.close()
