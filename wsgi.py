import os
import sys

# Add current dir to path so 'agem' imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agem.server import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
