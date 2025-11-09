const ytdl = require('ytdl-core');
const ytSearch = require('yt-search');
const ffmpegPath = require('ffmpeg-static');
const ffmpeg = require('fluent-ffmpeg');
ffmpeg.setFfmpegPath(ffmpegPath);
const { parse } = require('url');

module.exports = async (req, res) => {
  const proto = req.headers['x-forwarded-proto'] || 'https';
  const origin = `${proto}://${req.headers.host}`;
  const parsed = parse(req.url, true);
  const pathname = parsed.pathname || '/';
  const parts = pathname.replace(/^\/+/, '').split('/');
  if (parts[0] === 'api') parts.shift();
  const endpoint = (parts[0] || 'meta').toLowerCase();
  const q = parsed.query || {};

  res.setHeader('Access-Control-Allow-Origin', '*');

  if (endpoint === '' || endpoint === 'meta') {
    return res.json({ api: `${origin}/api` });
  }

  if (endpoint === 'ytfullsearch' || endpoint === 'ytfullsearch' || endpoint === 'ytfullsearch') {
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

  if (endpoint === 'ytfullinfo' || endpoint === 'ytfullinfo') {
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

  if (endpoint === 'ytdl3' || endpoint === 'ytdl' || endpoint === 'ytdl3') {
    const link = q.link || q.videoID || q.id || parts[1];
    const format = (q.format || 'mp4').replace(/[^a-z0-9]/gi, '').toLowerCase();
    if (!link) return res.status(400).json({ error: 'link required' });
    const downloadLink = `${origin}/api/stream/${encodeURIComponent(link)}?format=${format}`;
    return res.json({ downloadLink, format, videoID: link });
  }

  if (endpoint === 'stream') {
    const videoID = parts[1] || q.videoID || q.id || q.link;
    const format = (q.format || 'mp4').toLowerCase();
    if (!videoID) return res.status(400).send('video id required');
    const url = videoID.startsWith('http') ? videoID : `https://www.youtube.com/watch?v=${videoID}`;

    if (format === 'mp3') {
      res.setHeader('Content-Type', 'audio/mpeg');
      res.setHeader('Content-Disposition', `attachment; filename="${videoID}.mp3"`);
      try {
        const audioStream = ytdl(url, { quality: 'highestaudio' });
        const proc = ffmpeg(audioStream).format('mp3').audioBitrate(128);
        proc.on('error', () => res.end());
        proc.pipe(res, { end: true });
      } catch (e) {
        res.status(500).end();
      }
      return;
    }

    res.setHeader('Content-Disposition', `attachment; filename="${videoID}.${format}"`);
    res.setHeader('Content-Type', 'application/octet-stream');
    try {
      const stream = ytdl(url, { quality: 'highestvideo' });
      stream.pipe(res);
    } catch (e) {
      res.status(500).end();
    }
    return;
  }

  return res.json({ ok: true, endpoints: ['/api/meta', '/api/ytFullSearch?songName=..', '/api/ytfullinfo?videoID=..', '/api/ytDl3?link=..&format=mp3|mp4', '/api/stream/<id>?format=mp3|mp4'] });
};
    
