import subprocess
import shutil
import time
from pathlib import Path
from tempfile import TemporaryDirectory
import json # Added for JSON post storage
import os
from dotenv import load_dotenv

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel
from datetime import datetime
from google.cloud import storage # Re-import Google Cloud Storage
from starlette.middleware.sessions import SessionMiddleware

# Load environment variables
load_dotenv()

app = FastAPI(title="My Simple Blog", description="A personal blog built with FastAPI")

# Add session middleware for authentication
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "fallback-secret-key"))

# Admin password from .env
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

# --- GCS Configuration ---
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "blog-posts-gazerah")
# IMPORTANT: Replace with the actual path to your service account key file.
# This file grants permissions to write to GCS. Keep it secure!
GCS_SERVICE_ACCOUNT_KEY_PATH = os.getenv("GCS_SERVICE_ACCOUNT_KEY_PATH", "../credentials.json") 

storage_client = storage.Client.from_service_account_json(GCS_SERVICE_ACCOUNT_KEY_PATH)
bucket = storage_client.bucket(GCS_BUCKET_NAME)

# Remove StaticFiles mount as we'll be serving from GCS
# app.mount("/static", StaticFiles(directory="files"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# --- Blog Post Storage ---
POSTS_FILE = Path("blog_posts.json")

# Data models
class MediaItem(BaseModel):
    type: str  # 'image' or 'video'
    url: str

class BlogPost(BaseModel):
    id: int
    title: str
    date: str
    description: str
    media: List[MediaItem]

def load_posts() -> List[BlogPost]:
    if POSTS_FILE.exists():
        with open(POSTS_FILE, "r") as f:
            # Convert raw dicts to BlogPost objects
            return [BlogPost(**post) for post in json.load(f)]
    return []

def save_posts(posts: List[BlogPost]):
    with open(POSTS_FILE, "w") as f:
        # Convert BlogPost objects to dictionaries for JSON serialization
        json.dump([post.model_dump() for post in posts], f, indent=4)

def get_gcs_url(object_name: str) -> str:
    """Generates a public URL for a GCS object."""
    return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{object_name}"

def upload_to_gcs(source_file_path: Path, destination_blob_name: str):
    """Uploads a file to the GCS bucket."""
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_path)
    print(f"File {source_file_path} uploaded to {destination_blob_name}.")

def process_media(input_path: Path, quality: str, post_date_folder: str) -> Tuple[str, str]:
    """
    Converts the input media file (video or image) for web optimization and uploads to GCS.

    Args:
        input_path: Path to the original media file.
        quality: A string indicating the desired quality ('high', 'medium', 'low').
        post_date_folder: The date folder (e.g., '24-06-2025') for GCS organization.

    Returns:
        A tuple: (public GCS URL of the converted file, file_type_string)
    """
    ext = input_path.suffix.lower()
    
    # 1. Determine Conversion Parameters based on quality
    crf_map = {'high': '20', 'medium': '23', 'low': '28'}
    crf_value = crf_map.get(quality, '23')
    webp_quality_map = {'high': '85', 'medium': '75', 'low': '60'}
    webp_quality = webp_quality_map.get(quality, '75')

    # Use a temporary directory for the output file before uploading to GCS
    with TemporaryDirectory() as output_temp_dir_str:
        output_temp_dir = Path(output_temp_dir_str)
        
        if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
            # VIDEO CONVERSION (H.264/MP4)
            optimized_filename = f"optimized_{input_path.stem}.mp4"
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
                str(output_temp_dir / optimized_filename)
            ]
            
        elif ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.webp']:
            # IMAGE CONVERSION (WebP)
            optimized_filename = f"optimized_{input_path.stem}.webp"
            file_type = "Image (WebP)"
            command = [
                'ffmpeg',
                '-i', str(input_path),
                '-q:v', webp_quality, # WebP quality setting
                '-compression_level', '4', # Balance between speed and size (0=fastest, 6=slowest/smallest)
                '-y', 
                str(output_temp_dir / optimized_filename)
            ]
        else:
            raise RuntimeError(f"Unsupported file type: {ext}. Only common video and image types are supported.")

        optimized_output_path = output_temp_dir / optimized_filename
    
        print(f"Running command ({file_type}): {' '.join(command)}")
        
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error for {input_path.name}: {e.stderr}")
            error_detail = e.stderr.split('Error')[1].strip().split('\n')[0] if 'Error' in e.stderr else e.stderr.strip()
            raise RuntimeError(f"Conversion failed for {input_path.name}. Detail: {error_detail}")
        except FileNotFoundError:
            raise RuntimeError("FFmpeg command not found. Please install ffmpeg on your server.")
            
        # Upload the optimized file to GCS
        gcs_object_name = f"posts/{post_date_folder}/{optimized_filename}"
        upload_to_gcs(optimized_output_path, gcs_object_name)
        
        return get_gcs_url(gcs_object_name), file_type
    
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main blog page"""
    posts = load_posts()
    return templates.TemplateResponse("index.html", {"request": request, "posts": posts})

@app.get("/api/posts", response_model=List[BlogPost])
async def get_posts():
    """API endpoint to get all blog posts"""
    return load_posts()

@app.get("/api/posts/{post_id}", response_model=BlogPost)
async def get_post(post_id: int):
    """API endpoint to get a specific blog post"""
    posts = load_posts()
    for post in posts:
        if post.id == post_id:
            return post
    return {"error": "Post not found"}

def delete_gcs_object(object_name: str):
    """Deletes a single object from GCS bucket."""
    try:
        blob = bucket.blob(object_name)
        blob.delete()
        print(f"Deleted {object_name} from GCS")
    except Exception as e:
        print(f"Error deleting {object_name}: {e}")

def delete_post_media(media_urls: List[str]):
    """Deletes all media files for a post from GCS."""
    for url in media_urls:
        # Extract object name from URL
        # URL format: https://storage.googleapis.com/bucket-name/object-name
        try:
            object_name = url.split(f"storage.googleapis.com/{GCS_BUCKET_NAME}/")[1]
            delete_gcs_object(object_name)
        except Exception as e:
            print(f"Error parsing/deleting URL {url}: {e}")

def is_authenticated(request: Request) -> bool:
    """Check if user is authenticated"""
    return request.session.get("admin_authenticated", False)

def require_auth(request: Request):
    """Require authentication, redirect to login if not authenticated"""
    from fastapi.responses import RedirectResponse
    if not is_authenticated(request):
        return RedirectResponse(url="/admin/login")
    return None

# --- Authentication Routes ---
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page"""
    return templates.TemplateResponse("admin/login.html", {"request": request})

@app.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)):
    """Handle admin login"""
    from fastapi.responses import RedirectResponse
    if password == ADMIN_PASSWORD:
        request.session["admin_authenticated"] = True
        return RedirectResponse(url="/admin", status_code=303)
    else:
        return templates.TemplateResponse("admin/login.html", {
            "request": request,
            "error": "Invalid password"
        })

@app.get("/admin/logout")
async def admin_logout(request: Request):
    """Logout admin"""
    from fastapi.responses import RedirectResponse
    request.session.clear()
    return RedirectResponse(url="/")

# --- Admin Routes for Post Management ---
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Main admin dashboard"""
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    
    posts = load_posts()
    # Count media files in GCS
    media_count = sum(1 for blob in bucket.list_blobs(prefix="posts/") if not blob.name.endswith('/'))
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "posts": posts,
        "media_count": media_count
    })

@app.get("/admin/posts", response_class=HTMLResponse)
async def admin_posts_page(request: Request):
    """Redirect to main admin dashboard"""
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/admin")

@app.get("/admin/posts/new", response_class=HTMLResponse)
async def admin_create_post_page(request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    return templates.TemplateResponse("admin/edit_post.html", {
        "request": request,
        "post": None,
        "now": datetime.now()
    })

@app.post("/admin/posts/new")
async def admin_create_post(
    request: Request,
    title: str = Form(...),
    date: str = Form(...),
    description: str = Form(...),
    date_folder: str = Form(...),
    quality: str = Form("medium"),
    files: List[UploadFile] = File(None)
):
    """Create a new post with media uploads"""
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    from fastapi.responses import RedirectResponse
    
    # Process uploaded media
    media_items = []
    if files and files[0].filename:  # Check if files were actually uploaded
        with TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            
            for file in files:
                try:
                    input_file_path = temp_dir / file.filename
                    with open(input_file_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)
                    
                    gcs_url, file_type = process_media(input_file_path, quality, date_folder)
                    media_type = "video" if "video" in file_type.lower() else "image"
                    media_items.append(MediaItem(type=media_type, url=gcs_url))
                except Exception as e:
                    print(f"Error processing {file.filename}: {e}")
                    continue
    
    # Create the post
    posts = load_posts()
    next_id = max([p.id for p in posts]) + 1 if posts else 1
    new_post = BlogPost(id=next_id, title=title, date=date, description=description, media=media_items)
    posts.append(new_post)
    save_posts(posts)
    
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/posts/edit/{post_id}", response_class=HTMLResponse)
async def admin_edit_post_page(post_id: int, request: Request):
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    posts = load_posts()
    post = next((p for p in posts if p.id == post_id), None)
    if not post:
        return HTMLResponse("Post not found", status_code=404)
    return templates.TemplateResponse("admin/edit_post.html", {
        "request": request,
        "post": post,
        "now": datetime.now()
    })

@app.post("/admin/posts/edit/{post_id}")
async def admin_update_post(
    post_id: int,
    request: Request,
    title: str = Form(...),
    date: str = Form(...),
    description: str = Form(...),
    date_folder: str = Form(...),
    quality: str = Form("medium"),
    existing_media_urls: List[str] = Form(None),
    existing_media_types: List[str] = Form(None),
    files: List[UploadFile] = File(None)
):
    """Update a post, handling media additions and deletions"""
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    from fastapi.responses import RedirectResponse
    
    posts = load_posts()
    post_index = next((i for i, p in enumerate(posts) if p.id == post_id), None)
    
    if post_index is None:
        return HTMLResponse("Post not found", status_code=404)
    
    old_post = posts[post_index]
    
    # Determine which media to delete (old media not in existing_media_urls)
    old_media_urls = [m.url for m in old_post.media]
    existing_media_urls = existing_media_urls or []
    media_to_delete = [url for url in old_media_urls if url not in existing_media_urls]
    
    # Delete removed media from GCS
    if media_to_delete:
        delete_post_media(media_to_delete)
    
    # Keep existing media in the NEW ORDER from the form
    media_items = []
    if existing_media_urls and existing_media_types:
        for url, media_type in zip(existing_media_urls, existing_media_types):
            media_items.append(MediaItem(type=media_type, url=url))
    
    # Process newly uploaded media (these go at the end)
    if files and files[0].filename:
        with TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            
            for file in files:
                try:
                    input_file_path = temp_dir / file.filename
                    with open(input_file_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)
                    
                    gcs_url, file_type = process_media(input_file_path, quality, date_folder)
                    media_type = "video" if "video" in file_type.lower() else "image"
                    media_items.append(MediaItem(type=media_type, url=gcs_url))
                except Exception as e:
                    print(f"Error processing {file.filename}: {e}")
                    continue
    
    # Update the post
    updated_post = BlogPost(id=post_id, title=title, date=date, description=description, media=media_items)
    posts[post_index] = updated_post
    save_posts(posts)
    
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/posts/delete/{post_id}", response_class=HTMLResponse)
async def admin_delete_post(post_id: int, request: Request):
    """Delete a post and all its media from GCS"""
    auth_redirect = require_auth(request)
    if auth_redirect:
        return auth_redirect
    posts = load_posts()
    post = next((p for p in posts if p.id == post_id), None)
    
    if not post:
        return HTMLResponse("Post not found", status_code=404)
    
    # Delete all media for this post from GCS
    media_urls = [m.url for m in post.media]
    if media_urls:
        delete_post_media(media_urls)
    
    # Remove post from list
    posts = [p for p in posts if p.id != post_id]
    save_posts(posts)
    
    return HTMLResponse(status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)