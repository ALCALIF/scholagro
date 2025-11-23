import os
import time
from typing import Optional

try:
    import cloudinary
    import cloudinary.uploader
except Exception:  # cloudinary may not be installed yet
    cloudinary = None


def _ensure_cloudinary_config():
    if not cloudinary:
        return False
    # Prefer CLOUDINARY_URL if set, otherwise configure with individual vars
    url = os.getenv("CLOUDINARY_URL")
    if url:
        cloudinary.config(cloudinary_url=url)
        return True
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if cloud_name and api_key and api_secret:
        cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True)
        return True
    return False


def upload_image(file_storage, folder: str = "scholagro") -> Optional[str]:
    """
    Upload a Werkzeug FileStorage to Cloudinary. Returns the secure URL or None.
    """
    if not file_storage:
        return None
    # If Cloudinary is configured, use it
    if _ensure_cloudinary_config():
        try:
            res = cloudinary.uploader.upload(file_storage, folder=folder, overwrite=False)
            return res.get("secure_url")
        except Exception:
            return None

    # Fallback: save the file locally under static/uploads/<folder>/ and return a static URL
    try:
        from werkzeug.utils import secure_filename
        import pathlib
        # ensure uploads dir exists relative to project root (assume cwd is project root)
        uploads_dir = pathlib.Path.cwd() / "static" / "uploads" / folder
        uploads_dir.mkdir(parents=True, exist_ok=True)
        filename = secure_filename(getattr(file_storage, 'filename', 'upload'))
        if not filename:
            filename = f"img_{int(time.time())}.jpg"
        dest = uploads_dir / filename
        # Save file_storage to destination
        file_storage.save(str(dest))
        # Return a URL path that Flask can serve from the `static` folder
        return f"/static/uploads/{folder}/{filename}"
    except Exception:
        return None


def cl_transform(url: Optional[str], width: int = None, height: int = None, crop: str = "fill") -> Optional[str]:
    """
    If URL is a Cloudinary URL, insert transformation for size/optimization.
    Else return URL untouched.
    """
    if not url:
        return url
    if "res.cloudinary.com" not in url:
        return url
    try:
        # Cloudinary URL format: https://res.cloudinary.com/<cloud>/image/upload/<opts>/<path>
        parts = url.split("/upload/")
        if len(parts) != 2:
            return url
        opts = ["f_auto", "q_auto"]
        if width:
            if height:
                opts.insert(0, f"c_{crop},w_{width},h_{height}")
            else:
                opts.insert(0, f"c_{crop},w_{width}")
        elif height:
            opts.insert(0, f"c_{crop},h_{height}")
        return parts[0] + "/upload/" + ",".join(opts) + "/" + parts[1]
    except Exception:
        return url
