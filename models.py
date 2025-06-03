import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class ProcessingTask(db.Model):
    """Model to track multimedia processing tasks"""
    __tablename__ = 'processing_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    operation = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    progress = db.Column(db.Integer, default=0)
    message = db.Column(db.Text)
    output_file = db.Column(db.String(255))
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Relationship to uploaded files
    uploaded_files = db.relationship('UploadedFile', backref='task', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ProcessingTask {self.task_id}: {self.operation} - {self.status}>'


class UploadedFile(db.Model):
    """Model to track uploaded files for processing tasks"""
    __tablename__ = 'uploaded_files'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(36), db.ForeignKey('processing_tasks.task_id'), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    saved_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)
    file_size = db.Column(db.BigInteger)
    upload_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<UploadedFile {self.original_name} ({self.file_type})>'


class ProcessingHistory(db.Model):
    """Model to keep history of all processing operations"""
    __tablename__ = 'processing_history'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(36), nullable=False, index=True)
    operation = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    input_files_count = db.Column(db.Integer)
    output_file = db.Column(db.String(255))
    processing_time_seconds = db.Column(db.Float)
    file_sizes_total = db.Column(db.BigInteger)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProcessingHistory {self.task_id}: {self.operation}>'