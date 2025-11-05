
import { YtDlp } from 'ytdlp-nodejs';

const ytdlp = new YtDlp(); 

export default async function handler(req, res) {
  try {
    const url = (req.query.url || req.body?.url || '').toString();
    const mode = (req.query.mode || req.body?.mode || 'video').toString(); 
    if (!url) return res.status(400).send('Missing "url" query param');

    let info;
    try {
      info = await ytdlp.getInfoAsync(url, { flatPlaylist: true });
    } catch (e) {
      console.warn('getInfo failed:', e?.message || e);
    }
    const titleSafe = (info?.title || 'download').replace(/["<>:\\/|?*\x00-\x1F]/g, '_').slice(0,180);
    const wantAudioOnly = mode === 'audio';
    const formatArg = wantAudioOnly ? 'bestaudio' : 'best';

    const extHint = wantAudioOnly ? 'audio' : 'mp4';
    res.setHeader('Content-Disposition', `attachment; filename="${titleSafe}.${extHint}"`);
    res.setHeader('Content-Type', 'application/octet-stream');

    const ytdlpStream = ytdlp.stream(url, {
      format: formatArg,
      noPlaylist: true
    });

    await ytdlpStream.pipeAsync(res);

    if (!res.writableEnded) res.end();
  } catch (err) {
    console.error('Download error:', err);
    if (!res.headersSent) res.status(500).send('Server error: ' + (err.message || String(err)));
    else try { res.end(); } catch (e) {}
  }
}
