import os
import sys
import json
import argparse
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# We will dynamically import genai so that the file is syntactically valid even if requirements aren't installed yet.
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

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

class TechnicalSpecification(BaseModel):
    parameter: str = Field(description="The name of the technical parameter, e.g., 'Operating Temperature Range', 'Output Power'.")
    requirement: str = Field(description="The exact requirement details specified in the tender.")
    citation: str = Field(description="Exact page number and section clause where this specification is located.")

class FinancialConstraint(BaseModel):
    parameter: str = Field(description="The financial item name, e.g., 'EMD', 'Performance Security', 'Estimated Bid Value', 'Turnover'.")
    value: str = Field(description="The financial value or percentage required.")
    citation: str = Field(description="Exact page number and section clause where this constraint is located.")

class FeasibilityItem(BaseModel):
    parameter: str = Field(description="The criterion analyzed, e.g., 'Turnover Limit', 'Military Testing Standard compliance', 'Delivery Timeline'.")
    tender_requirement: str = Field(description="The requirement as stated in the tender document.")
    lt_capability: str = Field(description="Mapping of L&T's capability or matching stats against this requirement.")
    status: ComplianceStatus = Field(description="The compliance status of L&T against this requirement.")
    gap_analysis: str = Field(description="Detailed analysis of the gap or alignment between the requirement and L&T's capability.")
    mitigation_action: Optional[str] = Field(description="Actionable suggestion to mitigate risks or address the gap (if applicable).")
    citation: str = Field(description="Exact page number and section clause where this constraint is located.")

class BiddingTemplate(BaseModel):
    tender_id: str = Field(description="The unique Tender Identification Number / Reference Number.")
    issuing_authority: str = Field(description="The government department or authority issuing the tender (e.g., Indian Army, MoD).")
    scope_of_work: str = Field(description="A brief description of the scope of work and requirements.")
    submission_deadline: str = Field(description="The deadline date and time for bid submission.")
    
    technical_specifications: List[TechnicalSpecification] = Field(description="Key technical specifications and testing standards extracted from the document.")
    financial_constraints: List[FinancialConstraint] = Field(description="Financial requirements, bank guarantees, and bid values.")
    eligibility_criteria: List[str] = Field(description="Summary of experience, licensing, and certification requirements.")
    
    feasibility_scorecard: List[FeasibilityItem] = Field(description="Itemized feasibility comparison based on L&T's capability input.")
    
    recommendation: BidRecommendation = Field(description="Overall bid recommendation (GO / NO_GO / CONDITIONAL_GO).")
    recommendation_rationale: str = Field(description="Comprehensive technical and financial explanation behind the recommendation.")

# ==========================================
# 2. Analyzer Logic
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

    def analyze_tender(self, pdf_path: str, lt_capabilities: str) -> BiddingTemplate:
        """
        Uploads the PDF tender to Gemini, runs structured extraction mapping it against L&T's capabilities,
        and returns a validated BiddingTemplate object.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

        print(f"[*] Uploading tender document to Google GenAI: {pdf_path}...")
        file_ref = self.client.files.upload(file=pdf_path)
        print(f"[+] Upload complete. File ID: {file_ref.name}")

        prompt = f"""
You are a senior defense contract auditor and bidding strategist for L&T (Larsen & Toubro) Defence.
Your task is to analyze the attached defense tender document and evaluate it against L&T's core capabilities.

L&T's Capabilities and Budget Constraints for this bid analysis:
{lt_capabilities}

Instructions:
1. Examine the entire document, paying close attention to technical specifications, military standards (e.g., MIL-STD, IS, DEF-STAN), testing protocols, delivery timelines, financial guarantees (EMD, PBG), and vendor eligibility criteria.
2. Cross-reference related clauses (e.g., verifying if technical specs require certifications detailed elsewhere).
3. Evaluate feasibility for each key parameter against L&T's capabilities, determining if we are COMPLIANT, NON_COMPLIANT, PARTIALLY_COMPLIANT, or if there is a major RISK.
4. For every claim, requirement, or constraint, provide the exact page number and section citation (e.g., 'Page 43, Section 4.2.1') for auditability.
5. Synthesize this data and compile the final bidding template including a structured scorecard and an overall recommendation (GO, NO_GO, or CONDITIONAL_GO).
"""

        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        print(f"[*] Processing document with {model_name} (Multimodal Analyzer)...")
        try:
            response = self.client.models.generate_content(
                model=model_name,
                contents=[file_ref, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=BiddingTemplate,
                    temperature=0.1,  # Low temperature for highly deterministic analytical output
                )
            )
            
            # Parse the response text as JSON and load it into our Pydantic model
            raw_json = response.text
            result = BiddingTemplate.model_validate_json(raw_json)
            return result
            
        finally:
            print("[*] Cleaning up uploaded file from Gemini storage...")
            self.client.files.delete(name=file_ref.name)
            print("[+] Cleanup complete.")

# ==========================================
# 3. CLI & Runner
# ==========================================

def print_terminal_scorecard(result: BiddingTemplate):
    """Prints a beautiful summary of the results to the console."""
    print("\n" + "="*80)
    print(f" TENDER ANALYSIS REPORT: {result.tender_id}")
    print(f" Authority: {result.issuing_authority}")
    print(f" Deadline:  {result.submission_deadline}")
    print("="*80)
    
    print("\n[+] SCOPE OF WORK")
    print(result.scope_of_work)
    
    print("\n[+] FINANCIAL REQUIREMENTS")
    for item in result.financial_constraints:
        print(f" - {item.parameter}: {item.value} ({item.citation})")
        
    print("\n[+] ELIGIBILITY CRITERIA")
    for criteria in result.eligibility_criteria:
        print(f" - {criteria}")

    print("\n[+] FEASIBILITY MATRIX & SCORECARD")
    print(f"{'Parameter':<25} | {'Status':<18} | {'Citation':<20}")
    print("-"*80)
    for item in result.feasibility_scorecard:
        status_color = item.status.value
        print(f"{item.parameter[:24]:<25} | {status_color:<18} | {item.citation:<20}")
        print(f"   Requirement: {item.tender_requirement}")
        print(f"   L&T Match:   {item.lt_capability}")
        print(f"   Gap Analysis: {item.gap_analysis}")
        if item.mitigation_action:
            print(f"   Mitigation:  {item.mitigation_action}")
        print("-" * 80)
        
    print(f"\n>>> OVERALL BID RECOMMENDATION: {result.recommendation.value} <<<")
    print(f"Rationale: {result.recommendation_rationale}")
    print("="*80 + "\n")

def main():
    parser = argparse.ArgumentParser(description="L&T Defence Tender Feasibility Analyzer")
    parser.add_argument("--pdf", required=True, help="Path to the tender PDF file")
    parser.add_argument("--output", default="bidding_template_output.json", help="Path to save output JSON template")
    parser.add_argument("--capabilities", help="Path to a text file containing L&T's capability limits")
    
    args = parser.parse_args()

    # Default capabilities if none provided
    if args.capabilities and os.path.exists(args.capabilities):
        with open(args.capabilities, "r") as f:
            lt_capabilities = f.read()
    else:
        print("[!] No custom capabilities file provided. Using default L&T capabilities matrix.")
        lt_capabilities = """
- Annual Turnover: $600 Million USD
- Certification: ISO 9001, AS9100 Rev D, ISO 14001, OHSAS 18001.
- Experience: 15 years in missile launchers, naval gun mounts, armored vehicles, and aerospace assemblies. Successfully executed 4 large-scale government defense supply contracts in last 5 years.
- Security Clearance: Valid Department of Defence production clearance, facility security clearance (Secret level).
- Technical Capability: Advanced multi-axis CNC machining, structural welding under ISO 3834-2, composite fabrication, electronics integration conforming to J-STD-001.
- Testing Facilities: In-house environmental chambers (-40C to +85C), vibe tables up to 10g, EMI/EMC compliance chamber.
- Delivery Lead Time capability: Standard delivery timeline for medium systems is 14 months. Express tooling can reduce this to 11 months with an additional 15% manufacturing cost.
- Budget/EMD Limit: Max EMD bank guarantee available is $2 Million USD. Minimum acceptable operating margin is 12%.
"""

    try:
        analyzer = TenderAnalyzer()
        result = analyzer.analyze_tender(args.pdf, lt_capabilities)
        
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
