import sys
sys.path.insert(0, 'E:\\LeadStreamAI\\backend')
from app.services.email_service import get_user_email_font, get_user_email_font_size, get_user_signature_font, get_user_signature_font_size

# Test the functions directly
print('get_user_email_font("1"):', repr(get_user_email_font('1')))
print('get_user_email_font_size("1"):', repr(get_user_email_font_size('1')))
print('get_user_signature_font("1"):', repr(get_user_signature_font('1')))
print('get_user_signature_font_size("1"):', repr(get_user_signature_font_size('1')))