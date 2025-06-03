import os
import uuid
import asyncio
from datetime import datetime
from flask import render_template, request, jsonify, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from app import app
from models import db, ProcessingTask, UploadedFile, ProcessingHistory
from processing import ProcessingManager
import logging

# Initialize processing manager
processing_manager = ProcessingManager()

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'audio': {'mp3', 'wav', 'flac', 'aac', 'm4a', 'ogg'},
    'video': {'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv'},
    'image': {'jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp'}
}

def allowed_file(filename, file_type):
    """Check if file extension is allowed for the given file type"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS.get(file_type, set())

def generate_unique_filename(original_filename):
    """Generate a unique filename to prevent conflicts"""
    name, ext = os.path.splitext(secure_filename(original_filename))
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}_{timestamp}_{unique_id}{ext}"

@app.route('/')
def index():
    """Main page with upload forms and processing options"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads and return file information"""
    try:
        uploaded_files = []
        
        for file_key in request.files:
            file = request.files[file_key]
            if file and file.filename:
                # Determine file type based on form field name
                if 'audio' in file_key:
                    file_type = 'audio'
                elif 'video' in file_key:
                    file_type = 'video'
                elif 'image' in file_key:
                    file_type = 'image'
                else:
                    file_type = 'unknown'
                
                if allowed_file(file.filename, file_type):
                    filename = generate_unique_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    file_size = os.path.getsize(file_path)
                    
                    uploaded_files.append({
                        'original_name': file.filename,
                        'saved_name': filename,
                        'file_type': file_type,
                        'size': file_size
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': f'File type not allowed for {file.filename}'
                    }), 400
        
        return jsonify({
            'success': True,
            'files': uploaded_files
        })
    
    except Exception as e:
        logging.error(f"Upload error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Upload failed: {str(e)}'
        }), 500

@app.route('/process', methods=['POST'])
def process_files():
    """Process files based on operation type"""
    try:
        data = request.get_json()
        operation = data.get('operation')
        files = data.get('files', [])
        options = data.get('options', {})
        
        if not operation or not files:
            return jsonify({
                'success': False,
                'error': 'Operation and files are required'
            }), 400
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Create database record for the task
        task = ProcessingTask(
            task_id=task_id,
            operation=operation,
            status='pending',
            message='Task created, waiting to start...'
        )
        db.session.add(task)
        
        # Add uploaded files to database
        total_size = 0
        for file_info in files:
            uploaded_file = UploadedFile(
                task_id=task_id,
                original_name=file_info['original_name'],
                saved_name=file_info['saved_name'],
                file_type=file_info['file_type'],
                file_size=file_info['size'],
                upload_path=os.path.join(app.config['UPLOAD_FOLDER'], file_info['saved_name'])
            )
            db.session.add(uploaded_file)
            total_size += file_info['size']
        
        db.session.commit()
        
        # Start processing in background
        result = processing_manager.process_files(
            task_id=task_id,
            operation=operation,
            files=files,
            options=options,
            upload_folder=app.config['UPLOAD_FOLDER'],
            output_folder=app.config['OUTPUT_FOLDER']
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'task_id': task_id,
                'message': 'Processing started'
            })
        else:
            # Update task status to failed
            task.status = 'failed'
            task.error_message = result['error']
            db.session.commit()
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
    
    except Exception as e:
        logging.error(f"Processing error: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Processing failed: {str(e)}'
        }), 500

@app.route('/status/<task_id>')
def get_status(task_id):
    """Get processing status for a task"""
    try:
        status = processing_manager.get_status(task_id)
        return jsonify(status)
    except Exception as e:
        logging.error(f"Status check error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Status check failed: {str(e)}'
        }), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Download processed file"""
    try:
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        if os.path.exists(file_path):
            return send_file(
                file_path,
                as_attachment=True,
                download_name=filename
            )
        else:
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
    except Exception as e:
        logging.error(f"Download error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Download failed: {str(e)}'
        }), 500

@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    """Clean up uploaded and output files"""
    try:
        # Clean up old files (older than 1 hour)
        import time
        current_time = time.time()
        
        for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
            for filename in os.listdir(folder):
                if filename == '.gitkeep':
                    continue
                file_path = os.path.join(folder, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getctime(file_path)
                    if file_age > 3600:  # 1 hour
                        os.remove(file_path)
        
        return jsonify({'success': True, 'message': 'Cleanup completed'})
    
    except Exception as e:
        logging.error(f"Cleanup error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Cleanup failed: {str(e)}'
        }), 500

@app.errorhandler(413)
def too_large(e):
    """Handle file too large error"""
    return jsonify({
        'success': False,
        'error': 'File too large. Maximum size is 500MB.'
    }), 413

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return render_template('index.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logging.error(f"Server error: {str(e)}")
    return jsonify({
        'success': False,
        'error': 'Internal server error occurred'
    }), 500
