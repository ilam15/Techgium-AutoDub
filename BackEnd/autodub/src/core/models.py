from pydantic import BaseModel

class YouTubeInfoRequest(BaseModel):
    url: str

class YouTubeDownloadRequest(BaseModel):
    url: str
    quality: str = "720p" 
