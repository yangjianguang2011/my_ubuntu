#!/usr/bin/env python3
# parse_transcript.py
# Parse YouTube transcript files into structured JSON format

import json
import sys
import re
from datetime import datetime

def parse_timestamp(timestamp_str):
    """Convert [HH:MM:SS] format to seconds"""
    try:
        # Remove brackets and split
        clean = timestamp_str.strip('[]')
        parts = clean.split(':')
        if len(parts) == 3:
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m, s = map(int, parts)
            return m * 60 + s
        else:
            return int(parts[0])
    except:
        return 0

def parse_transcript_file(filename):
    """Parse transcript file with [HH:MM:SS] timestamps"""
    transcript_data = []
    current_start = 0
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Skip header lines
        i = 0
        while i < len(lines) and not lines[i].strip().startswith('['):
            i += 1
        
        # Parse timestamped lines
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('['):
                # Extract timestamp and text
                timestamp_match = re.match(r'\[(\d+:\d+:\d+)\](.*)', line)
                if timestamp_match:
                    timestamp_str = timestamp_match.group(1)
                    text = timestamp_match.group(2).strip()
                    
                    start_time = parse_timestamp(timestamp_str)
                    # Assume next timestamp is end time (or use default duration)
                    end_time = start_time + 30  # default 30s duration
                    
                    # Look ahead for next timestamp
                    j = i + 1
                    while j < len(lines) and not lines[j].strip().startswith('['):
                        j += 1
                    if j < len(lines):
                        next_timestamp_match = re.match(r'\[(\d+:\d+:\d+)\]', lines[j])
                        if next_timestamp_match:
                            next_start = parse_timestamp(next_timestamp_match.group(1))
                            end_time = next_start
                    
                    transcript_data.append({
                        'start': start_time,
                        'end': end_time,
                        'text': text
                    })
                    i = j
                else:
                    i += 1
            else:
                i += 1
                
    except Exception as e:
        print(f"Error parsing {filename}: {e}")
    
    return transcript_data

def main():
    if len(sys.argv) != 2:
        print("Usage: python parse_transcript.py <transcript_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    transcript_data = parse_transcript_file(input_file)
    
    # Generate output filename
    base_name = input_file.rsplit('.', 1)[0]
    output_file = f"{base_name}.json"
    
    # Create structured output
    result = {
        "video_id": "OH3MELS3-64",
        "source_file": input_file,
        "parsed_at": datetime.now().isoformat(),
        "transcript": transcript_data,
        "summary": {
            "total_segments": len(transcript_data),
            "total_duration": transcript_data[-1]['end'] if transcript_data else 0,
            "word_count": sum(len(item['text'].split()) for item in transcript_data)
        }
    }
    
    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Transcript parsed successfully!")
    print(f"Output: {output_file}")
    print(f"Segments: {len(transcript_data)}")
    print(f"Duration: {result['summary']['total_duration']:.0f} seconds")

if __name__ == "__main__":
    main()