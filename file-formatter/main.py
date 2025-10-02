import subprocess
import os
import shutil
import time
from typing import List, Tuple
from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from tempfile import TemporaryDirectory

# --- FastAPI Setup ---
app = FastAPI(title="Simple Media Optimization Tool")

# Configuration
CONVERTED_DIR = Path("converted_media")

# Ensure directories exist
CONVERTED_DIR.mkdir(exist_ok=True)

# Placeholder for Jinja2 (We are embedding the template below, but FastAPI expects a Templates object)
class EmbeddedTemplates:
    """Mock class to hold the embedded HTML content."""
    def TemplateResponse(self, name: str, context: dict):
        return HTMLResponse(content=HTML_CONTENT.format(**context))

templates = EmbeddedTemplates()

# --- Core Conversion Logic ---

def process_media(input_path: Path, quality: str) -> Tuple[Path, str]:
    """
    Converts the input media file (video or image) using ffmpeg for web optimization.

    Args:
        input_path: Path to the original media file.
        quality: A string indicating the desired quality ('high', 'medium', 'low').

    Returns:
        A tuple: (Path to the newly converted file, file_type_string)
    """
    ext = input_path.suffix.lower()
    
    # 1. Determine Conversion Parameters based on quality
    
    # CRF map for video (lower is higher quality/larger file)
    crf_map = {'high': '20', 'medium': '23', 'low': '28'}
    crf_value = crf_map.get(quality, '23')
    
    # WebP quality map (q:v 0-100, higher is better quality/larger size)
    webp_quality_map = {'high': '85', 'medium': '75', 'low': '60'}
    webp_quality = webp_quality_map.get(quality, '75')

    # 2. Setup Conversion Command (Video or Image)
    
    if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
        # VIDEO CONVERSION (H.264/MP4)
        output_filename = f"optimized_{input_path.stem}.mp4"
        file_type = "Video (MP4)"
        command = [
            'ffmpeg',
            '-i', str(input_path),
            '-vcodec', 'libx264',
            '-crf', crf_value,
            '-preset', 'fast',
            '-acodec', 'aac',
            '-movflags', '+faststart', # Optimizes for web streaming
            '-y', # Overwrite output files without asking
            str(CONVERTED_DIR / output_filename)
        ]
        
    elif ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
        # IMAGE CONVERSION (WebP is fast and efficient for web)
        output_filename = f"optimized_{input_path.stem}.webp"
        file_type = "Image (WebP)"
        command = [
            'ffmpeg',
            '-i', str(input_path),
            '-q:v', webp_quality, # WebP quality setting
            '-compression_level', '4', # Balance between speed and size (0=fastest, 6=slowest/smallest)
            '-y', 
            str(CONVERTED_DIR / output_filename)
        ]
    else:
        # Handle unsupported file types
        raise RuntimeError(f"Unsupported file type: {ext}. Only common video and image types are supported.")

    output_path = CONVERTED_DIR / output_filename

    # 3. Execute Command
    print(f"Running command ({file_type}): {' '.join(command)}")
    
    try:
        # Run the ffmpeg command
        subprocess.run(command, check=True, capture_output=True, text=True)
        return output_path, file_type
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error for {input_path.name}: {e.stderr}")
        # Extract the relevant error part for display
        error_detail = e.stderr.split('Error')[1].strip().split('\n')[0] if 'Error' in e.stderr else e.stderr.strip()
        raise RuntimeError(f"Conversion failed for {input_path.name}. Detail: {error_detail}")
    except FileNotFoundError:
        # This handles the case where ffmpeg is not installed on the system
        raise RuntimeError("FFmpeg command not found. Please install ffmpeg on your server.")


# --- HTMX Result Rendering ---

def build_results_html(results: List[dict]) -> str:
    """Generates the HTML summary table for all conversion results."""
    # Build table rows
    rows = []
    total_success = 0
    total_files = len(results)
    
    for r in results:
        is_success = r['status'] == 'success'
        if is_success:
            total_success += 1
            icon = '✅'
            status_text = f"<span class='font-mono text-sm bg-gray-100 px-2 py-0.5 rounded'>{r['output_name']} ({r['file_type']} - {r['time']})</span>"
            action = f"<a href='{r['download_url']}' download class='text-indigo-600 hover:text-indigo-800 font-medium text-sm'>Download</a>"
        else:
            icon = '❌'
            # Sanitize message for HTML
            message = str(r['message']).split('Detail:')[0].strip() 
            status_text = f"<span class='text-red-600 font-medium text-sm'>{message}</span>"
            action = "Failed"

        rows.append(f"""
        <tr class="{'' if is_success else 'bg-red-50'} border-b border-gray-100 hover:bg-gray-100 transition duration-100">
            <td class="p-3 text-sm font-medium text-gray-900">{r['filename']}</td>
            <td class="p-3 text-sm whitespace-nowrap text-center">{icon}</td>
            <td class="p-3 text-sm">{status_text}</td>
            <td class="p-3 text-sm text-right">{action}</td>
        </tr>
        """)

    # Overall summary and table structure
    summary_bg = 'bg-green-50 text-green-800 border-green-200' if total_success == total_files and total_success > 0 else 'bg-yellow-50 text-yellow-800 border-yellow-200'
    
    html = f"""
    <div class="space-y-6">
        <div class="p-4 rounded-lg border {summary_bg} shadow-md">
            <p class="font-bold text-lg">
                Optimization Batch Complete: <span class="text-xl font-extrabold">{total_success}</span> of <span class="text-xl font-extrabold">{total_files}</span> files succeeded.
            </p>
            <button onclick="window.location.reload()" class="mt-2 text-sm underline opacity-80 hover:opacity-100">
                Start a New Batch
            </button>
        </div>

        <div class="shadow overflow-x-auto border-b border-gray-200 sm:rounded-lg">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th scope="col" class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Original File</th>
                        <th scope="col" class="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                        <th scope="col" class="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Output File</th>
                        <th scope="col" class="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Download</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
    </div>
    """
    return html

# --- FastAPI Routes ---

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Serves the main page."""
    context = {
        "request": request,
        "current_status": "Ready to upload videos and/or images."
    }
    return templates.TemplateResponse("index.html", context)


@app.post("/convert", response_class=HTMLResponse)
async def convert_media_bulk(
    files: List[UploadFile] = File(...), 
    quality: str = Form("medium")
):
    """
    Handles bulk media upload, calls the conversion process for each file, 
    and returns a summary of results using HTMX.
    """
    if not files:
        return HTMLResponse("<div class='p-4 text-red-700'>No files uploaded. Please select one or more files.</div>")

    results = []
    # Use a temporary directory for all input files to ensure cleanup
    with TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        
        for file in files:
            result = {"filename": file.filename, "status": "failed", "message": "Processing failed."}
            input_file_path = temp_dir / file.filename
            
            try:
                # 1. Save the uploaded file temporarily
                with open(input_file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                # 2. Process the media
                start_time = time.time()
                output_path, file_type = process_media(input_file_path, quality)
                elapsed_time = time.time() - start_time
                
                download_url = f"/download/{output_path.name}"
                
                # 3. Record success
                result.update({
                    "status": "success",
                    "output_name": output_path.name,
                    "file_type": file_type,
                    "download_url": download_url,
                    "time": f"{elapsed_time:.2f}s"
                })
                
            except RuntimeError as e:
                result["message"] = str(e)
            except Exception as e:
                result["message"] = f"Internal server error: {e}"
            
            results.append(result)

    # 4. Construct HTMX result fragment for all files
    return build_results_html(results)


@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    Serves the converted media file for download.
    """
    file_path = CONVERTED_DIR / filename
    
    if not file_path.exists():
        return HTMLResponse(content="File not found.", status_code=404)

    def file_iterator():
        with open(file_path, mode="rb") as file_like:
            yield from file_like
    
    # Determine media type for streaming
    mime_type = "application/octet-stream"
    if filename.endswith(".mp4"):
        mime_type = "video/mp4"
    elif filename.endswith(".webp"):
        mime_type = "image/webp"

    # Stream the file to the browser
    return StreamingResponse(
        file_iterator(),
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

# --- Embedded HTML Template (Tailwind CSS, HTMX, Inter font) ---
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blog Media Optimizer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #f4f7f9;
        }}
    </style>
</head>
<body class="flex items-start justify-center min-h-screen p-4">
    <div class="w-full max-w-3xl bg-white p-8 rounded-xl shadow-2xl border border-gray-100 mt-10">
        <h1 class="text-3xl font-bold text-gray-800 mb-2">Blog Media Optimizer</h1>
        <p class="text-gray-500 mb-8">
            Upload videos (optimized to **MP4**) and images (optimized to **WebP**) in bulk for fast web delivery.
        </p>

        <!-- The main form. HTMX targets the result container below. -->
        <form 
            hx-post="/convert" 
            hx-target="#conversion-result" 
            hx-encoding="multipart/form-data" 
            hx-indicator="#loading-indicator"
            class="space-y-6"
        >
            <!-- File Upload Input -->
            <div>
                <label for="media-files" class="block text-sm font-medium text-gray-700 mb-2">Select Video and/or Image Files (Bulk Upload)</label>
                <input 
                    type="file" 
                    id="media-files" 
                    name="files" 
                    accept="video/*,image/*" 
                    multiple 
                    required 
                    class="block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />
            </div>

            <!-- Quality Selector -->
            <div>
                <label for="quality" class="block text-sm font-medium text-gray-700 mb-2">Optimization Quality (CRF/WebP Quality Setting)</label>
                <select id="quality" name="quality" class="mt-1 block w-full pl-3 pr-10 py-3 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md shadow-sm">
                    <option value="medium" selected>Medium (Good balance for both video and images)</option>
                    <option value="high">High Quality (Larger file, best visual quality)</option>
                    <option value="low">Smallest File (Aggressive compression, fastest loading)</option>
                </select>
            </div>

            <!-- Submit Button -->
            <button 
                type="submit" 
                class="w-full inline-flex items-center justify-center px-4 py-3 border border-transparent text-base font-medium rounded-lg shadow-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 transition duration-150"
            >
                Start Bulk Optimization
            </button>
        </form>

        <!-- Loading Indicator -->
        <div id="loading-indicator" class="hidden text-center mt-6 p-4 rounded-lg bg-yellow-50 text-yellow-700 border border-yellow-200"
            hx-indicator="true">
            <svg class="animate-spin h-5 w-5 mr-3 inline text-yellow-600" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Processing batch... this may take a moment depending on file sizes.
        </div>
        
        <!-- Result Display Area -->
        <div id="conversion-result" class="mt-6 p-6 border-2 border-dashed border-gray-200 rounded-lg text-center min-h-[150px] flex items-center justify-center">
            <p class="text-gray-400">{current_status}</p>
        </div>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    print("----------------------------------------------------------------------")
    print("Running the FastAPI server. Make sure you have 'ffmpeg' installed.")
    print("Open localhost:8000 in your browser.")
    print("To stop, press CTRL+C.")
    print("----------------------------------------------------------------------")
    # Using reload=True for development convenience. Remove in production.
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)
