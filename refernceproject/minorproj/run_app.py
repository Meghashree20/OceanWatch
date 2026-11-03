"""
Application Launcher for OCEANWATCH
Starts both the FastAPI backend and Streamlit dashboard
"""

import subprocess
import sys
import os
import time
import signal

def main():
    """Start the application"""
    print("Starting OCEANWATCH Application...")
    print("="*50)
    
    # Check if training has been run
    if not os.path.exists('data/processed/ocean_plastic_pollution_processed.csv'):
        print("Warning: Processed data not found.")
        print("   Please run the training pipeline first:")
        print("   python train_pipeline.py")
        print("\n   Do you want to run it now? (y/n): ", end="")
        response = input().strip().lower()
        if response == 'y':
            print("Running training pipeline...")
            subprocess.run([sys.executable, 'train_pipeline.py'])
        else:
            print("Exiting. Please run training pipeline first.")
            return
    
    print("\nStarting FastAPI Backend...")
    # Start FastAPI backend
    api_process = subprocess.Popen(
        [sys.executable, 'src/api.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give API time to start
    print("Waiting for API to initialize...")
    time.sleep(5)
    
    # Check if API started successfully
    if api_process.poll() is not None:
        print("Failed to start API backend")
        return
    
    print("API Backend started successfully")
    print("API available at: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    
    print("\nStarting Streamlit Dashboard...")
    # Start Streamlit dashboard
    dashboard_process = subprocess.Popen(
        [sys.executable, '-m', 'streamlit', 'run', 'app/dashboard.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give dashboard time to start
    time.sleep(3)
    
    if dashboard_process.poll() is not None:
        print("Failed to start Dashboard")
        api_process.terminate()
        return
    
    print("Dashboard started successfully")
    print("Dashboard available at: http://localhost:8501")
    
    print("\n" + "="*50)
    print("OCEANWATCH is now running!")
    print("="*50)
    print("\nPress Ctrl+C to stop the application")
    
    try:
        # Keep the script running
        while True:
            time.sleep(1)
            
            # Check if processes are still running
            if api_process.poll() is not None:
                print("API process stopped unexpectedly")
                break
            if dashboard_process.poll() is not None:
                print("Dashboard process stopped unexpectedly")
                break
                
    except KeyboardInterrupt:
        print("\n\nStopping OCEANWATCH...")
        api_process.terminate()
        dashboard_process.terminate()
        
        # Wait for processes to terminate
        try:
            api_process.wait(timeout=5)
            dashboard_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_process.kill()
            dashboard_process.kill()
        
        print("Application stopped successfully")

if __name__ == "__main__":
    main()
