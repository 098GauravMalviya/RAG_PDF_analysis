import os
import json
from analyzer import BiddingTemplate, print_terminal_scorecard, TenderAnalyzer

MOCK_CAPABILITIES = """
- Annual Turnover: $600 Million USD
- Certification: ISO 9001, AS9100 Rev D
- Experience: Executed 4 large-scale defense supply contracts in last 5 years.
- Security Clearance: Valid Secret level.
- EMD Limit: Max EMD bank guarantee available is $2 Million USD.
"""

MOCK_RESPONSE_DATA = {
  "tender_id": "TND-MOD-2026-8923",
  "issuing_authority": "Ministry of Defence (MoD), Indian Govt.",
  "scope_of_work": "Supply of fifty (50) mobile launcher assemblies for tactical missile systems.",
  "submission_deadline": "August 30, 2026",
  "technical_specifications": [
    {
      "parameter": "Operating Temperature",
      "requirement": "-30°C to +75°C",
      "citation": "Page 1, Clause 2.1.1"
    },
    {
      "parameter": "Environmental Standard",
      "requirement": "MIL-STD-810H vibration and high-humidity certified",
      "citation": "Page 1, Clause 2.1.2"
    },
    {
      "parameter": "Quality Assurance Standard",
      "requirement": "AS9100 Rev D certification required",
      "citation": "Page 1, Clause 2.2.2"
    }
  ],
  "financial_constraints": [
    {
      "parameter": "Earnest Money Deposit (EMD)",
      "value": "$1.5 Million USD",
      "citation": "Page 1, Clause 3.1"
    },
    {
      "parameter": "Performance Bank Guarantee (PBG)",
      "value": "10% of contract value",
      "citation": "Page 1, Clause 3.2"
    },
    {
      "parameter": "Ceiling Budget",
      "value": "$12.5 Million USD",
      "citation": "Page 1, Clause 3.3"
    }
  ],
  "eligibility_criteria": [
    "Average annual turnover of at least $500 Million USD over last 3 years.",
    "Successfully manufactured and delivered at least three defense assemblies in the last 5 years.",
    "Valid Secret-level security clearance from Department of Defence."
  ],
  "feasibility_scorecard": [
    {
      "parameter": "Turnover Requirement",
      "tender_requirement": "Min $500 Million USD",
      "lt_capability": "L&T average annual turnover is $600 Million USD.",
      "status": "COMPLIANT",
      "gap_analysis": "Compliant. Exceeds requirement by $100 Million USD.",
      "mitigation_action": None,
      "citation": "Page 1, Clause 4.1"
    },
    {
      "parameter": "Earnest Money Deposit (EMD)",
      "tender_requirement": "$1.5 Million USD",
      "lt_capability": "L&T limit is $2.0 Million USD.",
      "status": "COMPLIANT",
      "gap_analysis": "EMD value is well within L&T's maximum bank guarantee capacity.",
      "mitigation_action": None,
      "citation": "Page 1, Clause 3.1"
    },
    {
      "parameter": "Testing Standards",
      "tender_requirement": "MIL-STD-810H vibration and humidity testing",
      "lt_capability": "L&T has environmental chambers and vibration tables up to 10g.",
      "status": "COMPLIANT",
      "gap_analysis": "Compliant. L&T's in-house capabilities meet the testing parameters.",
      "mitigation_action": None,
      "citation": "Page 1, Clause 2.1.2"
    }
  ],
  "recommendation": "GO",
  "recommendation_rationale": "L&T is fully compliant with all major technical, financial, and eligibility requirements. The $12.5M ceiling budget provides a healthy margin above L&T's operating targets, and the in-house test rigs minimize outsourcing risks."
}

def main():
    print("="*60)
    print(" L&T DEFENCE TENDER ANALYZER: TEST & VALIDATION")
    print("="*60)
    
    api_key = os.getenv("GEMINI_API_KEY")
    
    # 1. Validation Test: Pydantic Schema Parsing
    print("[*] Test 1: Validating Pydantic Schema parsing & strict formatting...")
    try:
        validated_template = BiddingTemplate.model_validate(MOCK_RESPONSE_DATA)
        print("[+] Validation SUCCESS: Pydantic parsed mock data perfectly.")
        
        # Test terminal formatting printing
        print("[*] Displaying sample terminal scorecard output:")
        print_terminal_scorecard(validated_template)
    except Exception as e:
        print(f"[!] Validation FAILED: {e}")
        return

    # 2. Live API Test
    print("[*] Test 2: Checking for live Gemini API configurations...")
    if not api_key:
        print("[!] GEMINI_API_KEY not found in environment.")
        print("[i] To run live validation on the sample tender document:")
        print("    1. Rename '.env.example' to '.env'")
        print("    2. Populate your GEMINI_API_KEY in '.env'")
        print("    3. Run: python analyzer.py --pdf sample_tender.md")
    else:
        print("[+] GEMINI_API_KEY found! Launching live API test on sample_tender.md...")
        try:
            analyzer = TenderAnalyzer()
            result = analyzer.analyze_tender("sample_tender.md", MOCK_CAPABILITIES)
            
            print("\n" + "#"*40)
            print(" LIVE API RESULT SUCCESS")
            print("#"*40)
            print_terminal_scorecard(result)
        except Exception as e:
            print(f"[!] Live API execution failed: {e}")

if __name__ == "__main__":
    main()
