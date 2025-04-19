# Loom Video Downloader

No-BS Loom video downloader

## Setup

```bash
git clone https://github.com/h0n3yb/loom-downloader.git
cd loom-downloader
pip install -r requirements.txt
```

## Usage

### Download a single video

```bash
python dl.py --url https://www.loom.com/share/abcd1234 --out video.mp4
```

### Download multiple videos from a text file

```bash
python dl.py --list videos.txt --prefix loom-video --out ./downloads
```

## Command Line Arguments

| Argument | Short | Description |
|----------|-------|-------------|
| `--url`, | `-u` | URL of the video in the format https://www.loom.com/share/[ID] |
| `--list` | `-l` | Filename of the text file containing the list of URLs |
| `--prefix` | `-p` | Prefix for the output filenames when downloading from a list |
| `--out` | `-o` | Path to output the file or directory for output files when using --list |
| `--timeout` | `-t` | Timeout in milliseconds to wait between downloads (default: 5000) |
| `--help` | `-h` | Show help message |

