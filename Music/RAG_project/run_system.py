import subprocess
import sys
import time
import os

def main():
    print("="*60)
    # Correctly identify python execution path
    py_exec = sys.executable
    
    # 1. Start backend server
    print("[*] Starting FastAPI Backend on http://127.0.0.1:8000...")
    backend = subprocess.Popen(
        [py_exec, "-m", "uvicorn", "app_backend:app", "--host", "127.0.0.1", "--port", "8000"]
    )
    
    # Wait briefly for backend to warm up
    time.sleep(2)
    
    # 2. Start frontend dashboard
    print("[*] Starting Streamlit Frontend on http://127.0.0.1:8501...")
    frontend = subprocess.Popen(
        [py_exec, "-m", "streamlit", "run", "app_frontend.py"]
    )
    
    print("\n" + "="*60)
    print(" [+] BOTH SERVICES RUNNING CONCURRENTLY!")
    print("     - Frontend Dashboard:  http://127.0.0.1:8501")
    print("     - API documentation:   http://127.0.0.1:8000/docs")
    print("="*60)
    print("\nPress Ctrl+C to terminate both servers...\n")
    
    try:
        # Keep launcher alive
        while True:
            # Check if any process died
            if backend.poll() is not None:
                print("[!] Backend process stopped unexpectedly.")
                break
            if frontend.poll() is not None:
                print("[!] Frontend process stopped unexpectedly.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[*] Shutting down servers safely...")
        backend.terminate()
        frontend.terminate()
        backend.wait()
        frontend.wait()
        print("[+] All services terminated successfully.")

if __name__ == "__main__":
    main()
