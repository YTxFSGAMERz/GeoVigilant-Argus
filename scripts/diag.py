"""
GeoVigilant Argus Eye - System & Hardware Diagnostics
Checks Python, PyTorch CUDA GPU acceleration, ports, and environment.
"""
import sys
import os
import subprocess
import socket

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0

def run():
    print("=" * 72)
    print("  🌍 GEOVIGILANT ARGUS EYE // SYSTEM & HARDWARE DIAGNOSTIC REPORT")
    print("=" * 72)
    
    # 1. Python
    print(f"\n[+] PYTHON ENVIRONMENT:")
    print(f"    - Version      : {sys.version.split()[0]} ({sys.platform})")
    print(f"    - Executable   : {sys.executable}")
    
    # 2. PyTorch & CUDA
    print(f"\n[+] PYTORCH & ACCELERATION (NVIDIA):")
    try:
        import torch
        cuda_avail = torch.cuda.is_available()
        print(f"    - PyTorch Ver  : {torch.__version__}")
        print(f"    - CUDA Active  : {'YES (Hardware Accelerated)' if cuda_avail else 'NO (Running on CPU - HIGH HEAT)'}")
        if cuda_avail:
            dev_name = torch.cuda.get_device_name(0)
            vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
            print(f"    - GPU Device   : {dev_name} ({vram_gb} GB VRAM)")
            print(f"    - Compute Cap  : {torch.cuda.get_device_capability(0)}")
        else:
            print("    [!] WARNING: PyTorch is running in CPU-only mode.")
            print("        Run: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 --force-reinstall")
    except ImportError:
        print("    [-] PyTorch is not installed.")

    # 3. NVIDIA-SMI
    print(f"\n[+] DEDICATED GPU (NVIDIA-SMI):")
    try:
        smi_out = subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version,temperature.gpu,utilization.gpu", "--format=csv,noheader"], text=True)
        for line in smi_out.strip().splitlines():
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 4:
                print(f"    - GPU Model    : {parts[0]}")
                print(f"    - Driver Ver   : {parts[1]}")
                print(f"    - GPU Temp     : {parts[2]} °C")
                print(f"    - Utilization  : {parts[3]}")
    except Exception:
        print("    [-] Unable to query nvidia-smi directly.")

    # 4. Ports
    print(f"\n[+] NETWORK PORTS:")
    p5000 = check_port(5000)
    p5173 = check_port(5173)
    print(f"    - Port 5000 (Flask) : {'IN USE (Server is Active)' if p5000 else 'FREE (Ready to start)'}")
    print(f"    - Port 5173 (Vite)  : {'IN USE (Dev Server Active)' if p5173 else 'FREE (Ready to start)'}")

    # 5. Environment & Config
    print(f"\n[+] CONFIGURATION:")
    env_exists = os.path.exists(".env")
    print(f"    - .env File    : {'Present' if env_exists else 'Missing (Defaults will be used)'}")
    print(f"    - Argus Mode   : {os.environ.get('ARGUS_MODE', 'eco (30 FPS thermal optimized)')}")

    # 6. Summer Thermal Health Advice
    print(f"\n[+] SUMMER THERMAL ADVICE:")
    print("    * Windows Graphics: Ensure Firefox/Chrome is set to 'High Performance (NVIDIA RTX)' in Windows Settings.")
    print("    * Refresh Rate    : 30 FPS Eco Mode is active by default to prevent 165Hz overheating.")
    print("    * Airflow         : Keep the laptop elevated 1-2 cm from your desk surface.")
    print("=" * 72)

if __name__ == "__main__":
    run()
