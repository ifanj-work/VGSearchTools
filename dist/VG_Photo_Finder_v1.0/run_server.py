from waitress import serve
from app import app
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Starting server on http://0.0.0.0:5000")
    serve(app, host="0.0.0.0", port=5000)
