import pandas as pd
import re
from typing import List, Tuple
from modules.models import ValidationResult
from modules.template_engine import TemplateEngine

class ValidatorService:
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

    @classmethod
    def validate_excel(cls, df: pd.DataFrame, required_fields: List[str] = None) -> ValidationResult:
        if required_fields is None:
            required_fields = ["candidate_name", "email"]
            
        warnings = []
        errors = []
        
        # Normalize columns
        df.columns = [TemplateEngine.normalize_key(col) for col in df.columns]
        
        # Check required fields
        for field in required_fields:
            if field not in df.columns:
                errors.append(f"Missing required column: {field}")
                
        if errors:
            return ValidationResult(
                is_valid=False,
                health_score=0.0,
                total_rows=len(df),
                valid_rows=0,
                invalid_emails=0,
                duplicates=0,
                missing_fields=len(df),
                warnings=warnings,
                errors=errors,
                cleaned_df=None
            )

        total_rows = len(df)
        
        # Remove empty rows
        df = df.dropna(how='all')
        
        # Find duplicates
        if "email" in df.columns:
            duplicates_mask = df.duplicated(subset=['email'], keep='first')
            duplicates = duplicates_mask.sum()
            df = df[~duplicates_mask]
            
            # Find invalid emails
            valid_email_mask = df['email'].astype(str).str.match(cls.EMAIL_REGEX)
            invalid_emails = (~valid_email_mask).sum()
            df = df[valid_email_mask]
        else:
            duplicates = 0
            invalid_emails = 0
            
        valid_rows = len(df)
        
        # Missing fields in rows
        missing_fields_mask = df[required_fields].isnull().any(axis=1) | (df[required_fields] == "").any(axis=1)
        missing_fields = missing_fields_mask.sum()
        df = df[~missing_fields_mask]
        
        valid_rows = len(df)
        
        health_score = (valid_rows / total_rows * 100) if total_rows > 0 else 0
        is_valid = valid_rows > 0
        
        if duplicates > 0:
            warnings.append(f"Removed {duplicates} duplicate emails.")
        if invalid_emails > 0:
            warnings.append(f"Removed {invalid_emails} invalid emails.")
        if missing_fields > 0:
            warnings.append(f"Removed {missing_fields} rows with missing required fields.")
            
        return ValidationResult(
            is_valid=is_valid,
            health_score=health_score,
            total_rows=total_rows,
            valid_rows=valid_rows,
            invalid_emails=invalid_emails,
            duplicates=duplicates,
            missing_fields=missing_fields,
            warnings=warnings,
            errors=errors,
            cleaned_df=df
        )

    @classmethod
    def validate_template_variables(cls, docx_path: str, df_columns: List[str]) -> Tuple[bool, List[str], List[str]]:
        """
        Validates if the template variables match the dataframe columns.
        Returns (is_valid, found_vars, missing_vars)
        """
        try:
            from docxtpl import DocxTemplate
            doc = DocxTemplate(docx_path)
            # A hacky way to extract variables without rendering
            # docxtpl uses jinja2 internally.
            import jinja2.meta
            env = jinja2.Environment()
            
            # Read all xml sources
            xml_src = ""
            for xml in doc.xml_to_string_list():
                xml_src += xml
                
            ast = env.parse(xml_src)
            template_vars = jinja2.meta.find_undeclared_variables(ast)
            
            normalized_cols = [TemplateEngine.normalize_key(col) for col in df_columns]
            missing_vars = [var for var in template_vars if var not in normalized_cols]
            
            is_valid = len(missing_vars) == 0
            return is_valid, list(template_vars), missing_vars
        except Exception as e:
            return False, [], [f"Error parsing template: {str(e)}"]
