import os
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from werkzeug.utils import secure_filename
from processing import ProcessingManager

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create FastAPI app
app = FastAPI(title="Multimedia Processor", description="Process multimedia files using FFmpeg")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Initialize processing manager
processing_manager = ProcessingManager()

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'audio': {'mp3', 'wav', 'flac', 'aac', 'm4a', 'ogg'},
    'video': {'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv'},
    'image': {'jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp'}
}

# Pydantic models
class ProcessRequest(BaseModel):
    operation: str
    files: List[Dict]
    options: Dict = {}

class StatusResponse(BaseModel):
    status: str
    progress: int
    message: str
    output_file: Optional[str] = None
    error: Optional[str] = None

def allowed_file(filename: str, file_type: str) -> bool:
    """Check if file extension is allowed for the given file type"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS.get(file_type, set())

def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename to prevent conflicts"""
    name, ext = os.path.splitext(secure_filename(original_filename))
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}_{timestamp}_{unique_id}{ext}"

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page with upload forms and processing options"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_files(
    audio: List[UploadFile] = File(None),
    video: List[UploadFile] = File(None),
    image: List[UploadFile] = File(None),
    file: List[UploadFile] = File(None)
):
    """Handle file uploads and return file information"""
    try:
        uploaded_files = []
        
        # Process all file types
        file_groups = [
            (audio or [], 'audio'),
            (video or [], 'video'), 
            (image or [], 'image'),
            (file or [], 'unknown')
        ]
        
        for files, file_type in file_groups:
            for upload_file in files:
                if upload_file and upload_file.filename:
                    # Check file size
                    content = await upload_file.read()
                    if len(content) > MAX_FILE_SIZE:
                        raise HTTPException(status_code=413, detail="File too large. Maximum size is 500MB.")
                    
                    # Determine actual file type if unknown
                    if file_type == 'unknown':
                        ext = upload_file.filename.rsplit('.', 1)[-1].lower()
                        for ftype, extensions in ALLOWED_EXTENSIONS.items():
                            if ext in extensions:
                                file_type = ftype
                                break
                    
                    if not allowed_file(upload_file.filename, file_type):
                        raise HTTPException(status_code=400, detail=f"File type not allowed for {upload_file.filename}")
                    
                    filename = generate_unique_filename(upload_file.filename)
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    
                    # Write file
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    uploaded_files.append({
                        'original_name': upload_file.filename,
                        'saved_name': filename,
                        'file_type': file_type,
                        'size': len(content)
                    })
        
        return {"success": True, "files": uploaded_files}
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/process")
async def process_files(request: ProcessRequest):
    """Process files based on operation type"""
    try:
        if not request.operation or not request.files:
            raise HTTPException(status_code=400, detail="Operation and files are required")
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Start processing in background
        result = processing_manager.process_files(
            task_id=task_id,
            operation=request.operation,
            files=request.files,
            options=request.options,
            upload_folder=UPLOAD_FOLDER,
            output_folder=OUTPUT_FOLDER
        )
        
        if result['success']:
            return {"success": True, "task_id": task_id, "message": "Processing started"}
        else:
            raise HTTPException(status_code=400, detail=result['error'])
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """Get processing status for a task"""
    try:
        status = processing_manager.get_status(task_id)
        return status
    except Exception as e:
        logging.error(f"Status check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download processed file"""
    try:
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/octet-stream'
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@app.post("/cleanup")
async def cleanup_files():
    """Clean up uploaded and output files"""
    try:
        import time
        current_time = time.time()
        
        for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
            for filename in os.listdir(folder):
                if filename == '.gitkeep':
                    continue
                file_path = os.path.join(folder, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getctime(file_path)
                    if file_age > 3600:  # 1 hour
                        os.remove(file_path)
        
        return {"success": True, "message": "Cleanup completed"}
    
    except Exception as e:
        logging.error(f"Cleanup error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

# Error handlers
@app.exception_handler(413)
async def file_too_large_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=413,
        content={"success": False, "error": "File too large. Maximum size is 500MB."}
    )

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/") or request.headers.get("content-type") == "application/json":
        return JSONResponse(status_code=404, content={"success": False, "error": "Not found"})
    return templates.TemplateResponse("index.html", {"request": request}, status_code=404)

@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    logging.error(f"Server error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error occurred"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=True)