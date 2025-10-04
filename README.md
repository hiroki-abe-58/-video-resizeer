# Video Compressor - Audio Quality Priority

[日本語](README_ja.md) | [中文](README_zh.md)

A video compression CLI tool for macOS. Compress videos to a target file size while prioritizing audio quality.

## Features

- **Precise Size Control**: Specify target size in MB (decimal support)
- **Audio Quality Priority**: Maintains high audio quality at 192kbps
- **Real-time Progress Display**: Shows progress bar and estimated time remaining
- **2-Pass Encoding**: Achieves high-quality compression
- **Batch Processing**: Process entire directories at once
- **Dry Run Mode**: Preview compression results without actual encoding
- **Format Conversion**: Supports MP4, MOV, AVI, MKV, WebM, FLV
- **Comprehensive Error Handling**: Clear error messages for common issues

## Requirements

- macOS
- Python 3.8 or later
- ffmpeg

## Installation

### 1. Install ffmpeg

```bash
brew install ffmpeg
```

### 2. Download Script

```bash
# Clone from GitHub
git clone https://github.com/hiroki-abe-58/video-compressor.git
cd video-compressor

# Or download directly
curl -O https://raw.githubusercontent.com/hiroki-abe-58/video-compressor/main/compress_video.py
chmod +x compress_video.py
```

### 3. Grant Execute Permission

```bash
chmod +x compress_video.py
```

## Usage

### Basic Usage

```bash
python3 compress_video.py
```

Or:

```bash
./compress_video.py
```

### Command Line Options

```bash
# Normal mode
./compress_video.py

# Dry run mode (preview without encoding)
./compress_video.py --dry-run

# Show version
./compress_video.py --version

# Show help
./compress_video.py --help
```

### Execution Flow

#### Phase 1: Input File Path
```
Enter the path to the video file or directory and press Enter:
> /path/to/video.mp4
```

**Tip**: Drag and drop from Finder works too

#### Phase 2: Target Size Input
```
File name: video.mp4
Current file size: 150.50 MB
Video duration: 00:05:30

To what size (MB) should this video be compressed? Enter a number (decimals allowed):
> 50
```

#### Phase 3: Format Conversion (Optional)
```
Do you want to convert the file extension? (y/press Enter):
> y

Available formats:
  1. MP4 (H.264)
  2. MOV (QuickTime)
  3. AVI
  4. MKV (Matroska)
  5. WebM
  6. FLV (Flash Video)

Select a number: 1
```

#### Phase 4: Compression
```
[1/2] Pass 1: Analyzing bitrate...
Pass 1: [████████████████████░░░░░░░░░░░░░░░░░░░░]  48.5% | Time remaining: 00:02:15

[2/2] Pass 2: Final encoding...
Pass 2: [████████████████████████████████████████] 100.0% | Time remaining: 00:00:00
```

#### Phase 5: Complete
```
Compression complete! The compressed video file has been saved.
============================================================
File name: video--compressed--50.0MB--2025-10-04-15-30-45.mp4
Save location: /path/to/video--compressed--50.0MB--2025-10-04-15-30-45.mp4
Target size: 50.00 MB
Actual size: 49.85 MB
Difference: 0.15 MB
============================================================

Compress another video? (y/n):
```

### Dry Run Mode

Preview compression results without actual encoding:

```bash
./compress_video.py --dry-run
```

**Output Example**:
```
Dry Run Results
============================================================
Input file: video.mp4
Current size: 150.50 MB
Target size: 50.00 MB
Compression ratio: 66.8%
Video duration: 00:05:30

[Encoding Settings]
  Video bitrate: 1145 kbps
  Audio bitrate: 192 kbps (AAC)
  Codec: H.264 (libx264)

[Estimated Quality]
  High quality (minor degradation)

[Output File]
  File name: video--compressed--50.0MB--2025-10-04-15-30-45.mp4
  Save location: /path/to/video--compressed--50.0MB--2025-10-04-15-30-45.mp4
============================================================

To actually compress, run without the --dry-run option.
```

### Batch Processing

Process all video files in a directory:

```bash
./compress_video.py

# Enter directory path
> /Users/username/Videos/batch-compress/

# 5 video files found:
#   1. video1.mp4 (150.50 MB)
#   2. video2.mov (200.30 MB)
#   ...

# Select settings method:
#   1. Batch settings (apply same settings to all files)
#   2. Individual settings (configure each file separately)
```

## Output File Format

```
[original_filename]--compressed--[target_size]MB--[yyyy-mm-dd-hh-mm-ss].[extension]
```

Example:
```
my_video--compressed--50.0MB--2025-10-04-15-30-45.mp4
```

## Error Handling

This tool detects and clearly displays the following errors:

- ffmpeg not installed
- File does not exist
- Unsupported file format
- Target size larger than current size
- Target size too small (audio alone exceeds capacity)
- Invalid input values (non-numeric)
- Encoding errors

## Technical Details

### Compression Algorithm

1. **Get video duration** (using ffprobe)
2. **Fix audio bitrate at 192kbps** (maintain high quality)
3. **Calculate required video bitrate from target size**
   ```
   Video bitrate = (target size - audio size) / video duration * 0.95
   ```
4. **High-quality compression with 2-pass encoding**
   - Pass 1: Analyze bitrate distribution
   - Pass 2: Optimized encoding

### Supported File Formats

**Input**: `.mp4`, `.avi`, `.mov`, `.mkv`, `.flv`, `.wmv`, `.webm`, `.m4v`, `.mpeg`, `.mpg`

**Output**: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.flv`

## Troubleshooting

### ffmpeg not found
```bash
brew install ffmpeg
```

### Compression takes too long
- 2-pass encoding is time-consuming (pass 1 + pass 2)
- Long videos may take tens of minutes
- Progress can be monitored via progress bar

### Target size deviation
- Deviation of ±5% is normal
- For more accuracy, set target size slightly smaller

### Encoding fails
- Check disk space
- Verify video file is not corrupted
- Try a different extension

## License

MIT License

## Author

[hiroki-abe-58](https://github.com/hiroki-abe-58)

## Acknowledgments

Reference: https://note.com/genelab_999/n/n5db5c3a80793
