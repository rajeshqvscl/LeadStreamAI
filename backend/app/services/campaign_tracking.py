import psycopg2
from app.database import get_db_connection
from datetime import datetime
import uuid

class CampaignTrackingService:
    @staticmethod
    def add_recipient(campaign_id, lead_id):
        conn = get_db_connection()
        cur = conn.cursor()
        
        token = str(uuid.uuid4())
        try:
            cur.execute("""
                INSERT INTO recipients (campaign_id, lead_id, tracking_token)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (campaign_id, lead_id, token))
            recipient_id = cur.fetchone()['id']
            conn.commit()
            return recipient_id, token
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def log_event(campaign_id, recipient_id, event_type, ip_address=None, user_agent=None):
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO campaign_events (campaign_id, recipient_id, event_type, ip_address, user_agent)
                VALUES (%s, %s, %s, %s, %s)
            """, (campaign_id, recipient_id, event_type, ip_address, user_agent))
            
            if event_type == 'SENT':
                cur.execute("UPDATE recipients SET status = 'SENT', sent_at = NOW() WHERE id = %s", (recipient_id,))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def get_recipient_by_token(token):
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("SELECT * FROM recipients WHERE tracking_token = %s", (token,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row
