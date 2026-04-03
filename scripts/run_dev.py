import subprocess
import sys

subprocess.run([sys.executable, "app/main.py"] + sys.argv[1:], check=False)
