import subprocess
import sys
import os
import concurrent.futures

current_directory = os.getcwd()
sourceFileName = os.path.join(current_directory, "adult_latest.m3u")
channelsOKFile = os.path.join(current_directory, "ok.txt")
channelsFailFile = os.path.join(current_directory, "fail.txt")

def is_ffmpeg_installed(ffmpeg_path):
    try:
        # Run `ffmpeg -version` to check if ffmpeg is installed
        result = subprocess.run(
            [ffmpeg_path, '-version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False

def check_video(ffmpeg_path, url):
    try:
        if not url.startswith("http"):
            print(f"#####error process#####: Invalid URL: {url}")
            return (url, False)

        # Run ffmpeg to check video file validity for 3 seconds
        result = subprocess.run(
            [ffmpeg_path, '-v', 'error', '-t', '3', '-i', url, '-f', 'null', '-'],
            stderr=subprocess.PIPE,
            text=True,
            timeout=10  # Timeout for subprocess execution
        )
        # If there's any error message in stderr, the video file is invalid
        if result.stderr:
            return (url, False)
        else:
            return (url, True)
    except subprocess.TimeoutExpired:
        print(f"Timeout expired for {url}.")
        return (url, False)
    except Exception as e:
        print(f"Error checking {url}: {e}")
        return (url, False)

def parse_m3u_line(line):
    """
    Parse a line from an M3U file.
    Returns a tuple (channel_name, group_title, url) or None if the line is not a valid entry.
    """
    if line.startswith("#EXTINF"):
        # Extract channel name and group title from the #EXTINF line
        parts = line.split(',', 1)
        if len(parts) == 2:
            metadata = parts[0]
            channel_name = parts[1].strip()
            group_title = None

            # Extract group-title from metadata
            if 'group-title=' in metadata:
                group_title = metadata.split('group-title="')[1].split('"')[0]

            return channel_name, group_title
    elif line.startswith("http"):
        # This is the URL line
        return line.strip()
    return None

def check_program_list(file_path, ffmpeg_path):
    try:
        channels_ok_file = channelsOKFile
        channels_fail_file = channelsFailFile
        if os.path.exists(channels_ok_file):
            os.remove(channels_ok_file)
        if os.path.exists(channels_fail_file):
            os.remove(channels_fail_file)

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            urls = []
            descriptions = []
            current_channel = None
            current_group = None

            for line in file:
                line = line.strip()
                parsed = parse_m3u_line(line)

                if isinstance(parsed, tuple):
                    # This is a #EXTINF line, extract channel name and group title
                    current_channel, current_group = parsed
                elif isinstance(parsed, str):
                    # This is a URL line
                    url = parsed
                    if current_channel and url:
                        # Combine channel name and group title for the description
                        description = f"{current_channel} ({current_group})" if current_group else current_channel
                        urls.append(url)
                        descriptions.append(description)
                        current_channel = None
                        current_group = None

        print(f"Found {len(urls)} channels to check.\n")

        # Use a thread pool to check the videos in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=24) as executor:
            results = executor.map(lambda args: check_video(*args), zip([ffmpeg_path] * len(urls), urls))

        # Write the results to files
        ok_files = 0
        fail_files = 0
        with open(channels_ok_file, 'a', encoding='utf-8', errors='ignore') as ok_file, \
                open(channels_fail_file, 'a', encoding='utf-8', errors='ignore') as fail_file:
            for url, result in zip(urls, results):
                clean_description = next((desc for u, desc in zip(urls, descriptions) if u == url), None)
                uc, valid = result
                if valid:
                    ok_files += 1
                    ok_file.write(f"{clean_description},{url}\n")
                    print(f"{clean_description} ({url}) is valid.")
                else:
                    fail_files += 1
                    fail_file.write(f"{clean_description},{url}\n")
                    print(f"{clean_description} ({url}) is invalid.")
        print(f"###OK channels {ok_files}  -  fail channels {fail_files}\n")
    except FileNotFoundError:
        print(f"File {file_path} not found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    ffmpeg_path = r'/volume2/@appstore/MediaServer/bin/ffmpeg'

    # Check if ffmpeg is installed
    if not is_ffmpeg_installed(ffmpeg_path):
        print("ffmpeg is not installed or not found at the specified path. Please install ffmpeg or check the path.")
        sys.exit(1)

    filename = sourceFileName
    print("Processing file:", filename)

    check_program_list(filename, ffmpeg_path)
