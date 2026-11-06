# SoundCloud Archive

A small local web app for exporting **publicly available** SoundCloud likes and playlists as JSON. It never asks for login credentials, cookies, or tokens. Data is saved on your computer.

## Run it (Windows)

1. Download this repository as a ZIP from the green **Code** button and choose **Download ZIP**. Extract the ZIP.
2. Open the extracted folder in File Explorer. Click the address bar, type `cmd`, and press Enter.
3. Install Python 3.10+ if needed, then run:

   ```bat
   py -m pip install -r requirements.txt
   py app.py
   ```

4. Open **http://127.0.0.1:8765** in Chrome or another browser. Paste a public profile URL and click **Export data**.
5. Download `likes.json`, `playlists.json`, and `report.json` from the page. Files are stored in the `soundcloud-export` folder beside the app.

## macOS/Linux

```sh
python3 -m pip install -r requirements.txt
python3 app.py
```

Then open http://127.0.0.1:8765.

## Pagination, checkpoints, and limitations

The app uses yt-dlp's SoundCloud public collection extractor and does not set a page/entry cap; it consumes the collection iterator through completion. It checkpoints every 25 new entries and at completion. If interrupted, starting the same profile again resumes by refetching from the beginning and de-duplicating IDs against the checkpoint. Re-fetch restarts the categories.

- Likes and playlists are exported only if SoundCloud makes them public and the extractor can retrieve them.
- Followings are explicitly marked **unsupported**: the current supported extractor does not expose a followings collection. This app does not guess private or undocumented endpoints.
- A collection is marked complete only after its iterator ends normally. Check `report.json` and the counts; no tool can guarantee data SoundCloud did not return.
- This is an exporter, not a migration importer. It does not automate likes or follows, evade bot detection, or interact with destination accounts. SoundCloud's supported public interfaces do not provide a reliable bulk migration pathway for those actions.
- The server binds to `127.0.0.1` only. Keep the app local; don't expose it to a public network.
