# SoundCloud Public Data Exporter

A small local command-line program to export publicly visible SoundCloud likes and playlists to JSON. It does not ask for a SoundCloud login, password, cookie, or token. It uses yt-dlp's maintained SoundCloud extractor for public collection pagination.

## Quick start

You need Python 3.10 or newer.

**Windows:**

1. Download this repository as a ZIP from the green **Code** button and choose **Download ZIP**. Extract it.
2. Open the extracted folder, click the address bar in File Explorer, type `cmd`, and press Enter.
3. Run:

   ```bat
   py -m pip install -r requirements.txt
   py export_public.py
   ```

4. When prompted, paste the public profile URL, for example `https://soundcloud.com/artist`.

**macOS/Linux:**

```sh
python3 -m pip install -r requirements.txt
python3 export_public.py
```

Or pass the URL directly:

```sh
python export_public.py https://soundcloud.com/artist
```

The exporter writes `likes.json`, `playlists.json`, and `report.json` in a `soundcloud-export` folder. Choose a different destination with `-o folder-name`.

## Checkpoints and errors

Each category is written to a temporary file and atomically renamed only after yt-dlp finishes that collection. Re-running keeps completed category files and attempts any missing/failed category. To deliberately re-fetch completed categories, use `--retry`:

```sh
python export_public.py https://soundcloud.com/artist --retry
```

A successful JSON file contains the returned collection entries, metadata, item count, source profile URL, and export timestamp. `report.json` records per-category status and errors. If SoundCloud blocks a public page, the program reports that rather than claiming the export completed.

## Limitations

- This is an **exporter only**; it does not add likes, followings, or playlists to another account.
- It exports public likes and public playlists where SoundCloud and yt-dlp allow access. Private or unavailable content cannot be retrieved without authorization.
- The current yt-dlp SoundCloud extractor does not expose a profile followings collection. The report marks followings as unsupported instead of using undocumented endpoints.
- SoundCloud may change or throttle public access. No tool can guarantee a complete export if the service does not return all entries. Check the reported counts and warnings.
- This project does not download audio files.
