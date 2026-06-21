# yt-script-extractor

Pull a YouTube video's transcript with one command. By default you get the script
in the **original language** of the captions. An **auto-translated**
version is available when you ask for it. Outputs both a `.txt`
log and a `.docx` Word file, with per-line timestamps.

Works for any video with captions, including auto-generated ones - Chinese,
English, Spanish, etc.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Default: original transcript, analysis, Notion, txt + docx
python main.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Also save a Chinese auto-translation when YouTube offers one
python main.py "https://youtu.be/dQw4w9WgXcQ" --translate --lang zh-Hans

# Save local transcript files only
python main.py "<url>" --no-analyze --no-notion

# Plain text only, no timestamps
python main.py "<url>" --format txt --no-timestamps

# Pass a bare 11-character video id
python main.py dQw4w9WgXcQ
```

Files land in `./scripts/` by default (override with `--out <dir>`):

```
scripts/
  dQw4w9WgXcQ_original_es.txt    # original (Spanish in this example)
  dQw4w9WgXcQ_original_es.docx
  dQw4w9WgXcQ_zh-Hans_zh-Hans.txt  # optional Chinese translation
  dQw4w9WgXcQ_zh-Hans_zh-Hans.docx
```

## Options

| Flag | Default | What it does |
| --- | --- | --- |
| `--lang`, `-l` | `zh-Hans` | Target language when `--translate` is used (ISO code: `en`, `zh-Hans`, `es`, `fr`, `ja`, ...) |
| `--out`, `-o` | `scripts` | Output directory |
| `--format`, `-f` | `txt,docx` | Comma-separated: `txt`, `docx`, or both |
| `--no-timestamps` | off | Strip per-line timestamps |
| `--translate` | off | Also save a YouTube auto-translated transcript |
| `--skip-translation` | on | Save only the original transcript |
| `--no-analyze` | off | Skip transcript analysis |
| `--no-notion` | off | Skip Notion publishing |

## Daily Codex Mobile prompt

Send:

```
help me with this video: <link>
```

The default run analyzes the transcript and publishes the result to Notion.
Local transcript and analysis files are still saved under `./scripts/`.

## VideoBrief iOS app

This repo now includes a native SwiftUI app under `ios/VideoBrief`.

The app provides:

- A searchable video library with YouTube thumbnails
- Summary, key points, deep dive, AI comments, and full transcript
- Favorites and read/unread state
- Offline local cache on the iPhone
- A paste-YouTube-link flow that starts extraction on the Mac
- Dual persistence: SQLite for the app and Notion for the existing knowledge base

### Start the API

```bash
./run_api.sh
```

The API listens on port `8765`. The iOS Simulator uses:

```text
http://127.0.0.1:8765
```

For a physical iPhone, the app first discovers the Mac's current private
Cloudflare Tunnel URL from a secret GitHub Gist. This works over Wi-Fi, 5G,
and remote networks as long as the Mac is powered on and connected.

The app retains these local addresses as fallbacks:

```text
http://Sens-Mac-mini.ad.analog.com:8765
http://10.20.16.23:8765
http://Sens-Mac-mini.local:8765
```

The tunnel starts automatically after Mac login and republishes its URL if it
changes. Remote API requests require the private token embedded in the
TestFlight build; the token is stored in the Mac login keychain and never
committed to Git.

Copy a YouTube link before opening the add-video screen and the app fills it
from the clipboard automatically.

### Build the iOS app

```bash
cd ios
xcodegen generate
open VideoBrief.xcodeproj
```

Choose your Apple development team in Xcode, connect an iPhone with Developer
Mode enabled, select the iPhone, then Run. The API is already configured as a
Mac `launchd` service and starts automatically after login.

### API endpoints

```text
GET    /api/health
GET    /api/videos
GET    /api/videos/{video_id}
PATCH  /api/videos/{video_id}
POST   /api/videos/process
GET    /api/jobs/{job_id}
POST   /api/library/import
```

The canonical app library is stored in:

```text
data/video_library.sqlite3
```

## How it works

1. Resolve the URL (or bare id) to an 11-character video id.
2. Use [`youtube-transcript-api`](https://github.com/jdepoix/youtube-transcript-api)
   to list available caption tracks; prefer uploader-provided over
   auto-generated for the "original".
3. If `--translate` is used and `--lang` differs from the original, ask YouTube
   to auto-translate it (no third-party translation service needed).
4. Write `.txt` and/or `.docx` files with timestamps and a small header.

## Limitations

- Videos without captions use local Whisper transcription and take longer.
- Translation quality is whatever YouTube gives you (it's auto-translation).
- Some private/age-restricted/region-locked videos won't expose captions.
```
