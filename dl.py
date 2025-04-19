#!/usr/bin/env python3
import argparse
import asyncio
import os
import sys
import time
from typing import List, Set
import aiohttp
import aiofiles
import requests
from urllib.parse import urlparse


def extract_id(url: str) -> str:
    """Extract the ID from a Loom URL."""
    url = url.split('?')[0]
    return url.split('/')[-1]


async def fetch_loom_download_url(session: aiohttp.ClientSession, video_id: str) -> str:
    """Fetch the download URL for a Loom video."""
    url = f"https://www.loom.com/api/campaigns/sessions/{video_id}/transcoded-url"
    async with session.post(url) as response:
        if response.status != 200:
            raise Exception(f"Failed to fetch download URL: {response.status}")
        data = await response.json()
        return data["url"]


async def download_loom_video(session: aiohttp.ClientSession, url: str, output_path: str) -> None:
    """Download a video from the given URL to the output path."""
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    async with session.get(url) as response:
        if response.status == 403:
            raise Exception("Received 403 Forbidden")
        
        with open(output_path, 'wb') as f:
            async for chunk in response.content.iter_chunked(1024 * 1024):  # 1MB chunks
                f.write(chunk)


async def backoff(retries: int, fn, delay: int = 1000):
    """Retry a function with exponential backoff."""
    try:
        return await fn()
    except Exception as e:
        if retries > 1 and delay <= 32000:
            await asyncio.sleep(delay / 1000)  # Convert ms to seconds
            return await backoff(retries - 1, fn, delay * 2)
        raise e


async def append_to_log_file(url: str, log_file: str) -> None:
    """Append a URL to the log file."""
    async with aiofiles.open(log_file, 'a') as f:
        await f.write(f"{url}\n")


async def read_downloaded_log(log_file: str) -> Set[str]:
    """Read the log file of downloaded URLs."""
    try:
        async with aiofiles.open(log_file, 'r') as f:
            content = await f.read()
            return set(line.strip() for line in content.split('\n') if line.strip())
    except FileNotFoundError:
        return set()


async def async_pool(pool_limit: int, tasks):
    """Run tasks with limited concurrency."""
    semaphore = asyncio.Semaphore(pool_limit)
    
    async def bounded_task(task):
        async with semaphore:
            return await task
    
    return await asyncio.gather(*(bounded_task(task) for task in tasks))


async def download_from_list(args):
    """Download videos from a list of URLs."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(script_dir, 'downloaded.log')
    downloaded_set = await read_downloaded_log(log_file)
    
    file_path = os.path.abspath(args.list)
    async with aiofiles.open(file_path, 'r') as f:
        content = await f.read()
    
    urls = [url.strip() for url in content.split('\n') if url.strip() and url.strip() not in downloaded_set]
    output_directory = os.path.abspath(args.out) if args.out else os.path.join(script_dir, 'Downloads')
    os.makedirs(output_directory, exist_ok=True)
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, url in enumerate(urls):
            video_id = extract_id(url)
            tasks.append(download_single_video(
                session=session,
                url=url,
                video_id=video_id,
                output_directory=output_directory,
                prefix=args.prefix,
                index=i+1,
                log_file=log_file,
                timeout=args.timeout
            ))
        
        await async_pool(5, tasks)  # Limit to 5 concurrent downloads


async def download_single_video(session, url, video_id, output_directory, prefix, index, log_file, timeout):
    """Download a single video and apply delay if needed."""
    try:
        download_url = await fetch_loom_download_url(session, video_id)
        
        if prefix:
            filename = f"{prefix}-{index}-{video_id}.mp4"
        else:
            filename = f"{video_id}.mp4"
        
        output_path = os.path.join(output_directory, filename)
        print(f"Downloading video {video_id} and saving to {output_path}")
        
        await backoff(5, lambda: download_loom_video(session, download_url, output_path))
        await append_to_log_file(url, log_file)
        
        if timeout:
            print(f"Waiting for {timeout/1000} seconds before the next download...")
            await asyncio.sleep(timeout/1000)  # Convert ms to seconds
        else:
            print("Waiting for 5 seconds before the next download...")
            await asyncio.sleep(5)
    
    except Exception as e:
        print(f"Failed to download video {video_id}: {str(e)}")


async def download_single_file(args):
    """Download a single video from URL."""
    video_id = extract_id(args.url)
    
    async with aiohttp.ClientSession() as session:
        download_url = await fetch_loom_download_url(session, video_id)
        output_path = args.out if args.out else f"{video_id}.mp4"
        print(f"Downloading video {video_id} and saving to {output_path}")
        await download_loom_video(session, download_url, output_path)


async def main():
    parser = argparse.ArgumentParser(description="Download Loom videos")
    
    parser.add_argument('--url', '-u', type=str, help='URL of the video in the format https://www.loom.com/share/[ID]')
    parser.add_argument('--list', '-l', type=str, help='Filename of the text file containing the list of URLs')
    parser.add_argument('--prefix', '-p', type=str, help='Prefix for the output filenames when downloading from a list')
    parser.add_argument('--out', '-o', type=str, help='Path to output the file to or directory to output files when using --list')
    parser.add_argument('--timeout', '-t', type=int, help='Timeout in milliseconds to wait between downloads when using --list', default=5000)
    
    args = parser.parse_args()
    
    if not args.url and not args.list:
        parser.error("Please provide either a single video URL with --url or a list of URLs with --list to proceed")
    
    if args.url and args.list:
        parser.error("Please provide either --url or --list, not both")
    
    if args.timeout is not None and args.timeout < 0:
        parser.error("Please provide a non-negative number for --timeout")
    
    if args.list:
        await download_from_list(args)
    elif args.url:
        await download_single_file(args)


if __name__ == "__main__":
    asyncio.run(main())
