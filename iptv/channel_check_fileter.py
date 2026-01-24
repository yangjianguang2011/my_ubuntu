import subprocess
import sys
import re
import os

def is_ffmpeg_installed(ffmpeg_path):
    """Check if FFmpeg is installed and accessible."""
    try:
        result = subprocess.run([ffmpeg_path, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def check_video(url, ffmpeg_path):
    """Check if a video stream is valid using FFmpeg."""
    try:
        result = subprocess.run([ffmpeg_path, '-v', 'error', '-t', '5', '-i', url, '-c', 'copy', '-f', 'null', '-'],
                                stderr=subprocess.PIPE, text=True, timeout=10)
        return not result.stderr
    except subprocess.TimeoutExpired:
        print(f"Timeout expired for {url}.")
    except Exception as e:
        print(f"Error checking {url}: {e}")
    return False

def extract_tvname(extinf_line):
    """Extract TV name from #EXTINF line."""
    match = re.search(r'tvg-id="([^"]+)"', extinf_line)
    if match:
        return match.group(1)
    parts = extinf_line.split(',', 1)
    return parts[1] if len(parts) > 1 else "Unknown"

def remove_bracket_content(text):
    """Remove text within brackets and unnecessary spaces."""
    text = re.sub(r'[\[\(].*?[\]\)]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def check_program_list(file_path, ffmpeg_path):
    """Check IPTV channels from an input file."""
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    file_ext = os.path.splitext(file_path)[1].lower()
    ok_file = file_path.replace(file_ext, '_ok' + file_ext)
    fail_file = file_path.replace(file_ext, '_fail' + file_ext)

    print(f"Checking {file_path} ({ok_file}) {file_ext}...")

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file,\
         open(ok_file, 'w', encoding='utf-8') as ok_f,\
         open(fail_file, 'w', encoding='utf-8') as fail_f:
        
        tvid, addr = None, None
        for line in file:
            line = line.strip()

            if not line:
            	continue
            if line.startswith('#EXTM3U'):
                    ok_f.write(line)
                    fail_f.write(line)
                    continue

            if file_ext == '.m3u' and line.startswith("#EXTINF:"):
                tvid = line
                continue
            
            if line.startswith(('http', 'rtmp', 'rtp','https')):
                addr = line
            
            if tvid and addr:
                tvname = extract_tvname(tvid)
                print(f"Checking {tvname} ({addr})...")
                if check_video(addr, ffmpeg_path):
                    ok_f.write(f"{tvid}\n{addr}\n")
                    print(f"Valid: {tvname}")
                else:
                    fail_f.write(f"{tvid}\n{addr}\n")
                    print(f"Invalid: {tvname}")
                tvid, addr = None, None
            elif file_ext == '.txt':
                parts = line.split(',', 1)
                if len(parts) == 2:
                    desc, url = map(remove_bracket_content, parts)
                    if check_video(url, ffmpeg_path):
                        ok_f.write(f"{desc},{url}\n")
                        print(f"Valid: {desc}")
                    else:
                        fail_f.write(f"{desc},{url}\n")
                        print(f"Invalid: {desc}")

if __name__ == "__main__":
    #ffmpeg_path = r'C:\ffmpeg\bin\ffmpeg.exe'  # Update this path accordingly
    ffmpeg_path = r'/volume2/@appstore/MediaServer/bin/ffmpeg'
    if not is_ffmpeg_installed(ffmpeg_path):
        print("FFmpeg is not installed or path is incorrect.")
        sys.exit(1)
    
    if len(sys.argv) != 2:
        print("Usage: python script.py <inputfile>")
        sys.exit(1)
    
    check_program_list(sys.argv[1], ffmpeg_path)
