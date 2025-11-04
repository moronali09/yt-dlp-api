from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import os, shutil, tempfile, cgi, base64
from yt_dlp import YoutubeDL

class handler(BaseHTTPRequestHandler):
    def _respond(self, code, body=b"", headers=None):
        self.send_response(code)
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        if body:
            if isinstance(body, str):
                body = body.encode()
            self.wfile.write(body)

    def do_POST(self):
        # parse multipart/form-data
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD':'POST'})
        url = form.getvalue("url")
        typ = (form.getvalue("type") or "mp4").lower()
        cookies_field = form['cookies'] if 'cookies' in form else None

        if not url:
            return self._respond(400, "missing url")

        work = tempfile.mkdtemp(prefix="ydl-")
        cookiefile = None
        try:
            if cookies_field:
                # if uploaded file
                if getattr(cookies_field, "file", None):
                    cookiefile = os.path.join(work, "cookies.txt")
                    with open(cookiefile, "wb") as fh:
                        fh.write(cookies_field.file.read())
                else:
                    # maybe raw text
                    cookiefile = os.path.join(work, "cookies.txt")
                    with open(cookiefile, "wb") as fh:
                        fh.write(cookies_field.value.encode())
            # prepare ydl opts
            if typ == "mp3":
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": os.path.join(work, "%(id)s.%(ext)s"),
                    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}],
                    "quiet": True, "no_warnings": True
                }
                content_type = "audio/mpeg"
            else:
                ydl_opts = {
                    "format": "bestvideo[height<=360]+bestaudio/best/best[height<=360]",
                    "outtmpl": os.path.join(work, "%(id)s.%(ext)s"),
                    "merge_output_format": "mp4",
                    "quiet": True, "no_warnings": True
                }
                content_type = "video/mp4"

            if cookiefile:
                ydl_opts["cookiefile"] = cookiefile

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(unquote(url), download=True)

            # find file
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
                return self._respond(500, "download failed (no file)")

            # stream file back
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(os.path.getsize(fp)))
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(fp)}"')
            self.end_headers()
            with open(fp, "rb") as fh:
                shutil.copyfileobj(fh, self.wfile)
        except Exception as e:
            return self._respond(500, "yt-dlp error: " + str(e))
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def do_GET(self):
        # keep your old GET behavior, but support cookie string param (base64 or raw)
        q = parse_qs(urlparse(self.path).query)
        url = q.get("url", [None])[0]
        typ = q.get("type", ["mp4"])[0].lower()
        cookies_param = q.get("cookies", [None])[0]

        if not url:
            return self._respond(400, "missing url")

        work = tempfile.mkdtemp(prefix="ydl-")
        cookiefile = None
        try:
            if cookies_param:
                # if base64 encoded, try decode, else write raw
                try:
                    b = base64.b64decode(cookies_param)
                    cookiefile = os.path.join(work, "cookies.txt")
                    with open(cookiefile, "wb") as fh:
                        fh.write(b)
                except Exception:
                    cookiefile = os.path.join(work, "cookies.txt")
                    with open(cookiefile, "w") as fh:
                        fh.write(cookies_param)

            if typ == "mp3":
                if not shutil.which("ffmpeg"):
                    return self._respond(500, "mp3 conversion requires ffmpeg in PATH on the server")
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": os.path.join(work, "%(id)s.%(ext)s"),
                    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}],
                    "quiet": True, "no_warnings": True
                }
                content_type = "audio/mpeg"
            else:
                ydl_opts = {
                    "format": "bestvideo[height<=360]+bestaudio/best/best[height<=360]",
                    "outtmpl": os.path.join(work, "%(id)s.%(ext)s"),
                    "merge_output_format": "mp4",
                    "quiet": True, "no_warnings": True
                }
                content_type = "video/mp4"

            if cookiefile:
                ydl_opts["cookiefile"] = cookiefile

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(unquote(url), download=True)

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
                return self._respond(500, "download failed (no file)")

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(os.path.getsize(fp)))
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(fp)}"')
            self.end_headers()
            with open(fp, "rb") as fh:
                shutil.copyfileobj(fh, self.wfile)
        except Exception as e:
            return self._respond(500, "yt-dlp error: " + str(e))
        finally:
            shutil.rmtree(work, ignore_errors=True)
