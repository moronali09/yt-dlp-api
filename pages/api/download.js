// pages/api/download.js
import { YtDlp } from 'ytdlp-nodejs';

const ytdlp = new YtDlp();

const sanitize = (s = '') =>
  s.replace(/["<>:\\/|?*\x00-\x1F]/g, '_').trim().slice(0, 180) || 'download';

export default async function handler(req, res) {
  try {
    const url = (req.query.url || req.body?.url || '').toString();
    const mode = (req.query.mode || req.body?.mode || 'video').toString(); // 'video' or 'audio'
    if (!url) return res.status(400).json({ error: 'Missing "url" query param' });

    // metadata best-effort
    let info = null;
    try {
      info = await ytdlp.getInfoAsync(url, { noWarnings: true, noCallHome: true });
    } catch (e) {
      console.warn('ytdlp getInfo failed (continuing):', e?.message || e);
    }
    const titleSafe = sanitize(info?.title);

    // choose format and extension (no re-encoding here)
    const wantAudio = mode === 'audio';
    const format = wantAudio ? 'bestaudio' : 'bestvideo+bestaudio/best';
    const ext = wantAudio ? 'm4a' : 'mp4';

    // headers for download
    res.setHeader('Content-Disposition', `attachment; filename="${titleSafe}.${ext}"`);
    res.setHeader('Content-Type', 'application/octet-stream');

    // stream from yt-dlp into response
    const streamObj = ytdlp.stream(url, {
      format,
      noPlaylist: true
    });

    try {
      await streamObj.pipeAsync(res);
      if (!res.writableEnded) res.end();
    } catch (pipeErr) {
      console.error('Pipe error:', pipeErr);
      if (!res.headersSent) res.status(500).json({ error: 'Streaming failed', detail: String(pipeErr) });
      else try { res.end(); } catch (e) {}
    }
  } catch (err) {
    console.error('Handler error:', err);
    if (!res.headersSent) return res.status(500).json({ error: 'Server error', detail: String(err) });
    try { res.end(); } catch (e) {}
  }
}
