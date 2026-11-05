import os
import streamlit as st
import json
import time

# Import analyzer components directly
from analyzer import TenderAnalyzer, BiddingTemplate, CompanyProfile

# ==========================================
# 0. Helper: Docx Generation Logic
# ==========================================
def build_docx_report(result: BiddingTemplate, filepath: str):
    """Compiles the hybrid scorecard into a professional styled MS Word document."""
    try:
        import docx
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement, parse_xml
        from docx.oxml.ns import nsdecls, qn
    except ImportError:
        raise ImportError("python-docx is not installed or available.")

    doc = docx.Document()

    # Define color scheme (navy primary, dark grey body, red/orange/green alerts)
    COLOR_PRIMARY = RGBColor(12, 35, 64)   # Navy
    COLOR_SECONDARY = RGBColor(112, 128, 144) # Slate grey
    COLOR_DARK = RGBColor(51, 51, 51)
    
    # helper for styling tables
    def set_cell_background(cell, color_hex):
        shading_xml = f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>'
        cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))
        
    def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
            node = OxmlElement(f'w:{m}')
            node.set(qn('w:w'), str(val))
            node.set(qn('w:type'), 'dxa')
            tcMar.append(node)
        tcPr.append(tcMar)

    # Document Title
    title = doc.add_paragraph()
    title_run = title.add_run("L&T Defence Bidding & Compliance Report")
    title_run.font.name = 'Arial'
    title_run.font.size = Pt(22)
    title_run.font.bold = True
    title_run.font.color.rgb = COLOR_PRIMARY
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # Metadata subtitle
    sub = doc.add_paragraph()
    sub_run = sub.add_run(f"Tender Reference: {result.tender_id} | Issued by: {result.issuing_authority}")
    sub_run.font.name = 'Arial'
    sub_run.font.size = Pt(11)
    sub_run.font.color.rgb = COLOR_SECONDARY

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # Recommendation Callout Box
    rec_table = doc.add_table(rows=1, cols=1)
    rec_table.alignment = docx.enum.table.WD_TABLE_ALIGNMENT.CENTER
    cell = rec_table.rows[0].cells[0]
    set_cell_margins(cell, top=150, bottom=150, left=200, right=200)
    
    rec_color = "D4EDDA" # green background
    rec_text = f"OVERALL BID DECISION: {result.recommendation.value}"
    
    if result.recommendation.value == "NO_GO":
        rec_color = "F8D7DA" # red
    elif result.recommendation.value == "CONDITIONAL_GO":
        rec_color = "FFF3CD" # yellow
        
    set_cell_background(cell, rec_color)
    
    p = cell.paragraphs[0]
    prun = p.add_run(rec_text)
    prun.font.bold = True
    prun.font.size = Pt(14)
    prun.font.color.rgb = COLOR_PRIMARY
    
    p_rat = cell.add_paragraph()
    p_rat_run = p_rat.add_run(f"Rationale: {result.recommendation_rationale}")
    p_rat_run.font.size = Pt(10)
    p_rat_run.font.color.rgb = COLOR_DARK

    doc.add_paragraph().paragraph_format.space_after = Pt(15)

    # Section 1: Scope of Work
    h1 = doc.add_heading(level=1)
    h1_run = h1.add_run("1. Scope of Work")
    h1_run.font.color.rgb = COLOR_PRIMARY
    h1_run.font.size = Pt(14)
    
    scope_p = doc.add_paragraph(result.scope_of_work)
    scope_p.style.font.size = Pt(10.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # Section 2: Deterministic Scorecard (Stage 2 Python Checks)
    h2 = doc.add_heading(level=1)
    h2_run = h2.add_run("2. Financial & Eligibility Check (Deterministic)")
    h2_run.font.color.rgb = COLOR_PRIMARY
    h2_run.font.size = Pt(14)

    det_table = doc.add_table(rows=1, cols=4)
    det_table.style = 'Table Grid'
    hdr_cells = det_table.rows[0].cells
    headers = ["Parameter / Check", "Required spec", "L&T Value", "Status"]
    for i, name in enumerate(headers):
        hdr_cells[i].text = name
        set_cell_background(hdr_cells[i], "0C2340") # Navy header
        hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        hdr_cells[i].paragraphs[0].runs[0].font.bold = True
        hdr_cells[i].paragraphs[0].runs[0].font.size = Pt(9.5)
        set_cell_margins(hdr_cells[i], top=80, bottom=80, left=100, right=100)

    for check in result.deterministic_scorecard:
        row_cells = det_table.add_row().cells
        row_cells[0].text = check.parameter
        row_cells[1].text = check.required_value
        row_cells[2].text = check.company_value
        
        status_cell = row_cells[3]
        status_cell.text = check.status.value
        set_cell_margins(status_cell, top=80, bottom=80, left=100, right=100)
        
        # Color match status cell
        if check.status.value == "COMPLIANT":
            set_cell_background(status_cell, "D4EDDA")
        else:
            set_cell_background(status_cell, "F8D7DA")
            
        for c in row_cells:
            set_cell_margins(c, top=80, bottom=80, left=100, right=100)
            c.paragraphs[0].style.font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(15)

    # Section 3: Technical specifications scorecard (Stage 3 LLM checks)
    h3 = doc.add_heading(level=1)
    h3_run = h3.add_run("3. Technical & Engineering Scorecard")
    h3_run.font.color.rgb = COLOR_PRIMARY
    h3_run.font.size = Pt(14)

    tech_table = doc.add_table(rows=1, cols=4)
    tech_table.style = 'Table Grid'
    hdr_cells_t = tech_table.rows[0].cells
    headers_t = ["Technical Spec", "Tender Requirement", "L&T Capability / Gap", "Status"]
    for i, name in enumerate(headers_t):
        hdr_cells_t[i].text = name
        set_cell_background(hdr_cells_t[i], "708090") # Slate grey header
        hdr_cells_t[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        hdr_cells_t[i].paragraphs[0].runs[0].font.bold = True
        hdr_cells_t[i].paragraphs[0].runs[0].font.size = Pt(9.5)
        set_cell_margins(hdr_cells_t[i], top=80, bottom=80, left=100, right=100)

    for check in result.technical_scorecard:
        row_cells = tech_table.add_row().cells
        row_cells[0].text = f"{check.parameter}\n({check.citation})"
        row_cells[1].text = check.tender_requirement
        
        company_text = check.lt_capability
        if check.gap_analysis:
            company_text += f"\nGap: {check.gap_analysis}"
        if check.mitigation_action:
            company_text += f"\nMitigation: {check.mitigation_action}"
        row_cells[2].text = company_text
        
        status_cell = row_cells[3]
        status_cell.text = check.status.value
        
        # Color match status cell
        if check.status.value == "COMPLIANT":
            set_cell_background(status_cell, "D4EDDA")
        elif check.status.value == "RISKY" or check.status.value == "PARTIALLY_COMPLIANT":
            set_cell_background(status_cell, "FFF3CD")
        else:
            set_cell_background(status_cell, "F8D7DA")
            
        for c in row_cells:
            set_cell_margins(c, top=80, bottom=80, left=100, right=100)
            c.paragraphs[0].style.font.size = Pt(8.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(20)

    # Footer note
    fp = doc.sections[0].footer.paragraphs[0]
    fp.text = "Confidential - Larsen & Toubro Defence Internal Use Only"
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    fp.style.font.size = Pt(8.5)
    fp.style.font.color.rgb = COLOR_SECONDARY

    doc.save(filepath)

# ==========================================
# 1. Global Setup & Design Styling
# ==========================================
st.set_page_config(
    page_title="L&T Defence - Tender Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling injection
st.markdown("""
<style>
    .main { background-color: #f7f9fc; }
    h1, h2, h3 { color: #0c2340 !important; font-family: 'Helvetica Neue', Arial, sans-serif; }
    
    .rec-card-go {
        background-color: #d4edda; border-left: 6px solid #28a745; color: #155724;
        padding: 20px; border-radius: 6px; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .rec-card-nogo {
        background-color: #f8d7da; border-left: 6px solid #dc3545; color: #721c24;
        padding: 20px; border-radius: 6px; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .rec-card-cond {
        background-color: #fff3cd; border-left: 6px solid #ffc107; color: #856404;
        padding: 20px; border-radius: 6px; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    .styled-table {
        width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 14px; text-align: left;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02); border-radius: 8px; overflow: hidden;
    }
    .styled-table thead tr { background-color: #0c2340; color: #ffffff; font-weight: bold; }
    .styled-table th, .styled-table td { padding: 12px 15px; border-bottom: 1px solid #dddddd; }
    .styled-table tbody tr:nth-of-type(even) { background-color: #f3f4f6; }
    
    .badge-compliant {
        background-color: #d4edda; color: #155724; padding: 4px 10px; border-radius: 12px;
        font-weight: bold; font-size: 11px; border: 1px solid #c3e6cb;
    }
    .badge-noncompliant {
        background-color: #f8d7da; color: #721c24; padding: 4px 10px; border-radius: 12px;
        font-weight: bold; font-size: 11px; border: 1px solid #f5c6cb;
    }
    .badge-risky {
        background-color: #fff3cd; color: #856404; padding: 4px 10px; border-radius: 12px;
        font-weight: bold; font-size: 11px; border: 1px solid #ffeeba;
    }
</style>
""", unsafe_allow_html=True)

# Local database file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_PATH = os.path.join(BASE_DIR, "company_profile.json")

# Robust fallback path discovery if launched from another working directory
if not os.path.exists(PROFILE_PATH):
    for candidate in [
        os.path.join(os.getcwd(), "Music", "RAG_project", "company_profile.json"),
        os.path.join(os.getcwd(), "company_profile.json"),
    ]:
        if os.path.exists(candidate):
            PROFILE_PATH = candidate
            break

# ==========================================
# Sidebar Settings
# ==========================================
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Try discovering pre-configured key from env or st.secrets
    default_key = os.getenv("GEMINI_API_KEY", "")
    if not default_key:
        try:
            if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
                default_key = st.secrets["GEMINI_API_KEY"]
        except Exception:
            default_key = ""
            
    api_key_input = st.text_input(
        "🔑 Gemini API Key",
        value=default_key,
        type="password",
        help="Enter your Google Gemini API key from https://aistudio.google.com/. If configured in Streamlit Secrets or .env, it loads automatically."
    )
    if not api_key_input:
        st.warning("⚠️ Enter a Gemini API Key to enable tender analysis.")
    else:
        st.success("✅ API Key loaded.")

st.title("🛡️ Bidding Compliance Portal (Serverless)")
st.caption("3-Stage Hybrid Decision Engine for Tender Verification")

tab_dashboard, tab_profile = st.tabs(["📊 Tender Analysis Dashboard", "⚙️ L&T Company Profile"])

# ==========================================
# TAB 1: TENDER ANALYSIS DASHBOARD
# ==========================================
with tab_dashboard:
    st.header("Analyze New Defence Tender")
    st.write("Upload a PDF document to run the extraction, rules validation, and feasibility evaluation pipeline.")

    uploaded_file = st.file_uploader("Upload Tender PDF", type=["pdf", "md"])

    if uploaded_file is not None:
        if st.button("🚀 Execute Hybrid Compliance Analysis", type="primary"):
            status_box = st.empty()
            progress_bar = st.progress(0)
            
            try:
                # 1. Save uploaded file to temp file
                temp_filename = f"temp_{int(time.time())}_{uploaded_file.name}"
                with open(temp_filename, "wb") as f:
                    f.write(uploaded_file.getvalue())
                
                # 2. Run Stages
                status_box.markdown("**Pipeline State:** `Stage 1: Extracting raw specifications...`")
                progress_bar.progress(25)
                
                # Set environment variable so TenderAnalyzer can pick it up under any circumstance
                if api_key_input:
                    os.environ["GEMINI_API_KEY"] = api_key_input
                
                try:
                    analyzer = TenderAnalyzer(api_key=api_key_input or None)
                except TypeError:
                    # In case an older cached module version of analyzer is in memory
                    analyzer = TenderAnalyzer()
                
                # Upload to Gemini File API
                file_ref = analyzer.client.files.upload(file=temp_filename)
                
                # Stage 1: Extraction
                requirements = analyzer.extract_requirements(file_ref)
                
                status_box.markdown("**Pipeline State:** `Stage 2: Running deterministic comparison rules...`")
                progress_bar.progress(60)
                
                # Load profile
                with open(PROFILE_PATH, "r") as pf:
                    profile_data = json.load(pf)
                profile = CompanyProfile.model_validate(profile_data)
                
                # Stage 2: Checks
                det_report = analyzer.run_deterministic_checks(requirements, profile)
                
                status_box.markdown("**Pipeline State:** `Stage 3: Running heuristic engineering evaluations...`")
                progress_bar.progress(85)
                
                # Stage 3: Synthesis
                result = analyzer.generate_bidding_template(file_ref, requirements, det_report, profile)
                
                # Clean up cloud file
                analyzer.client.files.delete(name=file_ref.name)
                # Clean up local temp file
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                
                progress_bar.progress(100)
                status_box.success("🎉 Pipeline Completed successfully!")
                
                # Save session state
                st.session_state["standalone_result"] = result.model_dump()
                st.rerun()
                
            except Exception as e:
                status_box.error(f"❌ Analysis failed: {e}")
                if 'temp_filename' in locals() and os.path.exists(temp_filename):
                    os.remove(temp_filename)

    # Render results
    if "standalone_result" in st.session_state:
        res = st.session_state["standalone_result"]
        
        st.markdown("---")
        st.subheader(f"📄 Tender Compliance Scorecard: {res['tender_id']}")
        
        rec = res["recommendation"]
        rationale = res["recommendation_rationale"]
        
        if rec == "GO":
            st.markdown(f'<div class="rec-card-go"><h3>🟢 OVERALL BID RECOMMENDATION: GO</h3><p>{rationale}</p></div>', unsafe_allow_html=True)
        elif rec == "NO_GO":
            st.markdown(f'<div class="rec-card-nogo"><h3>🔴 OVERALL BID RECOMMENDATION: NO_GO</h3><p>{rationale}</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="rec-card-cond"><h3>🟡 OVERALL BID RECOMMENDATION: CONDITIONAL_GO</h3><p>{rationale}</p></div>', unsafe_allow_html=True)
            
        with st.expander("📝 View Scope of Work"):
            st.write(res["scope_of_work"])
            st.caption(f"Authority: {res['issuing_authority']} | Deadline: {res['submission_deadline']}")

        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Stage 1: Deterministic Compliance Check (Python)")
            html_det = """
            <table class="styled-table">
                <thead><tr><th>Parameter</th><th>Required Spec</th><th>L&T Value</th><th>Status</th></tr></thead>
                <tbody>
            """
            for check in res["deterministic_scorecard"]:
                status_badge = f'<span class="badge-compliant">{check["status"]}</span>' if check["status"] == "COMPLIANT" else f'<span class="badge-noncompliant">{check["status"]}</span>'
                html_det += f"""
                <tr>
                    <td><strong>{check['parameter']}</strong><br><small style="color: grey;">Citation: {check['citation']}</small></td>
                    <td>{check['required_value']}</td>
                    <td>{check['company_value']}</td>
                    <td>{status_badge}</td>
                </tr>
                """
            html_det += "</tbody></table>"
            st.markdown(html_det, unsafe_allow_html=True)
            
        with col2:
            st.subheader("Stage 2: Technical Feasibility Scorecard (Gemini)")
            html_tech = """
            <table class="styled-table">
                <thead><tr><th>Specification</th><th>Tender Requirement</th><th>L&T Match & Gap</th><th>Status</th></tr></thead>
                <tbody>
            """
            for item in res["technical_scorecard"]:
                status_val = item["status"]
                badge_class = "badge-compliant" if status_val == "COMPLIANT" else ("badge-noncompliant" if status_val == "NON_COMPLIANT" else "badge-risky")
                status_badge = f'<span class="{badge_class}">{status_val}</span>'
                
                gap_text = item["gap_analysis"]
                if item["mitigation_action"]:
                    gap_text += f'<br><strong>Mitigation:</strong> {item["mitigation_action"]}'
                
                html_tech += f"""
                <tr>
                    <td><strong>{item['parameter']}</strong><br><small style="color: grey;">Citation: {item['citation']}</small></td>
                    <td>{item['tender_requirement']}</td>
                    <td>{item['lt_capability']}<br><small style="color: #4b5563;">{gap_text}</small></td>
                    <td>{status_badge}</td>
                </tr>
                """
            html_tech += "</tbody></table>"
            st.markdown(html_tech, unsafe_allow_html=True)
            
        st.markdown("---")
        st.subheader("📥 Export Final Bid Documents")
        exp_col1, exp_col2 = st.columns(2)
        
        with exp_col1:
            try:
                # Generate Word Doc locally in memory
                from analyzer import BiddingTemplate
                result_obj = BiddingTemplate.model_validate(res)
                temp_docx_path = f"temp_report_{res['tender_id']}.docx"
                build_docx_report(result_obj, temp_docx_path)
                
                with open(temp_docx_path, "rb") as f:
                    doc_bytes = f.read()
                
                st.download_button(
                    label="📄 Download Formatted Word Report (.docx)",
                    data=doc_bytes,
                    file_name=f"L&T_Bidding_Report_{res['tender_id']}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
                # Cleanup local temp docx
                if os.path.exists(temp_docx_path):
                    os.remove(temp_docx_path)
            except Exception as e:
                st.error(f"Failed to compile Word report: {e}")
                
        with exp_col2:
            st.download_button(
                label="⚙️ Download Raw JSON Data (.json)",
                data=json.dumps(res, indent=2),
                file_name=f"L&T_Bidding_Template_{res['tender_id']}.json",
                mime="application/json",
                use_container_width=True
            )

# ==========================================
# TAB 2: L&T COMPANY PROFILE MANAGER
# ==========================================
with tab_profile:
    st.header("L&T Capabilities Profile Database")
    st.write("Edit L&T's corporate metrics, certifications, and testing capabilities.")
    
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, "r") as f:
            profile = json.load(f)
            
        with st.form("profile_form"):
            company_name = st.text_input("Company Name", value=profile["company_name"])
            
            col_fin1, col_fin2 = st.columns(2)
            with col_fin1:
                turnover = st.number_input("Annual Turnover (USD)", value=profile["financials"]["annual_turnover_usd"], format="%f")
            with col_fin2:
                emd_cap = st.number_input("Max EMD Guarantee Limit (USD)", value=profile["financials"]["max_emd_guarantee_usd"], format="%f")
                
            col_cap1, col_cap2 = st.columns(2)
            with col_cap1:
                lead_time = st.number_input("Standard Lead Time (months)", value=profile["capabilities"]["standard_lead_time_months"])
                exp_yrs = st.number_input("Defence Experience (years)", value=profile["capabilities"]["defense_experience_years"])
            with col_cap2:
                security_lvl = st.selectbox("Security Clearance Level", ["None", "Secret", "Top Secret"], index=["none", "secret", "top secret"].index(profile["capabilities"]["security_clearance_level"].lower()))
                past_projects = st.number_input("Similar Projects Completed (last 5 years)", value=profile["capabilities"]["past_projects_5yr"])
            
            facilities = st.text_area("In-House Testing Facilities (one per line)", value="\n".join(profile["capabilities"]["testing_facilities"]))
            
            st.subheader("🎖️ Active Certifications")
            certs_list = []
            for i, cert in enumerate(profile["certifications"]):
                c_col1, c_col2, c_col3 = st.columns([3, 2, 2])
                with c_col1:
                    c_name = st.text_input(f"Cert #{i+1} Name", value=cert["name"], key=f"cert_name_{i}")
                with c_col2:
                    c_expiry = st.text_input(f"Cert #{i+1} Expiry (YYYY-MM-DD)", value=cert["expiry_date"], key=f"cert_expiry_{i}")
                with c_col3:
                    c_status = st.selectbox(f"Cert #{i+1} Status", ["ACTIVE", "EXPIRED"], index=["active", "expired"].index(cert["status"].lower()), key=f"cert_status_{i}")
                
                if c_name:
                    certs_list.append({
                        "name": c_name,
                        "expiry_date": c_expiry,
                        "status": c_status
                    })
            
            save_btn = st.form_submit_button("💾 Save Profile Changes", type="primary")
            if save_btn:
                updated_profile = {
                    "company_name": company_name,
                    "financials": {
                        "annual_turnover_usd": turnover,
                        "max_emd_guarantee_usd": emd_cap
                    },
                    "certifications": certs_list,
                    "capabilities": {
                        "standard_lead_time_months": int(lead_time),
                        "security_clearance_level": security_lvl,
                        "defense_experience_years": int(exp_yrs),
                        "past_projects_5yr": int(past_projects),
                        "testing_facilities": [f.strip() for f in facilities.split("\n") if f.strip()]
                    }
                }
                with open(PROFILE_PATH, "w") as pf:
                    json.dump(updated_profile, pf, indent=2)
                st.success("🎉 Company profile updated successfully!")
    else:
        st.error("Profile configuration file `company_profile.json` not found.")
