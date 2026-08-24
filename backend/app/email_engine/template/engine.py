"""
Template Engine - Jinja2 with SandboxedEnvironment
Loads templates from database (prompts table) and filesystem.
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound
from jinja2.sandbox import SandboxedEnvironment
from app.core.config import get_email_engine_settings
from app.database import get_db_connection
import logging

logger = logging.getLogger(__name__)

# Global template environment (created lazily)
_env: Optional[SandboxedEnvironment] = None


def get_template_env() -> SandboxedEnvironment:
    """Get or create Jinja2 sandboxed environment"""
    global _env
    if _env is None:
        settings = get_email_engine_settings()
        template_dir = settings.template_dir
        
        # Create directory if not exists
        os.makedirs(template_dir, exist_ok=True)
        
        loader = FileSystemLoader(template_dir)
        _env = SandboxedEnvironment(
            loader=loader,
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
            cache_size=settings.template_cache_size,
        )
        
        # Add custom filters
        _env.filters['format_currency'] = format_currency_filter
        _env.filters['truncate_words'] = truncate_words_filter
        _env.filters['markdownify'] = markdownify_filter
        
        # Add globals
        _env.globals['current_year'] = lambda: datetime.now().year
        
        logger.info(f"Initialized Jinja2 environment: {template_dir}")
    
    return _env


def format_currency_filter(value: Any) -> str:
    """Format number as currency"""
    if value is None:
        return ""
    try:
        num = float(value)
        if num >= 1e7:  # 1 crore
            return f"₹{num/1e7:.2f} Cr"
        elif num >= 1e5:  # 1 lakh
            return f"₹{num/1e5:.2f} L"
        else:
            return f"₹{num:,.0f}"
    except (ValueError, TypeError):
        return str(value)


def truncate_words_filter(text: str, length: int = 50) -> str:
    """Truncate text to word boundary"""
    if not text:
        return ""
    words = text.split()
    if len(words) <= length:
        return text
    return ' '.join(words[:length]) + '...'


def markdownify_filter(text: str) -> str:
    """Convert markdown to HTML"""
    import markdown
    return markdown.markdown(text, extensions=['extra', 'nl2br'])


class DBTemplateLoader:
    """Loads templates from prompts table"""
    
    @staticmethod
    def load_campaign_template(campaign_key: str, stage: int) -> Optional[str]:
        """Load follow-up template from prompts table"""
        # First try to find a CUSTOM_DRAFT prompt matching campaign
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT followup_1, followup_2, followup_3, content, subject
                FROM prompts 
                WHERE prompt_type = 'CUSTOM_DRAFT' 
                  AND is_active = TRUE
                  AND (name ILIKE %s OR name ILIKE %s)
                ORDER BY created_at DESC
                LIMIT 1
            """, (f"%{campaign_key.lower()}%", f"%{campaign_key.replace('_', ' ').lower()}%"))
            
            row = cur.fetchone()
            if row:
                followup_key = f'followup_{stage}'
                if row[0] and stage == 1:
                    return row[0]
                elif row[1] and stage == 2:
                    return row[1]
                elif row[2] and stage == 3:
                    return row[2]
                elif row[3]:  # content field
                    return row[3]
            
            return None
        finally:
            cur.close()
            conn.close()
    
    @staticmethod
    def load_prompt_template(prompt_name: str) -> Optional[Dict[str, Any]]:
        """Load full prompt template by name"""
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT name, content, subject, cc, followup_1, followup_2, followup_3, followup_count, attachment_file
                FROM prompts 
                WHERE name = %s AND prompt_type = 'CUSTOM_DRAFT' AND is_active = TRUE
            """, (prompt_name,))
            
            row = cur.fetchone()
            if row:
                return {
                    'name': row[0],
                    'content': row[1],
                    'subject': row[2],
                    'cc': row[3],
                    'followup_1': row[4],
                    'followup_2': row[5],
                    'followup_3': row[6],
                    'followup_count': row[7],
                    'attachment_file': row[8],
                }
            return None
        finally:
            cur.close()
            conn.close()


class TemplateEngine:
    """
    High-level template rendering engine.
    Supports both filesystem templates (for layouts) and DB templates (for content).
    """
    
    def __init__(self):
        self.env = get_template_env()
        self.db_loader = DBTemplateLoader()
    
    def render_layout(self, layout_name: str, context: Dict[str, Any]) -> str:
        """Render a layout template (base.html, outreach.html, etc.)"""
        try:
            template = self.env.get_template(f"layouts/{layout_name}.html")
            return template.render(**context)
        except TemplateNotFound:
            # Fallback to base layout
            template = self.env.get_template("base.html")
            return template.render(**context)
    
    def render_campaign(self, campaign_key: str, stage: int, context: Dict[str, Any]) -> str:
        """Render campaign-specific template"""
        # Try DB first
        db_template = self.db_loader.load_campaign_template(campaign_key, stage)
        if db_template:
            template = self.env.from_string(db_template)
            return template.render(**context)
        
        # Fallback to filesystem
        try:
            template = self.env.get_template(f"campaigns/{campaign_key.lower()}.html")
            return template.render(**context)
        except TemplateNotFound:
            # Final fallback to generic
            template = self.env.get_template("campaigns/investor_generic.html")
            return template.render(**context)
    
    def render_component(self, component_name: str, context: Dict[str, Any]) -> str:
        """Render a component (signature, unsubscribe_footer, tracking_pixel)"""
        try:
            template = self.env.get_template(f"components/{component_name}.html")
            return template.render(**context)
        except TemplateNotFound:
            logger.warning(f"Component template not found: {component_name}")
            return ""
    
    def render_string(self, template_string: str, context: Dict[str, Any]) -> str:
        """Render arbitrary template string"""
        template = self.env.from_string(template_string)
        return template.render(**context)


# Singleton
_template_engine: Optional[TemplateEngine] = None


def get_template_engine() -> TemplateEngine:
    global _template_engine
    if _template_engine is None:
        _template_engine = TemplateEngine()
    return _template_engine


def render_email(
    layout: str,
    campaign_key: str,
    stage: int,
    context: Dict[str, Any],
) -> str:
    """
    Convenience function: render complete email with layout + campaign + components.
    """
    engine = get_template_engine()
    
    # Build base context with common variables
    base_context = {
        'subject': context.get('subject', ''),
        'body': context.get('body', ''),
        'signature': context.get('signature', ''),
        'unsubscribe_url': context.get('unsubscribe_url', ''),
        'tracking_pixel': context.get('tracking_pixel', ''),
        'font_family': context.get('font_family', 'sans-serif'),
        'font_size': context.get('font_size', '15px'),
        **context,
    }
    
    # Render campaign content
    campaign_html = engine.render_campaign(campaign_key, stage, base_context)
    
    # Render layout with campaign content
    base_context['content'] = campaign_html
    return engine.render_layout(layout, base_context)