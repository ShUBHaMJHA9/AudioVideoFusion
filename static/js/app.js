// Multimedia Processor JavaScript Application

class MultimediaProcessor {
    constructor() {
        this.selectedOperation = null;
        this.uploadedFiles = [];
        this.currentTaskId = null;
        this.statusCheckInterval = null;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.updateUI();
        this.initTheme();
    }
    
    initTheme() {
        const themeToggle = document.getElementById('theme-toggle');
        const savedTheme = localStorage.getItem('theme') || 'dark';
        
        if (savedTheme === 'light') {
            document.body.classList.add('light-theme');
            themeToggle.checked = true;
        }
        
        themeToggle.addEventListener('change', () => {
            if (themeToggle.checked) {
                document.body.classList.add('light-theme');
                localStorage.setItem('theme', 'light');
            } else {
                document.body.classList.remove('light-theme');
                localStorage.setItem('theme', 'dark');
            }
        });
    }
    
    async importFromUrl() {
        const urlInput = document.getElementById('media-url');
        const fileTypeSelect = document.getElementById('url-file-type');
        const url = urlInput.value.trim();
        
        if (!url) {
            this.showToast('Please enter a valid URL', 'error');
            return;
        }
        
        try {
            this.showToast('Importing file from URL...', 'info');
            
            // Create a temporary file object from URL
            const response = await fetch(url, { method: 'HEAD' });
            if (!response.ok) {
                throw new Error('Failed to access URL');
            }
            
            const contentType = response.headers.get('content-type') || '';
            const contentLength = response.headers.get('content-length') || 0;
            
            // Determine file type
            let fileType = fileTypeSelect.value;
            if (fileType === 'auto') {
                if (contentType.includes('audio')) fileType = 'audio';
                else if (contentType.includes('video')) fileType = 'video';
                else if (contentType.includes('image')) fileType = 'image';
                else fileType = 'unknown';
            }
            
            // Extract filename from URL
            const urlParts = url.split('/');
            const filename = urlParts[urlParts.length - 1] || 'media_file';
            
            // Add to uploaded files
            this.uploadedFiles.push({
                original_name: filename,
                saved_name: filename,
                file_type: fileType,
                size: parseInt(contentLength),
                url: url
            });
            
            // Close modal and show success
            const modal = bootstrap.Modal.getInstance(document.getElementById('urlModal'));
            modal.hide();
            
            this.showUploadResults();
            this.updateUI();
            this.showToast('File imported successfully!', 'success');
            
        } catch (error) {
            this.showToast('Failed to import file: ' + error.message, 'error');
        }
    }
    
    bindEvents() {
        // Operation selection
        document.querySelectorAll('.operation-card').forEach(card => {
            card.addEventListener('click', (e) => {
                this.selectOperation(card.dataset.operation);
            });
        });
        
        // Upload button
        document.getElementById('upload-btn').addEventListener('click', () => {
            this.uploadFiles();
        });
        
        // Process button
        document.getElementById('process-btn').addEventListener('click', () => {
            this.startProcessing();
        });
        
        // File input change events (delegated)
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('file-input')) {
                this.validateFiles();
            }
        });
    }
    
    selectOperation(operation) {
        // Remove previous selection
        document.querySelectorAll('.operation-card').forEach(card => {
            card.classList.remove('selected');
        });
        
        // Select new operation
        document.querySelector(`[data-operation="${operation}"]`).classList.add('selected');
        this.selectedOperation = operation;
        
        // Show upload section and setup forms
        this.setupUploadForms();
        this.setupOptionsSection();
        this.updateUI();
    }
    
    setupUploadForms() {
        const uploadForms = document.getElementById('upload-forms');
        const templates = {
            'merge_audio_video': ['audio-upload-template', 'video-upload-template'],
            'merge_audio_tracks': ['multiple-audio-template'],
            'audio_to_image': ['audio-upload-template', 'image-upload-template'],
            'convert_format': ['single-file-template'],
            'loop_audio': ['audio-upload-template']
        };
        
        uploadForms.innerHTML = '';
        
        const templateNames = templates[this.selectedOperation] || [];
        templateNames.forEach(templateName => {
            const template = document.getElementById(templateName);
            if (template) {
                const clone = template.content.cloneNode(true);
                uploadForms.appendChild(clone);
            }
        });
        
        this.validateFiles();
    }
    
    setupOptionsSection() {
        const optionsContent = document.getElementById('options-content');
        const optionsMap = {
            'merge_audio_video': `
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" id="loop-audio" name="loop_audio">
                    <label class="form-check-label" for="loop-audio">
                        Loop audio to match video duration
                    </label>
                </div>
            `,
            'merge_audio_tracks': `
                <div class="mb-3">
                    <label class="form-label">Mix Mode:</label>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="mix_mode" id="mix-overlay" value="overlay" checked>
                        <label class="form-check-label" for="mix-overlay">
                            Overlay (mix audio tracks together)
                        </label>
                    </div>
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="mix_mode" id="mix-concat" value="concatenate">
                        <label class="form-check-label" for="mix-concat">
                            Concatenate (play one after another)
                        </label>
                    </div>
                </div>
            `,
            'convert_format': `
                <div class="mb-3">
                    <label class="form-label">Target Format:</label>
                    <select class="form-select" name="target_format">
                        <option value="mp4">MP4 (Video)</option>
                        <option value="mp3">MP3 (Audio)</option>
                        <option value="wav">WAV (Audio)</option>
                        <option value="avi">AVI (Video)</option>
                    </select>
                </div>
            `,
            'loop_audio': `
                <div class="mb-3">
                    <label class="form-label">Loop Duration (seconds):</label>
                    <input type="number" class="form-control" name="duration" value="60" min="1" max="3600">
                    <div class="form-text">Maximum: 1 hour (3600 seconds)</div>
                </div>
            `
        };
        
        optionsContent.innerHTML = optionsMap[this.selectedOperation] || '';
    }
    
    validateFiles() {
        const fileInputs = document.querySelectorAll('.file-input');
        let hasFiles = false;
        
        fileInputs.forEach(input => {
            if (input.files && input.files.length > 0) {
                hasFiles = true;
            }
        });
        
        document.getElementById('upload-btn').disabled = !hasFiles;
    }
    
    async uploadFiles() {
        const uploadBtn = document.getElementById('upload-btn');
        const originalText = uploadBtn.innerHTML;
        
        try {
            uploadBtn.disabled = true;
            uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Uploading...';
            
            const formData = new FormData();
            const fileInputs = document.querySelectorAll('.file-input');
            
            fileInputs.forEach(input => {
                if (input.files) {
                    Array.from(input.files).forEach(file => {
                        formData.append(input.name, file);
                    });
                }
            });
            
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.uploadedFiles = result.files;
                this.showUploadResults();
                this.updateUI();
            } else {
                this.showAlert('Upload failed: ' + result.error, 'danger');
            }
        } catch (error) {
            this.showAlert('Upload error: ' + error.message, 'danger');
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = originalText;
        }
    }
    
    showUploadResults() {
        const uploadSection = document.getElementById('upload-section');
        const existingResults = uploadSection.querySelector('.upload-results');
        
        if (existingResults) {
            existingResults.remove();
        }
        
        const resultsDiv = document.createElement('div');
        resultsDiv.className = 'upload-results mt-3';
        resultsDiv.innerHTML = `
            <h6 class="text-success mb-3">
                <i class="fas fa-check-circle me-2"></i>
                Files Uploaded Successfully
            </h6>
            <div class="uploaded-files">
                ${this.uploadedFiles.map(file => `
                    <div class="upload-item">
                        <div class="file-info">
                            <strong>${file.original_name}</strong>
                            <div class="file-size">${this.formatFileSize(file.size)}</div>
                        </div>
                        <span class="badge file-type-badge bg-secondary">${file.file_type}</span>
                    </div>
                `).join('')}
            </div>
        `;
        
        uploadSection.querySelector('.card-body').appendChild(resultsDiv);
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    async startProcessing() {
        const processBtn = document.getElementById('process-btn');
        const originalText = processBtn.innerHTML;
        
        try {
            processBtn.disabled = true;
            processBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Starting...';
            
            // Gather options
            const options = this.gatherOptions();
            
            const response = await fetch('/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    operation: this.selectedOperation,
                    files: this.uploadedFiles,
                    options: options
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.currentTaskId = result.task_id;
                this.startStatusCheck();
                this.updateProcessingStatus('Processing started...', 0);
            } else {
                this.showAlert('Processing failed: ' + result.error, 'danger');
                processBtn.disabled = false;
                processBtn.innerHTML = originalText;
            }
        } catch (error) {
            this.showAlert('Processing error: ' + error.message, 'danger');
            processBtn.disabled = false;
            processBtn.innerHTML = originalText;
        }
    }
    
    gatherOptions() {
        const options = {};
        const optionsSection = document.getElementById('options-content');
        
        // Gather form inputs
        const inputs = optionsSection.querySelectorAll('input, select');
        inputs.forEach(input => {
            if (input.type === 'checkbox') {
                options[input.name] = input.checked;
            } else if (input.type === 'radio') {
                if (input.checked) {
                    options[input.name] = input.value;
                }
            } else {
                options[input.name] = input.value;
            }
        });
        
        return options;
    }
    
    startStatusCheck() {
        // Show loading modal
        const loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
        loadingModal.show();
        
        this.statusCheckInterval = setInterval(async () => {
            try {
                const response = await fetch(`/status/${this.currentTaskId}`);
                const status = await response.json();
                
                this.updateProcessingStatus(status.message, status.progress);
                
                // Update modal progress
                const modalProgressBar = document.getElementById('modal-progress-bar');
                const loadingText = document.getElementById('loading-text');
                modalProgressBar.style.width = status.progress + '%';
                loadingText.textContent = status.message;
                
                if (status.status === 'completed') {
                    loadingModal.hide();
                    this.handleProcessingComplete(status);
                } else if (status.status === 'failed') {
                    loadingModal.hide();
                    this.handleProcessingFailed(status);
                }
            } catch (error) {
                console.error('Status check error:', error);
                loadingModal.hide();
            }
        }, 1000);
    }
    
    updateProcessingStatus(message, progress) {
        const progressBar = document.getElementById('progress-bar');
        const statusMessage = document.getElementById('status-message');
        
        progressBar.style.width = progress + '%';
        progressBar.textContent = progress + '%';
        statusMessage.textContent = message;
        
        if (progress > 0) {
            progressBar.classList.add('processing-pulse');
        }
    }
    
    handleProcessingComplete(status) {
        clearInterval(this.statusCheckInterval);
        
        const progressBar = document.getElementById('progress-bar');
        progressBar.classList.remove('processing-pulse');
        progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
        progressBar.classList.add('bg-success');
        
        this.showResults(status.output_file);
        this.updateUI();
    }
    
    handleProcessingFailed(status) {
        clearInterval(this.statusCheckInterval);
        
        const progressBar = document.getElementById('progress-bar');
        progressBar.classList.remove('processing-pulse');
        progressBar.classList.add('bg-danger');
        
        this.showAlert('Processing failed: ' + status.message, 'danger');
        
        // Re-enable process button
        const processBtn = document.getElementById('process-btn');
        processBtn.disabled = false;
        processBtn.innerHTML = '<i class="fas fa-cogs me-2"></i>Start Processing';
    }
    
    showResults(outputFile) {
        // Show result modal
        const resultModal = new bootstrap.Modal(document.getElementById('resultModal'));
        const resultFilename = document.getElementById('result-filename');
        const downloadBtn = document.getElementById('download-btn');
        
        resultFilename.textContent = outputFile;
        downloadBtn.href = `/download/${outputFile}`;
        
        resultModal.show();
        
        // Also update the results section
        const resultsContent = document.getElementById('results-content');
        resultsContent.innerHTML = `
            <div class="results-download fade-in">
                <div class="file-info">
                    <h6><i class="fas fa-download me-2"></i>Processing Complete!</h6>
                    <small class="text-muted">File: ${outputFile}</small>
                </div>
                <div>
                    <a href="/download/${outputFile}" class="btn btn-gradient" download>
                        <i class="fas fa-download me-2"></i>Download
                    </a>
                </div>
            </div>
            <div class="mt-3">
                <button type="button" class="btn btn-outline-secondary" onclick="location.reload()">
                    <i class="fas fa-refresh me-2"></i>Process Another File
                </button>
            </div>
        `;
    }
    
    showToast(message, type = 'info') {
        const toastContainer = document.querySelector('.toast-container');
        const template = document.getElementById('toast-template');
        const toast = template.cloneNode(true);
        
        toast.id = 'toast-' + Date.now();
        toast.style.display = 'block';
        toast.classList.add(type);
        
        // Set toast styling based on type
        if (type === 'success') {
            toast.classList.add('text-bg-success');
        } else if (type === 'error') {
            toast.classList.add('text-bg-danger');
        } else if (type === 'warning') {
            toast.classList.add('text-bg-warning');
        } else {
            toast.classList.add('text-bg-info');
        }
        
        toast.querySelector('.toast-body').innerHTML = `
            <i class="fas fa-${type === 'error' ? 'exclamation-triangle' : type === 'success' ? 'check-circle' : 'info-circle'} me-2"></i>
            ${message}
        `;
        
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast, { delay: 5000 });
        bsToast.show();
        
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    showAlert(message, type) {
        this.showToast(message, type);
    }
    
    updateUI() {
        const uploadSection = document.getElementById('upload-section');
        const optionsSection = document.getElementById('options-section');
        const processingSection = document.getElementById('processing-section');
        const resultsSection = document.getElementById('results-section');
        
        // Show/hide sections based on current state
        uploadSection.style.display = this.selectedOperation ? 'block' : 'none';
        optionsSection.style.display = this.uploadedFiles.length > 0 ? 'block' : 'none';
        processingSection.style.display = this.uploadedFiles.length > 0 ? 'block' : 'none';
        
        // Enable process button if files are uploaded
        const processBtn = document.getElementById('process-btn');
        if (processBtn) {
            processBtn.disabled = this.uploadedFiles.length === 0 || this.currentTaskId !== null;
        }
        
        // Show results section if processing is complete
        if (this.currentTaskId && document.getElementById('results-content').innerHTML.trim()) {
            resultsSection.style.display = 'block';
        }
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new MultimediaProcessor();
});

// Utility functions
function showLoading(element, text = 'Loading...') {
    const originalContent = element.innerHTML;
    element.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>${text}`;
    element.disabled = true;
    
    return () => {
        element.innerHTML = originalContent;
        element.disabled = false;
    };
}

// Handle file size warnings
document.addEventListener('change', (e) => {
    if (e.target.type === 'file') {
        const files = Array.from(e.target.files);
        const maxSize = 500 * 1024 * 1024; // 500MB
        
        files.forEach(file => {
            if (file.size > maxSize) {
                alert(`Warning: ${file.name} is larger than 500MB and may fail to upload.`);
            }
        });
    }
});
