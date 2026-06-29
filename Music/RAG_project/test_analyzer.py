import os
import json
import sys
from analyzer import TenderAnalyzer, BiddingTemplate, print_terminal_scorecard

def main():
    print("="*60)
    print(" L&T DEFENCE HYBRID TENDER ANALYZER: END-TO-END TEST")
    print("="*60)
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[!] GEMINI_API_KEY not found in environment.")
        print("[i] Make sure '.env' file contains your key.")
        return

    pdf_path = "sample_tender.md"
    profile_path = "company_profile.json"
    output_path = "bidding_template_output.json"

    # Check file exists
    if not os.path.exists(pdf_path):
        print(f"[!] Test file not found: {pdf_path}")
        return
    if not os.path.exists(profile_path):
        print(f"[!] L&T Profile database not found: {profile_path}")
        return

    try:
        analyzer = TenderAnalyzer()
        print("[*] Launching 3-Stage Hybrid Decision Engine...")
        print("    Stage 1: LLM Extraction")
        print("    Stage 2: Deterministic Python rules matching")
        print("    Stage 3: LLM Heuristic analysis & synthesis\n")
        
        result = analyzer.analyze_tender(pdf_path, profile_path)
        
        # Save output JSON
        with open(output_path, "w") as f:
            json.dump(result.model_dump(), f, indent=2)
        print(f"[+] Output JSON saved successfully to: {output_path}")

        # Display formatted terminal scorecard
        print_terminal_scorecard(result)
        print("[+] End-to-end hybrid validation test PASSED.")

    except Exception as e:
        print(f"\n[!] Test execution failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
