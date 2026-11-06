# soundcloud-migration-tool

A generic, resumable SoundCloud migration CLI for exporting and importing likes, followings, and playlists.

Important: This tool does not log into your SoundCloud account for you. It expects you to provide your own SoundCloud client ID / access token and source/destination profile URLs when you run it.

This project intentionally slows requests, saves checkpoints, and logs failed items instead of firing high-volume automation at SoundCloud.

## Features

- Accept a source URL and a target URL at runtime
- Export likes, followings, and playlists to local JSON
- Save checkpoints after each page so exporting can resume
- Back off on 429s, timeouts, and transient server errors
- Write failed items to a final error log for later retry
- Optionally perform import to the target account in a controlled, slow mode

## Setup

```bash
npm install
cp .env.example .env
```

## Required environment variables

```env
SOUNDCLOUD_SOURCE_URL=https://soundcloud.com/your-source
SOUNDCLOUD_TARGET_URL=https://soundcloud.com/your-target
SOUNDCLOUD_CLIENT_ID=your_soundcloud_client_id
SOUNDCLOUD_SOURCE_TOKEN=oauth_access_token_for_source
SOUNDCLOUD_TARGET_TOKEN=oauth_access_token_for_target
OUTPUT_DIR=exports
STATE_FILE=state.json
FAILED_FILE=failed.json
DRY_RUN=false
```

## Run

```bash
npm run dev
```

## Dry run

```bash
DRY_RUN=true npm run dev
```

## Notes

- SoundCloud requires valid access tokens and may deny or restrict bulk actions.
- If the source is public but the likes/followings/playlists are behind authenticated endpoints, token-based access is required.
- A resilient tool must not assume all actions succeed; it should checkpoint and record failures.
