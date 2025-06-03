#!/usr/bin/env python3
import uvicorn
from fastapi_app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=True)