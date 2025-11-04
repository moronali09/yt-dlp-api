from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import os, shutil, tempfile
from yt_dlp import YoutubeDL
import shutil as _shutil

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        url = q.get("url", [None])[0]
        typ = q.get("type", ["mp4"])[0].lower()
        if not url:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"missing url query parameter")
            return

        work = tempfile.mkdtemp(prefix="ydl-")
        outtmpl = os.path.join(work, "%(id)s.%(ext)s")
        if typ == "mp3":
            if not _shutil.which("ffmpeg"):
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"mp3 conversion requires ffmpeg in PATH on the server")
                _shutil.rmtree(work, ignore_errors=True)
                return
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": outtmpl,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320"
                }],
                "quiet": True,
                "no_warnings": True
            }
            content_type = "audio/mpeg"
        else:
            ydl_opts = {
                "format": "bestvideo[height<=360]+bestaudio/best/best[height<=360]",
                "outtmpl": outtmpl,
                "merge_output_format": "mp4",
                "quiet": True,
                "no_warnings": True
            }
            content_type = "video/mp4"

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(unquote(url), download=True)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            msg = ("yt-dlp error: " + str(e)).encode()
            self.wfile.write(msg)
            _shutil.rmtree(work, ignore_errors=True)
            return

        vid_id = info.get("id")
        fp = None
        for f in os.listdir(work):
            if f.startswith(vid_id + ".") or f.startswith(vid_id + "-"):
                fp = os.path.join(work, f)
                break
        if not fp:
            files = [os.path.join(work, f) for f in os.listdir(work)]
            files.sort(key=os.path.getmtime, reverse=True)
            fp = files[0] if files else None
        if not fp or not os.path.exists(fp):
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"download failed (no file)")
            _shutil.rmtree(work, ignore_errors=True)
            return

        fname = os.path.basename(fp)
        try:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(os.path.getsize(fp)))
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.end_headers()
            with open(fp, "rb") as fh:
                shutil.copyfileobj(fh, self.wfile)
        finally:
            _shutil.rmtree(work, ignore_errors=True)
