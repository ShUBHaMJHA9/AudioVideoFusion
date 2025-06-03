import os
import ffmpeg
import threading
import logging
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional

class ProcessingManager:
    """Manages multimedia processing tasks using ffmpeg-python"""
    
    def __init__(self):
        self.tasks = {}  # Store task status and results
        self.lock = threading.Lock()
    
    def update_database_status(self, task_id: str, status: str, progress: int, message: str, output_file: Optional[str] = None):
        """Update database with task status"""
        try:
            # Import here to avoid circular imports
            from models import db, ProcessingTask, ProcessingHistory
            from app import app
            
            with app.app_context():
                task = ProcessingTask.query.filter_by(task_id=task_id).first()
                if task:
                    task.status = status
                    task.progress = progress
                    task.message = message
                    task.updated_at = datetime.utcnow()
                    if output_file:
                        task.output_file = output_file
                    if status == 'completed':
                        task.completed_at = datetime.utcnow()
                        # Add to processing history
                        history = ProcessingHistory(
                            task_id=task_id,
                            operation=task.operation,
                            status=status,
                            input_files_count=len(task.uploaded_files),
                            output_file=output_file,
                            file_sizes_total=sum(f.file_size or 0 for f in task.uploaded_files)
                        )
                        db.session.add(history)
                    elif status == 'failed':
                        task.error_message = message
                    
                    db.session.commit()
        except Exception as e:
            logging.error(f"Failed to update database status: {str(e)}")
    
    def process_files(self, task_id: str, operation: str, files: List[Dict], 
                     options: Dict, upload_folder: str, output_folder: str) -> Dict:
        """Start processing files in a background thread"""
        try:
            # Initialize task status
            with self.lock:
                self.tasks[task_id] = {
                    'status': 'started',
                    'progress': 0,
                    'message': 'Processing started...',
                    'output_file': None,
                    'error': None
                }
            
            # Start processing in background thread
            thread = threading.Thread(
                target=self._process_in_background,
                args=(task_id, operation, files, options, upload_folder, output_folder)
            )
            thread.daemon = True
            thread.start()
            
            return {'success': True, 'task_id': task_id}
        
        except Exception as e:
            logging.error(f"Failed to start processing: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _process_in_background(self, task_id: str, operation: str, files: List[Dict], 
                              options: Dict, upload_folder: str, output_folder: str):
        """Background processing method"""
        try:
            self._update_task_status(task_id, 'processing', 10, 'Initializing...')
            
            # Map operation to processing method
            operation_map = {
                'merge_audio_video': self._merge_audio_video,
                'merge_audio_tracks': self._merge_audio_tracks,
                'audio_to_image': self._audio_to_image,
                'convert_format': self._convert_format,
                'loop_audio': self._loop_audio
            }
            
            if operation not in operation_map:
                raise ValueError(f"Unknown operation: {operation}")
            
            self._update_task_status(task_id, 'processing', 25, 'Processing files...')
            
            # Execute the operation
            output_file = operation_map[operation](
                files, options, upload_folder, output_folder, task_id
            )
            
            self._update_task_status(task_id, 'completed', 100, 'Processing completed!', output_file)
        
        except Exception as e:
            logging.error(f"Processing failed for task {task_id}: {str(e)}")
            self._update_task_status(task_id, 'failed', 0, f'Processing failed: {str(e)}')
    
    def _update_task_status(self, task_id: str, status: str, progress: int, 
                           message: str, output_file: Optional[str] = None):
        """Update task status thread-safely"""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id].update({
                    'status': status,
                    'progress': progress,
                    'message': message,
                    'output_file': output_file,
                    'updated_at': datetime.now().isoformat()
                })
        
        # Also update database
        self.update_database_status(task_id, status, progress, message, output_file)
    
    def get_status(self, task_id: str) -> Dict:
        """Get current status of a task"""
        with self.lock:
            return self.tasks.get(task_id, {
                'status': 'not_found',
                'error': 'Task not found'
            })
    
    def _merge_audio_video(self, files: List[Dict], options: Dict, 
                          upload_folder: str, output_folder: str, task_id: str) -> str:
        """Merge audio with video, optionally looping audio"""
        audio_file = None
        video_file = None
        
        # Find audio and video files
        for file in files:
            if file['file_type'] == 'audio':
                audio_file = os.path.join(upload_folder, file['saved_name'])
            elif file['file_type'] == 'video':
                video_file = os.path.join(upload_folder, file['saved_name'])
        
        if not audio_file or not video_file:
            raise ValueError("Both audio and video files are required")
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"merged_video_{timestamp}.mp4"
        output_path = os.path.join(output_folder, output_file)
        
        self._update_task_status(task_id, 'processing', 50, 'Merging audio and video...')
        
        try:
            # Get video duration
            video_probe = ffmpeg.probe(video_file)
            video_duration = float(video_probe['streams'][0]['duration'])
            
            # Create input streams
            video_input = ffmpeg.input(video_file)
            
            # Handle audio looping if requested
            if options.get('loop_audio', False):
                # Loop audio to match video duration
                audio_probe = ffmpeg.probe(audio_file)
                audio_duration = float(audio_probe['streams'][0]['duration'])
                
                if audio_duration < video_duration:
                    # Calculate loop count
                    loop_count = int(video_duration / audio_duration) + 1
                    audio_input = ffmpeg.input(audio_file, stream_loop=loop_count)
                else:
                    audio_input = ffmpeg.input(audio_file)
            else:
                audio_input = ffmpeg.input(audio_file)
            
            # Merge audio and video
            output = ffmpeg.output(
                video_input,
                audio_input,
                output_path,
                vcodec='libx264',
                acodec='aac',
                t=video_duration  # Limit to video duration
            )
            
            ffmpeg.run(output, overwrite_output=True, quiet=True)
            
            return output_file
        
        except Exception as e:
            raise Exception(f"Failed to merge audio and video: {str(e)}")
    
    def _merge_audio_tracks(self, files: List[Dict], options: Dict, 
                           upload_folder: str, output_folder: str, task_id: str) -> str:
        """Merge multiple audio tracks"""
        audio_files = []
        
        # Find all audio files
        for file in files:
            if file['file_type'] == 'audio':
                audio_files.append(os.path.join(upload_folder, file['saved_name']))
        
        if len(audio_files) < 2:
            raise ValueError("At least 2 audio files are required for merging")
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"merged_audio_{timestamp}.mp3"
        output_path = os.path.join(output_folder, output_file)
        
        self._update_task_status(task_id, 'processing', 50, 'Merging audio tracks...')
        
        try:
            # Create input streams
            inputs = [ffmpeg.input(audio_file) for audio_file in audio_files]
            
            # Mix audio streams
            if options.get('mix_mode') == 'concatenate':
                # Concatenate audio files
                output = ffmpeg.concat(*inputs, v=0, a=1).output(output_path)
            else:
                # Mix audio files (overlay)
                mixed = ffmpeg.filter(inputs, 'amix', inputs=len(inputs))
                output = ffmpeg.output(mixed, output_path)
            
            ffmpeg.run(output, overwrite_output=True, quiet=True)
            
            return output_file
        
        except Exception as e:
            raise Exception(f"Failed to merge audio tracks: {str(e)}")
    
    def _audio_to_image(self, files: List[Dict], options: Dict, 
                       upload_folder: str, output_folder: str, task_id: str) -> str:
        """Combine audio with image (create video with static image)"""
        audio_file = None
        image_file = None
        
        # Find audio and image files
        for file in files:
            if file['file_type'] == 'audio':
                audio_file = os.path.join(upload_folder, file['saved_name'])
            elif file['file_type'] == 'image':
                image_file = os.path.join(upload_folder, file['saved_name'])
        
        if not audio_file or not image_file:
            raise ValueError("Both audio and image files are required")
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"audio_image_{timestamp}.mp4"
        output_path = os.path.join(output_folder, output_file)
        
        self._update_task_status(task_id, 'processing', 50, 'Creating video from audio and image...')
        
        try:
            # Use subprocess to get audio duration
            probe_cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                '-show_format', '-show_streams', audio_file
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            import json
            probe_data = json.loads(result.stdout)
            audio_duration = float(probe_data['format']['duration'])
            
            # Create video from static image and audio using subprocess
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-loop', '1', '-i', image_file,
                '-i', audio_file,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-t', str(audio_duration),
                '-pix_fmt', 'yuv420p',
                '-r', '1',
                output_path
            ]
            
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            
            return output_file
        
        except Exception as e:
            raise Exception(f"Failed to create video from audio and image: {str(e)}")
    
    def _convert_format(self, files: List[Dict], options: Dict, 
                       upload_folder: str, output_folder: str, task_id: str) -> str:
        """Convert file format"""
        if len(files) != 1:
            raise ValueError("Format conversion requires exactly one file")
        
        input_file = os.path.join(upload_folder, files[0]['saved_name'])
        target_format = options.get('target_format', 'mp4')
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(files[0]['saved_name'])[0]
        output_file = f"{base_name}_converted_{timestamp}.{target_format}"
        output_path = os.path.join(output_folder, output_file)
        
        self._update_task_status(task_id, 'processing', 50, f'Converting to {target_format}...')
        
        try:
            input_stream = ffmpeg.input(input_file)
            
            # Set codec based on target format
            codec_map = {
                'mp4': {'vcodec': 'libx264', 'acodec': 'aac'},
                'mp3': {'acodec': 'mp3'},
                'wav': {'acodec': 'pcm_s16le'},
                'avi': {'vcodec': 'libx264', 'acodec': 'mp3'}
            }
            
            codecs = codec_map.get(target_format, {})
            output = ffmpeg.output(input_stream, output_path, **codecs)
            
            ffmpeg.run(output, overwrite_output=True, quiet=True)
            
            return output_file
        
        except Exception as e:
            raise Exception(f"Failed to convert format: {str(e)}")
    
    def _loop_audio(self, files: List[Dict], options: Dict, 
                   upload_folder: str, output_folder: str, task_id: str) -> str:
        """Loop audio file for specified duration"""
        if len(files) != 1 or files[0]['file_type'] != 'audio':
            raise ValueError("Audio looping requires exactly one audio file")
        
        input_file = os.path.join(upload_folder, files[0]['saved_name'])
        loop_duration = options.get('duration', 60)  # Default 60 seconds
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(files[0]['saved_name'])[0]
        output_file = f"{base_name}_looped_{timestamp}.mp3"
        output_path = os.path.join(output_folder, output_file)
        
        self._update_task_status(task_id, 'processing', 50, f'Looping audio for {loop_duration} seconds...')
        
        try:
            # Get original audio duration
            audio_probe = ffmpeg.probe(input_file)
            original_duration = float(audio_probe['streams'][0]['duration'])
            
            # Calculate loop count
            loop_count = int(loop_duration / original_duration) + 1
            
            input_stream = ffmpeg.input(input_file, stream_loop=loop_count)
            output = ffmpeg.output(input_stream, output_path, t=loop_duration)
            
            ffmpeg.run(output, overwrite_output=True, quiet=True)
            
            return output_file
        
        except Exception as e:
            raise Exception(f"Failed to loop audio: {str(e)}")
