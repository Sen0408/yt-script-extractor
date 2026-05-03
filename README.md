# yt-script-extractor

Pull a YouTube video's transcript with one command. You always get the script
in the **original language** of the captions, plus an **auto-translated**
version in your default language (English by default). Outputs both a `.txt`
log and a `.docx` Word file, with per-line timestamps.

Works for any video with captions, including auto-generated ones - Chinese,
English, Spanish, etc.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Default: original transcript + English translation, txt + docx
python main.py "<https://www.youtube.com/watch?v=dQw4w9WgXcQ>"

# Translate to Chinese instead
python main.py "<https://youtu.be/dQw4w9WgXcQ>" --lang zh-Hans

# Only the original, no translation
python main.py "<url>" --skip-translation

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
  dQw4w9WgXcQ_en_en.txt          # translated to English
  dQw4w9WgXcQ_en_en.docx
```

## Options

| Flag | Default | What it does |
| --- | --- | --- |
| `--lang`, `-l` | `en` | Target language for translation (ISO code: `en`, `zh-Hans`, `es`, `fr`, `ja`, ...) |
| `--out`, `-o` | `scripts` | Output directory |
| `--format`, `-f` | `txt,docx` | Comma-separated: `txt`, `docx`, or both |
| `--no-timestamps` | off | Strip per-line timestamps |
| `--skip-translation` | off | Save only the original transcript |

## How it works

1. Resolve the URL (or bare id) to an 11-character video id.
2. Use [`youtube-transcript-api`](<https://github.com/jdepoix/youtube-transcript-api>)
   to list available caption tracks; prefer uploader-provided over
   auto-generated for the "original".
3. If `--lang` differs from the original and the track is translatable, ask
   YouTube to auto-translate it (no third-party translation service needed).
4. Write `.txt` and/or `.docx` files with timestamps and a small header.

## Limitations

- If the video has captions disabled, nothing can be extracted.
- Translation quality is whatever YouTube gives you (it's auto-translation).
- Some private/age-restricted/region-locked videos won't expose captions.
```
