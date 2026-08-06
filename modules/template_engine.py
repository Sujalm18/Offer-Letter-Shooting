from docxtpl import DocxTemplate
from jinja2 import Template
import re
from typing import Dict, Any

class TemplateEngine:
    @staticmethod
    def normalize_key(key: str) -> str:
        """
        Normalizes a string to a valid Jinja2 variable name.
        Example: "Candidate Name" -> "candidate_name"
        """
        key = str(key).strip().lower()
        key = re.sub(r'[^a-z0-9_]', '_', key)
        key = re.sub(r'_+', '_', key)
        return key.strip('_')

    @staticmethod
    def render_docx(template_path: str, output_path: str, context: Dict[str, Any]):
        """
        Renders a Word document using Jinja2 syntax via docxtpl.
        """
        doc = DocxTemplate(template_path)
        # Normalize context keys just in case
        normalized_context = {TemplateEngine.normalize_key(k): v for k, v in context.items()}
        doc.render(normalized_context)
        doc.save(output_path)

    @staticmethod
    def render_email_body(body_template: str, context: Dict[str, Any]) -> str:
        """
        Renders an email body using Jinja2 syntax.
        """
        template = Template(body_template)
        normalized_context = {TemplateEngine.normalize_key(k): v for k, v in context.items()}
        return template.render(**normalized_context)
