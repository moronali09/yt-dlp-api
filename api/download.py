from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import os, shutil, tempfile, cgi, base64
from yt_dlp import YoutubeDL
import shutil as _shutil

HTML_TEMPLATE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>yt-dlp downloader</title>
  <style>
    body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:24px}
    .card{max-width:720px;margin:0 auto;padding:18px;border-radius:12px;box-shadow:0 6px 22px rgba(0,0,0,.08)}
    label{display:block;margin:10px 0 6px}
    input[type=text],select{width:100%;padding:8px;border-radius:6px;border:1px solid #ddd}
    button{margin-top:12px;padding:10px 14px;border-radius:8px;border:0;background:#111;color:#fff}
    .note{font-size:13px;color:#666;margin-top:10px}
    .error{color:#c00}
  </style>
</head>
<body>
  <div class="card">
    <h2>yt-dlp downloader (simple UI)</h2>
    <form id="dlform">
      <label for="url">Video URL</label>
      <input id="url" name="url" type="text" placeholder="https://youtu.be/..." required />

      <label for="type">Download type</label>
      <select id="type" name="type">
        <option value="mp4">MP4 (360p)</option>
        <option value="mp3">MP3 (best audio)</option>
      </select>

      <label for="cookies">Optional: upload cookies.txt (for age-restricted / sign-in videos)</label>
      <input id="cookies" name="cookies" type="file" accept=".txt" />

      <button id="go" type="submit">Search & Download</button>
      <div id="status" class="note"></div>
      <div class="note">Server ffmpeg available: <strong>{ffmpeg}</strong></div>
      <div class="note">Privacy: uploaded cookies are used only for this request and not stored persistently. Use at your own risk.</div>
    </form>
  </div>

<script>
const form = document.getElementById('dlform');
const status = document.getElementById('status');
form.addEventListener('submit', async (e)=>{
  e.preventDefault();
  status.textContent = 'Starting...';
  const url = document.getElementById('url').value.trim();
  const type = document.getElementById('type').value;
  const cookiesInput = document.getElementById('cookies');

  if (!url) { status.textContent = 'Please enter a URL'; return; }

  // If user uploaded cookies file, we must POST with FormData (so server receives cookiefile)
  if (cookiesInput.files && cookiesInput.files.length > 0) {
    status.textContent = 'Uploading cookies and requesting download... (may take some time)';
    const fd = new FormData();
    fd.append('url', url);
    fd.append('type', type);
    fd.append('cookies', cookiesInput.files[0]);

    try {
      const res = await fetch(location.pathname, { method: 'POST', body: fd });
      if (!res.ok) {
        const t = await res.text();
        status.innerHTML = '<span class="error">Error: ' + res.status + ' - ' + t + '</span>';
        return;
      }
      const blob = await res.blob();
      // get suggested filename from header
      let filename = 'download';
      const cd = res.headers.get('Content-Disposition');
      if (cd) {
        const m = cd.match(/filename=\"?([^\";]+)\"?/);
        if (m) filename = m[1];
      }
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      status.textContent = 'Download started';
    } catch (err) {
      status.innerHTML = '<span class="error">Fetch error: '+err+'</span>';
    }

  } else {
    // no cookies uploaded — simple GET navigation will trigger browser download
    const params = new URLSearchParams({ url: url, type: type });
    status.textContent = 'Redirecting to download (GET)...';
    // navigate (the server will stream the file back)
    window.location = location.pathname + '?' + params.toString();
  }
});
</script>
</body>
</html>
"""

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

    def _do_download(self, url, typ, cookiefile_path=None):
        work = tempfile.mkdtemp(prefix="ydl-")
        try:
            if typ == 'mp3':
                if not _shutil.which('ffmpeg'):
                    return (500, 'mp3 conversion requires ffmpeg in PATH on the server', None)
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(work, '%(id)s.%(ext)s'),
                    'postprocessors': [{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'320'}],
                    'quiet': True, 'no_warnings': True
                }
                content_type = 'audio/mpeg'
            else:
                ydl_opts = {
                    'format': 'bestvideo[height<=360]+bestaudio/best/best[height<=360]',
                    'outtmpl': os.path.join(work, '%(id)s.%(ext)s'),
                    'merge_output_format': 'mp4',
                    'quiet': True, 'no_warnings': True
                }
                content_type = 'video/mp4'

            if cookiefile_path:
                ydl_opts['cookiefile'] = cookiefile_path

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(unquote(url), download=True)

            vid_id = info.get('id')
            fp = None
            for f in os.listdir(work):
                if f.startswith(vid_id + '.') or f.startswith(vid_id + '-'):
                    fp = os.path.join(work, f)
                    break
            if not fp:
                files = [os.path.join(work, f) for f in os.listdir(work)]
                files.sort(key=os.path.getmtime, reverse=True)
                fp = files[0] if files else None
            if not fp or not os.path.exists(fp):
                return (500, 'download failed (no file)', None)

            return (200, content_type, fp)
        except Exception as e:
            return (500, 'yt-dlp error: ' + str(e), None)
        finally:
            # do NOT remove work here because caller will stream file and then cleanup
            pass

    def do_POST(self):
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD':'POST'})
        url = form.getvalue('url')
        typ = (form.getvalue('type') or 'mp4').lower()
        cookies_field = form['cookies'] if 'cookies' in form else None

        if not url:
            return self._respond(400, 'missing url')

        work = tempfile.mkdtemp(prefix='ydl-')
        cookiefile = None
        try:
            if cookies_field:
                if getattr(cookies_field, 'file', None):
                    cookiefile = os.path.join(work, 'cookies.txt')
                    with open(cookiefile, 'wb') as fh:
                        fh.write(cookies_field.file.read())
                else:
                    cookiefile = os.path.join(work, 'cookies.txt')
                    with open(cookiefile, 'wb') as fh:
                        fh.write(cookies_field.value.encode())

            status, content_or_msg, fp = self._do_download(url, typ, cookiefile)
            if status != 200:
                return self._respond(status, content_or_msg)

            # stream file
            self.send_response(200)
            self.send_header('Content-Type', content_or_msg)
            self.send_header('Content-Length', str(os.path.getsize(fp)))
            self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(fp)}"')
            self.end_headers()
            with open(fp, 'rb') as fh:
                shutil.copyfileobj(fh, self.wfile)
        except Exception as e:
            return self._respond(500, 'yt-dlp error: ' + str(e))
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        url = q.get('url', [None])[0]
        typ = q.get('type', ['mp4'])[0].lower()
        cookies_param = q.get('cookies', [None])[0]

        # If no URL provided, render the simple HTML UI
        if not url:
            ffmpeg_available = 'yes' if _shutil.which('ffmpeg') else 'no'
            html = HTML_TEMPLATE.format(ffmpeg=ffmpeg_available)
            return self._respond(200, html, {'Content-Type': 'text/html; charset=utf-8'})

        work = tempfile.mkdtemp(prefix='ydl-')
        cookiefile = None
        try:
            if cookies_param:
                # try base64 decode, else raw
                try:
                    b = base64.b64decode(cookies_param)
                    cookiefile = os.path.join(work, 'cookies.txt')
                    with open(cookiefile, 'wb') as fh:
                        fh.write(b)
                except Exception:
                    cookiefile = os.path.join(work, 'cookies.txt')
                    with open(cookiefile, 'w') as fh:
                        fh.write(cookies_param)

            status, content_or_msg, fp = self._do_download(url, typ, cookiefile)
            if status != 200:
                return self._respond(status, content_or_msg)

            self.send_response(200)
            self.send_header('Content-Type', content_or_msg)
            self.send_header('Content-Length', str(os.path.getsize(fp)))
            self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(fp)}"')
            self.end_headers()
            with open(fp, 'rb') as fh:
                shutil.copyfileobj(fh, self.wfile)
        except Exception as e:
            return self._respond(500, 'yt-dlp error: ' + str(e))
        finally:
            shutil.rmtree(work, ignore_errors=True)
