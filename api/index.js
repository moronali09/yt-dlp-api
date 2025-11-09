const ytdl = require('ytdl-core');
const ytSearch = require('yt-search');
const ffmpegPath = require('ffmpeg-static');
const ffmpeg = require('fluent-ffmpeg');
ffmpeg.setFfmpegPath(ffmpegPath);
const { parse } = require('url');

function sanitizeFilename(name) {
  return (name || 'file').replace(/[^a-z0-9-_\.]/gi, '_').slice(0, 200);
}

module.exports = async (req, res) => {
  const proto = req.headers['x-forwarded-proto'] || 'https';
  const origin = `${proto}://${req.headers.host}`;
  const parsed = parse(req.url, true);
  const pathname = (parsed.pathname || '/').replace(/\/+$|^\/+/g, '/');
  const parts = pathname.replace(/^\/+/, '').split('/');
  if (parts[0] === 'api') parts.shift();
  const endpoint = (parts[0] || '').toLowerCase();
  const q = parsed.query || {};

  res.setHeader('Access-Control-Allow-Origin', '*');

  // Root: minimal website. If ?dl=<id|url>&format=mp3|mp4 provided -> redirect to stream endpoint
  if ((parsed.pathname || '/') === '/') {
    const dl = q.dl || q.link || q.v || q.videoID;
    const format = (q.format || 'mp3').toLowerCase();
    if (dl) {
      const encoded = encodeURIComponent(dl);
      const redirectTo = `${origin}/api/stream/${encoded}?format=${encodeURIComponent(format)}`;
      res.writeHead(302, { Location: redirectTo });
      return res.end();
    }
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    return res.end('Usage: visit this URL with query parameters. Example:
https://'+req.headers.host+'/?dl=<youtube-url-or-id>&format=mp3
Or use API endpoints under /api/.');
  }

  if (endpoint === '' || endpoint === 'meta') {
    return res.json({ api: `${origin}/api` });
  }

  if (endpoint === 'ytfullsearch') {
    const songName = q.songName || q.q || q.song || '';
    if (!songName) return res.status(400).json([]);
    try {
      const r = await ytSearch(songName);
      const videos = (r && r.videos) || [];
      const results = videos.slice(0, 10).map(v => ({
        id: v.videoId || v.video_id || v.id,
        title: v.title,
        thumbnail: v.thumbnail,
        time: v.timestamp,
        channel: { name: v.author && v.author.name }
      }));
      return res.json(results);
    } catch (e) {
      return res.status(500).json([]);
    }
  }

  if (endpoint === 'ytfullinfo') {
    const videoID = q.videoID || q.id || parts[1] || q.link;
    if (!videoID) return res.status(400).json({ error: 'videoID required' });
    try {
      const url = videoID.startsWith('http') ? videoID : `https://www.youtube.com/watch?v=${videoID}`;
      const info = await ytdl.getInfo(url);
      const out = {
        id: info.videoDetails.videoId || videoID,
        title: info.videoDetails.title,
        thumbnail: (info.videoDetails.thumbnails || []).slice(-1)[0] && (info.videoDetails.thumbnails || []).slice(-1)[0].url,
        time: info.videoDetails.lengthSeconds,
        channel: { name: info.videoDetails.author && info.videoDetails.author.name },
        formats: info.formats
      };
      return res.json(out);
    } catch (e) {
      return res.status(500).json({ id: videoID, title: 'Unknown Title' });
    }
  }

  if (endpoint === 'ytdl3' || endpoint === 'ytdl') {
    const link = q.link || q.videoID || q.id || parts[1];
    const format = (q.format || 'mp4').replace(/[^a-z0-9]/gi, '').toLowerCase();
    if (!link) return res.status(400).json({ error: 'link required' });
    const downloadLink = `${origin}/api/stream/${encodeURIComponent(link)}?format=${format}`;
    return res.json({ downloadLink, format, videoID: link });
  }

  if (endpoint === 'stream') {
    const videoIDraw = parts[1] || q.videoID || q.id || q.link;
    if (!videoIDraw) return res.status(400).send('video id required');
    const format = (q.format || 'mp4').toLowerCase();
    const videoID = decodeURIComponent(videoIDraw);
    const url = videoID.startsWith('http') ? videoID : `https://www.youtube.com/watch?v=${videoID}`;

    if (format === 'mp3') {
      res.setHeader('Content-Type', 'audio/mpeg');
      res.setHeader('Content-Disposition', `attachment; filename="${sanitizeFilename(videoID)}.mp3"`);
      try {
        const audioStream = ytdl(url, { quality: 'highestaudio' });
        const proc = ffmpeg(audioStream).format('mp3').audioBitrate(128);
        proc.on('error', () => {
          try { res.end(); } catch (e) {}
        });
        proc.pipe(res, { end: true });
      } catch (e) {
        res.status(500).end();
      }
      return;
    }

    // default -> stream video (mp4 or other requested format name, but ytdl provides best effort)
    res.setHeader('Content-Disposition', `attachment; filename="${sanitizeFilename(videoID)}.${format}"`);
    res.setHeader('Content-Type', 'application/octet-stream');
    try {
      const stream = ytdl(url, { quality: 'highestvideo' });
      stream.pipe(res);
    } catch (e) {
      res.status(500).end();
    }
    return;
  }

  return res.json({ ok: true, endpoints: ['/api/meta', '/api/ytFullSearch?songName=..', '/api/ytfullinfo?videoID=..', '/api/ytDl3?link=..&format=mp3|mp4', '/api/stream/<id>?format=mp3|mp4', '/?dl=<id|url>&format=mp3'] });
};
