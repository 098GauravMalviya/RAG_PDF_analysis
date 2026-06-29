import os
import sys
import json
import re
import argparse
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import time
import random

# Load environment variables
load_dotenv()

# We will dynamically import genai so that the file is syntactically valid even if requirements aren't installed yet.
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

def retry_with_backoff(max_retries=5, base_delay=2, max_delay=60):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    is_retryable = (
                        "503" in str(e) or
                        "UNAVAILABLE" in str(e) or
                        "overloaded" in str(e).lower() or
                        "429" in str(e)  # rate limit, worth retrying too
                    )
                    if not is_retryable or attempt == max_retries - 1:
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = random.uniform(0, delay * 0.3)
                    wait_time = delay + jitter
                    print(f"[!] API overloaded (attempt {attempt+1}/{max_retries}). Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    last_exception = e
            raise last_exception
        return wrapper
    return decorator

# ==========================================
# 1. Structured Data Models (Pydantic)
# ==========================================

class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    RISKY = "RISKY"

class BidRecommendation(str, Enum):
    GO = "GO"
    NO_GO = "NO_GO"
    CONDITIONAL_GO = "CONDITIONAL_GO"

# --- Stage 1 Models ---
class TechnicalSpecification(BaseModel):
    parameter: str = Field(description="The name of the technical parameter, e.g., 'Operating Temperature Range', 'Output Power'.")
    requirement: str = Field(description="The exact requirement details specified in the tender.")
    citation: str = Field(description="Exact page number and section clause where this specification is located.")

class FinancialConstraint(BaseModel):
    parameter: str = Field(description="The financial item name, e.g., 'EMD', 'Performance Security', 'Estimated Bid Value', 'Turnover'.")
    value: str = Field(description="The financial value or percentage required.")
    citation: str = Field(description="Exact page number and section clause where this constraint is located.")

class EligibilityCriterion(BaseModel):
    requirement: str = Field(description="The eligibility requirement as stated in the tender.")
    citation: str = Field(description="Exact page number and section clause where this requirement is located.")

class TenderRequirements(BaseModel):
    tender_id: str = Field(description="The unique Tender Identification Number / Reference Number.")
    issuing_authority: str = Field(description="The government department or authority issuing the tender.")
    scope_of_work: str = Field(description="Brief description of the scope of work and requirements.")
    submission_deadline: str = Field(description="Deadline date and time for bid submission.")
    
    technical_specifications: List[TechnicalSpecification] = Field(
        description="Key technical specifications and testing standards extracted from the document."
    )
    financial_constraints: List[FinancialConstraint] = Field(
        description="Financial requirements, bank guarantees, and bid values."
    )
    eligibility_criteria: List[EligibilityCriterion] = Field(
        description="Summary of experience, licensing, and certification requirements."
    )

# --- Company Profile Models (Mock Database Schema) ---
class Certification(BaseModel):
    name: str
    expiry_date: str
    status: str

class CompanyFinancials(BaseModel):
    annual_turnover_usd: float
    max_emd_guarantee_usd: float

class CompanyCapabilities(BaseModel):
    standard_lead_time_months: int
    security_clearance_level: str
    defense_experience_years: int
    past_projects_5yr: int
    testing_facilities: List[str]

class CompanyProfile(BaseModel):
    company_name: str
    financials: CompanyFinancials
    certifications: List[Certification]
    capabilities: CompanyCapabilities

# --- Stage 2 Models ---
class DeterministicCheck(BaseModel):
    parameter: str = Field(description="The parameter checked, e.g. 'Turnover', 'EMD', 'AS9100 Certification'.")
    required_value: str = Field(description="The requirement value from the tender.")
    company_value: str = Field(description="L&T's value from the company profile.")
    status: ComplianceStatus = Field(description="COMPLIANT or NON_COMPLIANT.")
    gap_analysis: str = Field(description="Summary of the matching check results.")
    citation: str = Field(description="Reference citation from the tender document.")

class DeterministicReport(BaseModel):
    checks: List[DeterministicCheck]
    all_compliant: bool

# --- Stage 3 Models ---
class FeasibilityItem(BaseModel):
    parameter: str = Field(description="The criterion analyzed, e.g. 'Military Testing Standard compliance', 'Delivery Timeline'.")
    tender_requirement: str = Field(description="The requirement as stated in the tender document.")
    lt_capability: str = Field(description="Mapping of L&T's capability or matching stats against this requirement.")
    status: ComplianceStatus = Field(description="The compliance status of L&T against this requirement.")
    gap_analysis: str = Field(description="Detailed analysis of the gap or alignment between the requirement and L&T's capability.")
    mitigation_action: Optional[str] = Field(description="Actionable suggestion to mitigate risks or address the gap (if applicable).")
    citation: str = Field(description="Exact page number and section clause where this constraint is located.")

class BiddingTemplate(BaseModel):
    tender_id: str = Field(description="The unique Tender Identification Number / Reference Number.")
    issuing_authority: str = Field(description="The government department or authority issuing the tender.")
    scope_of_work: str = Field(description="A brief description of the scope of work and requirements.")
    submission_deadline: str = Field(description="The deadline date and time for bid submission.")
    
    technical_specifications: List[TechnicalSpecification] = Field(description="Key technical specifications and testing standards extracted from the document.")
    financial_constraints: List[FinancialConstraint] = Field(description="Financial requirements, bank guarantees, and bid values.")
    eligibility_criteria: List[str] = Field(description="Summary of experience, licensing, and certification requirements.")
    
    deterministic_scorecard: List[DeterministicCheck] = Field(description="Exact math-based checks calculated deterministically in Python.")
    technical_scorecard: List[FeasibilityItem] = Field(description="Qualitative engineering/feasibility scorecard evaluated by the LLM.")
    
    recommendation: BidRecommendation = Field(description="Overall bid recommendation (GO / NO_GO / CONDITIONAL_GO).")
    recommendation_rationale: str = Field(description="Comprehensive technical and financial explanation behind the recommendation.")

# ==========================================
# 2. Rules Engine Utilities
# ==========================================

def parse_monetary_value(val_str: str) -> float:
    """Parses numeric monetary values from strings (handles $1.5 Million, $500M, Crores, Lakhs etc.)"""
    # Remove dollar signs, commas, and extra spaces
    clean_str = val_str.lower().replace(",", "").replace("$", "").replace("usd", "").strip()
    
    # Try to extract numbers
    match = re.search(r"(\d+(\.\d+)?)", clean_str)
    if not match:
        return 0.0
    
    num = float(match.group(1))
    
    # Apply scales
    if "million" in clean_str or "m" in clean_str.split():
        num *= 1_000_000
    elif "billion" in clean_str or "b" in clean_str.split():
        num *= 1_000_000_000
    elif "crore" in clean_str or "cr" in clean_str:
        num *= 10_000_000 / 83.0  # Convert 1 Crore INR to USD (roughly divided by 83)
    elif "lakh" in clean_str:
        num *= 100_000 / 83.0      # Convert Lakh INR to USD
        
    return num

# ==========================================
# 3. Analyzer Logic
# ==========================================

class TenderAnalyzer:
    def __init__(self):
        if genai is None or types is None:
            raise RuntimeError(
                "Google GenAI SDK is not installed. Please run: pip install -r requirements.txt"
            )
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is not set. Please set it in your .env file."
            )
        
        # Initialize Google GenAI client
        self.client = genai.Client(api_key=api_key)

    @retry_with_backoff(max_retries=5, base_delay=2, max_delay=60)
    def _call_gemini(self, contents, schema, model_name):
        return self.client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.1,
            )
        )

    def extract_requirements(self, file_ref) -> TenderRequirements:
        """
        Stage 1: Pure extraction. Pulls raw parameters out of the PDF tender.
        """
        prompt = """
You are a meticulous document analyst. Your ONLY job is extraction — do not
evaluate, judge, or compare anything against any company's capabilities.

Read the attached defense tender document and extract:
1. Tender ID, issuing authority, scope of work, submission deadline.
2. Every technical specification and testing/military standard mentioned (e.g., MIL-STD, IS, DEF-STAN), each with an exact page + clause citation.
3. Every financial constraint (EMD, PBG, ceiling budget, etc.), each with an exact page + clause citation.
4. Every eligibility criterion (turnover, past performance, certifications, security clearance, etc.).

Cross-reference scattered clauses where relevant (e.g., a spec on one page that is qualified by a standard defined elsewhere) so nothing is missed.
Do not add commentary, opinions, or feasibility assessments — extraction only.
"""
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        response = self._call_gemini(
            contents=[file_ref, prompt],
            schema=TenderRequirements,
            model_name=model_name,
        )
        return TenderRequirements.model_validate_json(response.text)

    def run_deterministic_checks(self, requirements: TenderRequirements, profile: CompanyProfile) -> DeterministicReport:
        """
        Stage 2: Deterministic Python Engine. Runs strict comparisons.
        """
        checks = []
        all_compliant = True

        # 1. Turnover Check
        required_turnover = 0.0
        turnover_citation = "Clause 4.1"
        for crit in requirements.eligibility_criteria:
            if "turnover" in crit.requirement.lower():
                required_turnover = parse_monetary_value(crit.requirement)
                turnover_citation = crit.citation
                break

        company_turnover = profile.financials.annual_turnover_usd
        if required_turnover > 0:
            turnover_ok = company_turnover >= required_turnover
            status = ComplianceStatus.COMPLIANT if turnover_ok else ComplianceStatus.NON_COMPLIANT
            gap_analysis = f"Required turnover: ${required_turnover/1e6:.1f}M. L&T turnover: ${company_turnover/1e6:.1f}M."
            if not turnover_ok:
                all_compliant = False
            checks.append(DeterministicCheck(
                parameter="Annual Turnover",
                required_value=f"Min ${required_turnover/1e6:.1f}M",
                company_value=f"${company_turnover/1e6:.1f}M",
                status=status,
                gap_analysis=gap_analysis,
                citation=turnover_citation
            ))

        # 2. EMD Check
        required_emd = 0.0
        emd_citation = "Clause 3.1"
        for fc in requirements.financial_constraints:
            if "emd" in fc.parameter.lower() or "earnest money" in fc.parameter.lower():
                required_emd = parse_monetary_value(fc.value)
                emd_citation = fc.citation
                break

        company_max_emd = profile.financials.max_emd_guarantee_usd
        if required_emd > 0:
            emd_ok = company_max_emd >= required_emd
            status = ComplianceStatus.COMPLIANT if emd_ok else ComplianceStatus.NON_COMPLIANT
            gap_analysis = f"Required EMD: ${required_emd/1e6:.1f}M. L&T EMD Capacity: ${company_max_emd/1e6:.1f}M."
            if not emd_ok:
                all_compliant = False
            checks.append(DeterministicCheck(
                parameter="Earnest Money Deposit (EMD)",
                required_value=f"Max ${required_emd/1e6:.1f}M",
                company_value=f"Capacity up to ${company_max_emd/1e6:.1f}M",
                status=status,
                gap_analysis=gap_analysis,
                citation=emd_citation
            ))

        # 3. Certifications Check
        # Check if the tender requests any of AS9100, ISO 9001, ISO 14001, etc.
        cert_names = [c.name.lower() for c in profile.certifications]
        for crit in requirements.eligibility_criteria:
            req_text = crit.requirement.lower()
            for company_cert in profile.certifications:
                cert_key = company_cert.name.lower()
                if cert_key in req_text:
                    # Check if L&T's certification is active
                    status = ComplianceStatus.COMPLIANT if company_cert.status.upper() == "ACTIVE" else ComplianceStatus.NON_COMPLIANT
                    gap_analysis = f"L&T holds active {company_cert.name} certification (valid until {company_cert.expiry_date})."
                    if company_cert.status.upper() != "ACTIVE":
                        all_compliant = False
                        gap_analysis = f"L&T's {company_cert.name} certification is expired or inactive."
                    
                    checks.append(DeterministicCheck(
                        parameter=f"{company_cert.name} Certification",
                        required_value=f"Valid {company_cert.name}",
                        company_value=f"{company_cert.status} (Expiry: {company_cert.expiry_date})",
                        status=status,
                        gap_analysis=gap_analysis,
                        citation=crit.citation
                    ))

        # 4. Security Clearance Check
        required_clearance = "none"
        clearance_citation = "Clause 4.3"
        for crit in requirements.eligibility_criteria:
            if "clearance" in crit.requirement.lower() or "security clearance" in crit.requirement.lower():
                if "secret" in crit.requirement.lower():
                    required_clearance = "Secret"
                elif "top secret" in crit.requirement.lower():
                    required_clearance = "Top Secret"
                clearance_citation = crit.citation
                break

        company_clearance = profile.capabilities.security_clearance_level
        if required_clearance != "none":
            clearance_levels = {"none": 0, "secret": 1, "top secret": 2}
            clearance_ok = clearance_levels.get(company_clearance.lower(), 0) >= clearance_levels.get(required_clearance.lower(), 0)
            status = ComplianceStatus.COMPLIANT if clearance_ok else ComplianceStatus.NON_COMPLIANT
            gap_analysis = f"Required clearance: {required_clearance}. L&T clearance: {company_clearance}."
            if not clearance_ok:
                all_compliant = False
            checks.append(DeterministicCheck(
                parameter="Security Clearance",
                required_value=required_clearance,
                company_value=company_clearance,
                status=status,
                gap_analysis=gap_analysis,
                citation=clearance_citation
            ))

        return DeterministicReport(checks=checks, all_compliant=all_compliant)

    def generate_bidding_template(self, file_ref, requirements: TenderRequirements, det_report: DeterministicReport, profile: CompanyProfile) -> BiddingTemplate:
        """
        Stage 3: Heuristic Analysis. Evaluates complex specifications and combines scorecards.
        """
        # Build prompt that merges extraction and deterministic report
        prompt = f"""
You are a senior defense contract auditor and bidding strategist for L&T (Larsen & Toubro) Defence.
Your task is to analyze the attached tender document and compile the final bidding template.

Here is the exact data from the previous pipeline steps:

1. Stage 1 Raw Extracted Requirements:
{requirements.model_dump_json(indent=2)}

2. Stage 2 Deterministic Python Compliance Report:
{det_report.model_dump_json(indent=2)}

3. L&T Company Profile Details (Capabilities, Test Facilities):
{profile.model_dump_json(indent=2)}

Instructions:
1. Review the deterministic scorecard from Stage 2. Include all of those checks directly in your final `deterministic_scorecard` output exactly as calculated.
2. Evaluate technical specifications and testing standards (like MIL-STD-810H vibration and temperature tests, J-STD-001 soldering) against L&T's capabilities and testing facilities. Complete the qualitative `technical_scorecard`.
3. Check the delivery timelines and capabilities.
4. Calculate the bid recommendation (GO / NO_GO / CONDITIONAL_GO).
   - If any deterministic check is NON_COMPLIANT, output NO_GO or CONDITIONAL_GO.
   - Outline a thorough, audit-ready rationale summarizing all matches and gaps.
"""
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        response = self._call_gemini(
            contents=[file_ref, prompt],
            schema=BiddingTemplate,
            model_name=model_name,
        )
        return BiddingTemplate.model_validate_json(response.text)

    def analyze_tender(self, pdf_path: str, profile_path: str) -> BiddingTemplate:
        """
        Runs the full 3-Stage pipeline end-to-end.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Tender file not found at: {pdf_path}")
        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"Company profile not found at: {profile_path}")

        # Load profile
        with open(profile_path, "r") as f:
            profile_data = json.load(f)
        profile = CompanyProfile.model_validate(profile_data)

        # Upload document
        print(f"[*] Uploading tender document: {pdf_path}...")
        file_ref = self.client.files.upload(file=pdf_path)
        print(f"[+] Upload complete. File ID: {file_ref.name}")

        try:
            # Stage 1: Extraction
            print("[*] Running Stage 1: Multimodal LLM Extraction...")
            requirements = self.extract_requirements(file_ref)

            # Stage 2: Deterministic Python matching
            print("[*] Running Stage 2: Deterministic Engine Python...")
            det_report = self.run_deterministic_checks(requirements, profile)

            # Stage 3: Heuristic Reasoning & Synthesis
            print("[*] Running Stage 3: Heuristic Analysis LLM...")
            bidding_template = self.generate_bidding_template(file_ref, requirements, det_report, profile)
            
            return bidding_template
            
        finally:
            print("[*] Cleaning up uploaded file from Gemini storage...")
            self.client.files.delete(name=file_ref.name)
            print("[+] Cleanup complete.")

# ==========================================
# 4. CLI & Runner
# ==========================================

def print_terminal_scorecard(result: BiddingTemplate):
    """Prints a beautiful summary of the results to the console."""
    print("\n" + "="*80)
    print(f" L&T HYBRID TENDER ANALYSIS REPORT: {result.tender_id}")
    print(f" Authority: {result.issuing_authority}")
    print(f" Deadline:  {result.submission_deadline}")
    print("="*80)
    
    print("\n[+] SCOPE OF WORK")
    print(result.scope_of_work)

    print("\n[+] STAGE 1: DETERMINISTIC SCOREGARD (Python Rules)")
    print(f"{'Parameter':<25} | {'Status':<18} | {'Citation':<20}")
    print("-"*80)
    for item in result.deterministic_scorecard:
        print(f"{item.parameter[:24]:<25} | {item.status.value:<18} | {item.citation:<20}")
        print(f"   Required: {item.required_value}")
        print(f"   L&T:      {item.company_value}")
        print(f"   Check:    {item.gap_analysis}")
        print("-" * 80)

    print("\n[+] STAGE 2: TECHNICAL FEASIBILITY MATRIX (Gemini reasoning)")
    print(f"{'Specification':<25} | {'Status':<18} | {'Citation':<20}")
    print("-"*80)
    for item in result.technical_scorecard:
        print(f"{item.parameter[:24]:<25} | {item.status.value:<18} | {item.citation:<20}")
        print(f"   Requirement: {item.tender_requirement}")
        print(f"   L&T Match:   {item.lt_capability}")
        print(f"   Analysis:    {item.gap_analysis}")
        if item.mitigation_action:
            print(f"   Mitigation:  {item.mitigation_action}")
        print("-" * 80)
        
    print(f"\n>>> OVERALL BID RECOMMENDATION: {result.recommendation.value} <<<")
    print(f"Rationale: {result.recommendation_rationale}")
    print("="*80 + "\n")

def main():
    parser = argparse.ArgumentParser(description="L&T Hybrid Tender Feasibility Analyzer")
    parser.add_argument("--pdf", required=True, help="Path to the tender PDF file")
    parser.add_argument("--profile", default="company_profile.json", help="Path to L&T company profile JSON database")
    parser.add_argument("--output", default="bidding_template_output.json", help="Path to save output JSON template")
    
    args = parser.parse_args()

    try:
        analyzer = TenderAnalyzer()
        result = analyzer.analyze_tender(args.pdf, args.profile)
        
        # Save output JSON
        with open(args.output, "w") as f:
            json.dump(result.model_dump(), f, indent=2)
        print(f"[+] Bidding template JSON saved to: {args.output}")
        
        # Display summary
        print_terminal_scorecard(result)
        
    except Exception as e:
        print(f"\n[!] Error during analysis: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
