import streamlit as st
import requests
import json
import time

# ==========================================
# 0. Global Setup & Design Styling
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
    /* Main Layout Aesthetics */
    .main {
        background-color: #f7f9fc;
    }
    h1, h2, h3 {
        color: #0c2340 !important;
        font-family: 'Helvetica Neue', Arial, sans-serif;
    }
    
    /* Premium Recommendation Card Banners */
    .rec-card-go {
        background-color: #d4edda;
        border-left: 6px solid #28a745;
        color: #155724;
        padding: 20px;
        border-radius: 6px;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .rec-card-nogo {
        background-color: #f8d7da;
        border-left: 6px solid #dc3545;
        color: #721c24;
        padding: 20px;
        border-radius: 6px;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .rec-card-cond {
        background-color: #fff3cd;
        border-left: 6px solid #ffc107;
        color: #856404;
        padding: 20px;
        border-radius: 6px;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* Table styling */
    .styled-table {
        width: 100%;
        border-collapse: collapse;
        margin: 15px 0;
        font-size: 14px;
        text-align: left;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        border-radius: 8px;
        overflow: hidden;
    }
    .styled-table thead tr {
        background-color: #0c2340;
        color: #ffffff;
        font-weight: bold;
    }
    .styled-table th, .styled-table td {
        padding: 12px 15px;
        border-bottom: 1px solid #dddddd;
    }
    .styled-table tbody tr:nth-of-type(even) {
        background-color: #f3f4f6;
    }
    
    /* Badge styling */
    .badge-compliant {
        background-color: #d4edda;
        color: #155724;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 11px;
        border: 1px solid #c3e6cb;
    }
    .badge-noncompliant {
        background-color: #f8d7da;
        color: #721c24;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 11px;
        border: 1px solid #f5c6cb;
    }
    .badge-risky {
        background-color: #fff3cd;
        color: #856404;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 11px;
        border: 1px solid #ffeeba;
    }
</style>
""", unsafe_allow_html=True)

BACKEND_URL = "http://127.0.0.1:8000"

# Title banner
st.title("🛡️ L&T Defence: Bidding Compliance Portal")
st.caption("3-Stage Hybrid Decision Engine for Defense Tender Verification")

# Main tabs navigation
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
            with st.spinner("Initiating analysis, saving file to backend server..."):
                try:
                    # POST upload file to backend API
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/octet-stream")}
                    response = requests.post(f"{BACKEND_URL}/analyze", files=files)
                    
                    if response.status_code == 200:
                        task_id = response.json()["task_id"]
                        st.info(f"Analysis started successfully. Job ID: {task_id}")
                        
                        # Polling loop
                        status_box = st.empty()
                        progress_bar = st.progress(0)
                        
                        completed = False
                        attempts = 0
                        
                        while not completed and attempts < 120:
                            status_resp = requests.get(f"{BACKEND_URL}/status/{task_id}")
                            if status_resp.status_code == 200:
                                status_data = status_resp.json()
                                status = status_data["status"]
                                error = status_data["error"]
                                
                                status_box.markdown(f"**Current Pipeline State:** `{status}`")
                                
                                if status == "Completed":
                                    completed = True
                                    progress_bar.progress(100)
                                    status_box.success("🎉 Pipeline Completed! Drawing Scorecard...")
                                elif status == "Failed":
                                    completed = True
                                    status_box.error(f"❌ Analysis failed: {error}")
                                    st.stop()
                                else:
                                    # Update progress increments based on string clues
                                    if "Extracting" in status:
                                        progress_bar.progress(25)
                                    elif "Rules" in status or "Deterministic" in status:
                                        progress_bar.progress(60)
                                    else:
                                        progress_bar.progress(85)
                                        
                            time.sleep(2)
                            attempts += 1
                        
                        if completed and status == "Completed":
                            # Get final results
                            result_resp = requests.get(f"{BACKEND_URL}/results/{task_id}")
                            if result_resp.status_code == 200:
                                result = result_resp.json()
                                st.session_state["analysis_result"] = result
                                st.session_state["task_id"] = task_id
                                
                    else:
                        st.error(f"Failed to submit file to backend: {response.text}")
                except Exception as e:
                    st.error(f"Error connecting to backend server: {e}")

    # Render results if present in session state
    if "analysis_result" in st.session_state:
        res = st.session_state["analysis_result"]
        task_id = st.session_state["task_id"]
        
        st.markdown("---")
        st.subheader(f"📄 Tender compliance Scorecard: {res['tender_id']}")
        
        # Display Bid Decision Card Banner
        rec = res["recommendation"]
        rationale = res["recommendation_rationale"]
        
        if rec == "GO":
            st.markdown(f"""
            <div class="rec-card-go">
                <h3>🟢 OVERALL BID RECOMMENDATION: GO</h3>
                <p><strong>Rationale:</strong> {rationale}</p>
            </div>
            """, unsafe_allow_html=True)
        elif rec == "NO_GO":
            st.markdown(f"""
            <div class="rec-card-nogo">
                <h3>🔴 OVERALL BID RECOMMENDATION: NO_GO</h3>
                <p><strong>Rationale:</strong> {rationale}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="rec-card-cond">
                <h3>🟡 OVERALL BID RECOMMENDATION: CONDITIONAL_GO</h3>
                <p><strong>Rationale:</strong> {rationale}</p>
            </div>
            """, unsafe_allow_html=True)
            
        # Scope info
        with st.expander("📝 View Scope of Work"):
            st.write(res["scope_of_work"])
            st.caption(f"Issuing Authority: {res['issuing_authority']} | Submission Deadline: {res['submission_deadline']}")

        # Display scorecard tables
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Stage 1: Deterministic Compliance Check (Python)")
            st.write("Pure database rules run in Python comparing numbers and dates against L&T profiles.")
            
            html_det = """
            <table class="styled-table">
                <thead>
                    <tr>
                        <th>Parameter</th>
                        <th>Required Spec</th>
                        <th>L&T Value</th>
                        <th>Status</th>
                    </tr>
                </thead>
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
            st.write("Multimodal AI reasoning checking testing criteria, facilities, and timelines.")
            
            html_tech = """
            <table class="styled-table">
                <thead>
                    <tr>
                        <th>Specification</th>
                        <th>Tender Requirement</th>
                        <th>L&T Match & Gap Analysis</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
            """
            for item in res["technical_scorecard"]:
                status_val = item["status"]
                badge_class = "badge-compliant"
                if status_val == "NON_COMPLIANT":
                    badge_class = "badge-noncompliant"
                elif status_val in ["RISKY", "PARTIALLY_COMPLIANT"]:
                    badge_class = "badge-risky"
                    
                status_badge = f'<span class="{badge_class}">{status_val}</span>'
                
                gap_text = item["gap_analysis"]
                if item["mitigation_action"]:
                    gap_text += f'<br><strong style="color: #0c2340;">Mitigation:</strong> {item["mitigation_action"]}'
                
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
            
        # Downloads Exports Section
        st.markdown("---")
        st.subheader("📥 Export Final Bid Documents")
        st.write("Download the compliance checklist to distribute to the legal, engineering, and bidding departments.")
        
        exp_col1, exp_col2 = st.columns(2)
        
        with exp_col1:
            # Word Doc download button
            try:
                doc_url = f"{BACKEND_URL}/export/{task_id}"
                doc_data = requests.get(doc_url).content
                st.download_button(
                    label="📄 Download Formatted Word Report (.docx)",
                    data=doc_data,
                    file_name=f"L&T_Bidding_Report_{res['tender_id']}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
            except Exception as e:
                st.error("Failed to generate Word document for download.")
                
        with exp_col2:
            # Raw JSON download button
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
    st.write("Edit L&T's corporate metrics, certifications, and testing capabilities. The deterministic engine queries these numbers in real time.")
    
    # Load profile details from backend
    try:
        profile_resp = requests.get(f"{BACKEND_URL}/profile")
        if profile_resp.status_code == 200:
            profile = profile_resp.json()
            
            with st.form("profile_form"):
                st.subheader("🏢 General Details")
                company_name = st.text_input("Company Name", value=profile["company_name"])
                
                col_fin1, col_fin2 = st.columns(2)
                with col_fin1:
                    st.subheader("💰 Financial Capacity")
                    turnover = st.number_input("Annual Turnover (USD)", value=profile["financials"]["annual_turnover_usd"], format="%f")
                with col_fin2:
                    st.subheader("📜 Guarantees & Bid Limits")
                    emd_cap = st.number_input("Max EMD Guarantee Limit (USD)", value=profile["financials"]["max_emd_guarantee_usd"], format="%f")
                    
                st.subheader("🛠️ Engineering & Production Capabilities")
                col_cap1, col_cap2 = st.columns(2)
                with col_cap1:
                    lead_time = st.number_input("Standard Lead Time (months)", value=profile["capabilities"]["standard_lead_time_months"])
                    exp_yrs = st.number_input("Defence Experience (years)", value=profile["capabilities"]["defense_experience_years"])
                with col_cap2:
                    security_lvl = st.selectbox("Security Clearance Level", ["None", "Secret", "Top Secret"], index=["none", "secret", "top secret"].index(profile["capabilities"]["security_clearance_level"].lower()))
                    past_projects = st.number_input("Similar Projects Completed (last 5 years)", value=profile["capabilities"]["past_projects_5yr"])
                
                facilities = st.text_area("In-House Testing Facilities (one per line)", value="\n".join(profile["capabilities"]["testing_facilities"]))
                
                st.subheader("🎖️ Active Certifications")
                st.write("Manage active quality ISO/AS credentials. These are matched directly against bidder eligibility clauses.")
                
                # Render certifications table inputs
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
                
                st.markdown("---")
                save_btn = st.form_submit_button("💾 Save Profile Database Changes", type="primary")
                
                if save_btn:
                    # Assemble updated JSON
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
                    
                    # POST update back to API
                    save_resp = requests.post(f"{BACKEND_URL}/profile", json=updated_profile)
                    if save_resp.status_code == 200:
                        st.success("🎉 Company profile database updated successfully! Future analysis runs will use this new criteria.")
                    else:
                        st.error(f"Failed to update profile: {save_resp.text}")
                        
        else:
            st.error("Could not fetch company profile details from backend server.")
    except Exception as e:
        st.error(f"Failed to connect to backend: {e}")
