import traceback
import sys
import os

# Redirect stdout and stderr to a file
sys.stdout = open('app_output.log', 'w', encoding='utf-8')
sys.stderr = sys.stdout

try:
    import app
    # If app.py code is just in the file, we can import it if it has if __name__ == "__main__":
    # But it has if __name__ == "__main__": main()
    # So we need to call main()
    # app.main() # This requires click
    # Easier: run via subprocess but capture everything
    import subprocess
    result = subprocess.run([sys.executable, 'app.py'], capture_output=True, text=True)
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)
except Exception as e:
    print(f"Exception: {e}")
    traceback.print_exc()
finally:
    sys.stdout.close()
