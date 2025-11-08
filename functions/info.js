const ytdl = require('ytdl-core');

exports.handler = async (event) => {
  const url = event.queryStringParameters && event.queryStringParameters.url;
  if (!url) return { statusCode: 400, body: 'missing url query param' };

  try {
    const info = await ytdl.getInfo(url);
    const formats = info.formats.map(f => ({
      itag: f.itag,
      mimeType: f.mimeType,
      quality: f.qualityLabel || f.quality,
      contentLength: f.contentLength,
      url: f.url
    }));
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: info.videoDetails.title, formats })
    };
  } catch (err) {
    return { statusCode: 500, body: String(err) };
  }
};
