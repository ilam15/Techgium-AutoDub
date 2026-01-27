# Automatic Cleanup System

## Overview

The Techgium-AutoDub backend now includes an **automatic cleanup system** that maintains disk space efficiency by removing temporary files after each video generation while preserving only the latest output video.

## How It Works

### 🔄 Automatic Background Cleanup

After each successful video dubbing operation, the system automatically:

1. **Keeps the Latest Output** - Preserves the most recently generated `output_*.mp4` file
2. **Removes Old Outputs** - Deletes all previous output videos
3. **Cleans Temporary Files** - Removes all processing artifacts from temporary directories
4. **Runs in Background** - Executes after the API response is sent (no user delay)

### 📁 Directories Cleaned

The cleanup process targets these directories:

| Directory | Content Type | Typical Size |
|-----------|-------------|--------------|
| `audio/` | Audio segments (mp3, wav, clean.wav) | ~50 MB |
| `audio_data/` | Separated vocals/noise files | ~500 MB |
| `temp_uploads/` | Uploaded video files | ~700 MB |
| `subtitle_audio/` | TTS audio for subtitles | ~50 MB |
| `TTS_DUB/` | Text-to-speech files | ~50 MB |
| `temp/` | Temporary processing files | ~100 MB |
| `dummy/` | Segment processing folders | Variable |
| `generated_subtitle/` | Generated subtitle files | ~1 MB |

**Total Space Recovered per Cleanup: ~1.5-2 GB** 🎯

### 🛡️ Files Preserved

- ✅ Latest `output_*.mp4` video
- ✅ Core application files (`app.py`, `api/`, etc.)
- ✅ Configuration files (`.env`, `requirements.txt`, etc.)
- ✅ Virtual environment (`venv311/`)

## Usage

### Automatic Mode (Default)

The cleanup runs automatically after each video generation via the API:

```bash
# No action needed - cleanup happens automatically!
# After each /dub_video request, temporary files are cleaned
```

### Manual Mode

You can also run cleanup manually:

```bash
# From the project root directory
python clean_up.py
```

### Programmatic Usage

```python
from clean_up import cleanup_all_temporary_files

# Run cleanup and get statistics
stats = cleanup_all_temporary_files(keep_latest_output=True)

print(f"Files deleted: {stats['total_files_deleted']}")
print(f"Space freed: {stats['total_bytes_freed']} bytes")
print(f"Latest output: {stats['latest_output_kept']}")
```

## Configuration

### Keep Latest Output (Default: True)

```python
# Keep the latest output video
cleanup_all_temporary_files(keep_latest_output=True)

# Delete ALL temporary files including outputs
cleanup_all_temporary_files(keep_latest_output=False)
```

### Preserve Specific Files

```python
# Preserve additional files
preserve_list = [
    "/path/to/important/file1.mp4",
    "/path/to/important/file2.wav"
]
cleanup_all_temporary_files(preserve_files=preserve_list)
```

## Cleanup Statistics

The cleanup system provides detailed statistics:

```
============================================================
CLEANUP SUMMARY
============================================================
✅ Total files deleted: 643
✅ Total directories deleted: 25
✅ Total space freed: 1.85 GB
📦 Latest output preserved: output_abc12345.mp4
============================================================
```

## Architecture Integration

### API Flow

```
1. User uploads video → /dub_video endpoint
2. Video processing begins
3. Output video generated → output_xyz.mp4
4. API returns success response to user
5. Background cleanup task starts (non-blocking)
6. Temporary files deleted
7. Only latest output remains
```

### Code Integration

**File: `api/routes.py`**
```python
# After successful video generation
background_tasks.add_task(cleanup_all_temporary_files, keep_latest_output=True)
logger.info(f"Scheduled background cleanup for request: {trace_id}")
```

## Benefits

### 💾 Disk Space Management
- Prevents accumulation of temporary files
- Recovers ~1.5-2 GB per video processing
- Maintains clean working directory

### ⚡ Performance
- Non-blocking background execution
- No impact on API response time
- Efficient directory traversal

### 🔒 Safety
- Preserves latest output
- Protects core application files
- Detailed error logging

## Troubleshooting

### Issue: Cleanup Not Running

**Check logs:**
```bash
# Look for cleanup messages in logs
grep "cleanup" logs/app.log
```

**Verify import:**
```python
# In api/routes.py
from clean_up import cleanup_all_temporary_files
```

### Issue: Files Not Being Deleted

**Permissions:**
- Ensure the application has write permissions to temporary directories
- Check file locks (files in use by other processes)

**Manual cleanup:**
```bash
python clean_up.py
```

### Issue: Important Files Deleted

**Recovery:**
- Check if files were in the preserve list
- Verify file paths are absolute
- Review cleanup logs for details

## Best Practices

1. **Monitor Disk Space**: Regularly check available disk space
2. **Review Logs**: Check cleanup logs for any errors
3. **Test Before Production**: Run manual cleanup first to verify behavior
4. **Backup Important Files**: Keep backups of critical output videos
5. **Adjust Retention**: Modify `keep_latest_output` based on your needs

## Future Enhancements

Potential improvements:

- [ ] Configurable retention policy (keep last N outputs)
- [ ] Scheduled cleanup (cron-based)
- [ ] Cleanup based on disk space threshold
- [ ] Archive old outputs to cloud storage
- [ ] Cleanup metrics dashboard

## Support

For issues or questions:
- Check logs in `logs/` directory
- Review error messages in cleanup output
- Verify file permissions
- Contact development team

---

**Last Updated**: January 27, 2026  
**Version**: 1.0.0
