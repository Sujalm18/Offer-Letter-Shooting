import streamlit as st
import pandas as pd
import os
import yaml
from datetime import datetime

# Initialize backend services
from modules.storage_service import SQLiteStorageService
from modules.email_service import EmailWorker
from modules.offer_generator import OfferGenerator
from modules.report_service import ReportService
from modules.pdf_service import PdfService
from modules.campaign_manager import CampaignManager
from modules.validators import ValidatorService
from modules.logger_service import log_service
from modules.constants import PRIMARY_COLOR, ACCENT_COLOR, BG_COLOR, CARD_BG, UPLOADS_DIR

# --- Dependency Injection Setup ---
@st.cache_resource
def get_services():
    storage = SQLiteStorageService()
    log_service.set_db_callback(storage.write_log)
    pdf = PdfService()
    offer = OfferGenerator(pdf)
    email = EmailWorker(storage)
    report = ReportService(storage)
    manager = CampaignManager(storage, email, offer, report)
    
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(os.path.join(UPLOADS_DIR, "excel"), exist_ok=True)
    os.makedirs(os.path.join(UPLOADS_DIR, "templates"), exist_ok=True)
    
    return storage, manager, pdf

storage, campaign_manager, pdf_service = get_services()

# --- Page Config & CSS ---
st.set_page_config(page_title="Navyanta HRMS", layout="wide")

st.markdown(f"""
<style>
    .stApp {{
        background-color: {BG_COLOR};
    }}
    .css-1d391kg {{
        background-color: {CARD_BG};
    }}
    h1, h2, h3 {{
        color: {PRIMARY_COLOR};
        font-family: 'Inter', sans-serif;
    }}
    .stButton>button {{
        background-color: {ACCENT_COLOR};
        color: white;
        border-radius: 6px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
    }}
    .stButton>button:hover {{
        background-color: {PRIMARY_COLOR};
        color: white;
    }}
    .card {{
        background: {CARD_BG};
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
    }}
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'page' not in st.session_state:
    st.session_state.page = "Dashboard"
if 'wizard_step' not in st.session_state:
    st.session_state.wizard_step = 1
if 'campaign_id' not in st.session_state:
    st.session_state.campaign_id = None
if 'df' not in st.session_state:
    st.session_state.df = None
if 'template_path' not in st.session_state:
    st.session_state.template_path = None
if 'val_result' not in st.session_state:
    st.session_state.val_result = None

# --- Sidebar Navigation ---
with st.sidebar:
    st.title("Navyanta HRMS")
    if st.button("📊 Dashboard"): st.session_state.page = "Dashboard"
    if st.button("🚀 New Campaign"): 
        st.session_state.page = "Wizard"
        st.session_state.wizard_step = 1
    if st.button("🔍 Search & Reports"): st.session_state.page = "Search"
    if st.button("⚙ Settings"): st.session_state.page = "Settings"

# --- Interrupted Campaign Check ---
interrupted = campaign_manager.get_interrupted_campaign()
if interrupted and st.session_state.page == "Dashboard" and st.session_state.get('prompt_recovery', True):
    st.warning(f"⚠ Interrupted campaign detected: **{interrupted.name}**")
    col1, col2 = st.columns(2)
    if col1.button("▶ Resume Campaign"):
        st.session_state.campaign_id = interrupted.id
        st.session_state.page = "Wizard"
        st.session_state.wizard_step = 7 # Jump to Send Offers
        st.session_state.prompt_recovery = False
        st.rerun()
    if col2.button("Discard"):
        storage.update_campaign_status(interrupted.id, "Cancelled")
        st.session_state.prompt_recovery = False
        st.rerun()

# --- Page Routing ---
if st.session_state.page == "Dashboard":
    st.header("📊 Dashboard")
    st.markdown("<div class='card'>Welcome to Navyanta HR Document Automation System. Select a menu option to get started.</div>", unsafe_allow_html=True)
    
    with st.expander("Recent Campaigns", expanded=True):
        with storage.get_connection() as conn:
            df_camp = pd.read_sql("SELECT name, doc_type, status, created_at FROM campaigns ORDER BY created_at DESC LIMIT 5", conn)
            st.dataframe(df_camp, use_container_width=True)

elif st.session_state.page == "Settings":
    st.header("⚙ System Health & Settings")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Dependencies")
        st.write(f"✅ SQLite Database ({storage.db_path})")
        st.write(f"{'✅' if pdf_service.word_installed else '❌'} Microsoft Word (docx2pdf)")
        st.write(f"{'✅' if pdf_service.libreoffice_installed else '❌'} LibreOffice Headless")
        if not pdf_service.word_installed and not pdf_service.libreoffice_installed:
            st.error("No PDF rendering engine available. PDF generation will fail.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("SMTP Configuration")
        from config import config
        st.write(f"**Server:** {config.SMTP_SERVER}:{config.SMTP_PORT}")
        st.write(f"**Email:** {config.SMTP_EMAIL}")
        st.write(f"**Retry Count:** {config.RETRY_COUNT}")
        st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.page == "Search":
    st.header("🔍 Search Documents")
    query = st.text_input("Search by Candidate Name, Email, or Doc Number")
    if query:
        results = storage.search_documents(query)
        if results:
            st.dataframe(pd.DataFrame(results)[['doc_number', 'candidate_name', 'email', 'campaign_name', 'status']])
        else:
            st.info("No documents found.")

elif st.session_state.page == "Wizard":
    st.header("🚀 Campaign Wizard")
    
    # Progress Bar
    progress = (st.session_state.wizard_step - 1) / 6
    st.progress(progress)
    
    if st.session_state.wizard_step == 1:
        st.subheader("Step 1: Create Campaign")
        
        doc_types = list(campaign_manager.doc_types.keys())
        doc_type = st.selectbox("Document Type", doc_types, format_func=lambda x: campaign_manager.doc_types[x]['name'])
        
        campaign_name = st.text_input("Campaign Name (e.g. Autoline August 2026)")
        client_code = st.text_input("Client Code (e.g. ATL)")
        
        st.markdown("---")
        subject = st.text_input("Email Subject")
        body_template = st.text_area("Email Body Template (Jinja2)")
        
        if st.button("Next: Upload Data ➡"):
            if not campaign_name or not client_code:
                st.error("Please fill in Campaign Name and Client Code")
            else:
                # Save Draft
                camp = campaign_manager.create_campaign_record(campaign_name, doc_type, client_code, subject, body_template, "v1")
                st.session_state.campaign_id = camp.id
                st.session_state.campaign_data = camp
                st.session_state.wizard_step = 2
                st.rerun()
                
    elif st.session_state.wizard_step == 2:
        st.subheader("Step 2: Upload Excel Data")
        excel_file = st.file_uploader("Upload Candidates Excel", type=["xlsx"])
        
        col1, col2 = st.columns([1, 4])
        if col1.button("⬅ Back"):
            st.session_state.wizard_step = 1
            st.rerun()
            
        if excel_file:
            df = pd.read_excel(excel_file)
            st.dataframe(df.head())
            if st.button("Next: Upload Template ➡"):
                st.session_state.df = df
                st.session_state.wizard_step = 3
                st.rerun()

    elif st.session_state.wizard_step == 3:
        st.subheader("Step 3: Upload Word Template")
        docx_file = st.file_uploader("Upload .docx Template (Jinja2)", type=["docx"])
        
        col1, col2 = st.columns([1, 4])
        if col1.button("⬅ Back"):
            st.session_state.wizard_step = 2
            st.rerun()
            
        if docx_file:
            template_path = os.path.join(UPLOADS_DIR, "templates", f"{st.session_state.campaign_id}.docx")
            with open(template_path, "wb") as f:
                f.write(docx_file.getvalue())
            
            st.success("Template Uploaded.")
            if st.button("Next: Validate ➡"):
                st.session_state.template_path = template_path
                st.session_state.wizard_step = 4
                st.rerun()

    elif st.session_state.wizard_step == 4:
        st.subheader("Step 4: Validation")
        
        with st.spinner("Validating..."):
            val_result = ValidatorService.validate_excel(st.session_state.df)
            is_valid_tpl, found_vars, missing_vars = ValidatorService.validate_template_variables(st.session_state.template_path, st.session_state.df.columns)
            
            st.markdown(f"### Health Score: {val_result.health_score:.1f}%")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Valid Rows", val_result.valid_rows)
            col2.metric("Invalid Emails", val_result.invalid_emails)
            col3.metric("Duplicates", val_result.duplicates)
            col4.metric("Missing Fields", val_result.missing_fields)
            
            if not is_valid_tpl:
                st.error(f"Template variables missing from Excel: {', '.join(missing_vars)}")
                
            st.session_state.val_result = val_result
            
        col1, col2 = st.columns([1, 4])
        if col1.button("⬅ Back"):
            st.session_state.wizard_step = 3
            st.rerun()
            
        if val_result.is_valid and is_valid_tpl:
            if st.button("Next: Dry Run & Generate ➡"):
                st.session_state.wizard_step = 5
                st.rerun()

    elif st.session_state.wizard_step == 5:
        st.subheader("Step 5: Generate Documents")
        
        if st.button("▶ Start Generation (Dry Run)"):
            with st.spinner("Generating DOCX and PDF files..."):
                candidates = st.session_state.val_result.cleaned_df.to_dict('records')
                gen_result = campaign_manager.run_generation(
                    st.session_state.campaign_data, 
                    st.session_state.template_path, 
                    candidates
                )
                
                if gen_result.success:
                    st.success(f"Generated {gen_result.generated} documents in {gen_result.duration_secs:.1f}s")
                    if st.button("Next: Send Offers ➡"):
                        st.session_state.wizard_step = 6
                        st.rerun()
                else:
                    st.error("Generation failed. Check logs.")

    elif st.session_state.wizard_step == 6:
        st.subheader("Step 6: Send Offers")
        st.warning("Campaign configuration is now locked. Clicking start will begin email dispatch.")
        
        # Real-time metrics placeholder
        metrics_placeholder = st.empty()
        
        if st.button("🚀 Start Campaign"):
            st.session_state.should_stop = False
            
            def should_stop():
                return st.session_state.get('should_stop', False)
                
            campaign_manager.start_email_campaign(st.session_state.campaign_data, should_stop)
            st.success("Campaign Completed!")
            st.balloons()
