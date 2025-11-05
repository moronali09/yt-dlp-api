export default function Home() {
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: 24 }}>
      <h1>yt-dlp-api</h1>
      <p>API: <code>/api/download?url=VIDEO_URL&amp;mode=video</code></p>

      <form method="get" action="/api/download" style={{ marginTop: 16 }}>
        <input name="url" placeholder="Video URL" style={{ width: "60%", padding: 8 }} />
        <select name="mode" style={{ marginLeft: 8, padding: 8 }}>
          <option value="video">video</option>
          <option value="audio">audio</option>
        </select>
        <button type="submit" style={{ marginLeft: 8, padding: "8px 12px" }}>Download</button>
      </form>

      <hr style={{ margin: "24px 0" }} />
      <p>Health check: <a href="/api/hello">/api/hello</a></p>
    </main>
  );
}
