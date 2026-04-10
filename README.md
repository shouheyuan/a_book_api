# Novel Backend

This is the Python backend service for the `swift-toolkit` application. Built with [FastAPI](https://fastapi.tiangolo.com/).

## Getting Started

### Prerequisites
* Python 3.8+

### Installation & Running

1. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the development server:
   ```bash
   python main.py
   # or
   uvicorn main:app --reload
   ```

### API Documentation
Once the server is running, the interactice Swagger UI API documentation will be available at `http://127.0.0.1:8000/docs`.
