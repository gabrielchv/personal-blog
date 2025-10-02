from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List, Dict, Any
from pydantic import BaseModel
import os
from datetime import datetime

app = FastAPI(title="My Simple Blog", description="A personal blog built with FastAPI")

# Mount static files for media content
app.mount("/static", StaticFiles(directory="files"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

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

# Sample blog post data (you can later move this to a database)
BLOG_POSTS = [
    BlogPost(
        id=1,
        title="Visita da mamãe no litoral",
        date="24/06/2025",
        description='Minha mãe veio passar o final de semana na minha casa, e nesse dia fizemos uns lanches naturais, fomos na praia, porque ela queria entrar no mar, e mais tarde encontramos a Agatha e fomos no cinema assistir "Divertidamente 2".\n\nFico lisongeado de olhar pra minha mãe e namorada vivendo coisas gostosas e frutíferas comigo, duas pessoas lindas de corpo e alma.\n\nSão momentos como esse que fazem a vida valer a pena.',
        media=[
            MediaItem(type='image', url='/static/24-06-2025/mamae-ceu.webp'),
            MediaItem(type='image', url='/static/24-06-2025/os-tres.webp'),
            MediaItem(type='image', url='/static/24-06-2025/mamae-comidinha.webp'),
            MediaItem(type='image', url='/static/24-06-2025/mamae-descontraida.webp'),
            MediaItem(type='image', url='/static/24-06-2025/cinema.webp'),
        ]
    )
]

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main blog page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/posts", response_model=List[BlogPost])
async def get_posts():
    """API endpoint to get all blog posts"""
    return BLOG_POSTS

@app.get("/api/posts/{post_id}", response_model=BlogPost)
async def get_post(post_id: int):
    """API endpoint to get a specific blog post"""
    for post in BLOG_POSTS:
        if post.id == post_id:
            return post
    return {"error": "Post not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)