const express = require('express');
const { spawn } = require('child_process');
const app = express();

app.get('/download', (req, res) => {
  const url = req.query.url;
  if (!url) return res.status(400).send('missing url');

  res.setHeader('Content-Disposition', 'attachment; filename="video.mp4"');

  const child = spawn('yt-dlp', ['-f', 'best[ext=mp4]/best', '-o', '-', url], { stdio: ['ignore', 'pipe', 'inherit'] });

  child.stdout.pipe(res);

  child.on('close', () => {
    try { res.end(); } catch (e) {}
  });

  child.on('error', (err) => {
    res.status(500).send('yt-dlp error: ' + String(err));
  });
});

app.listen(3000);
