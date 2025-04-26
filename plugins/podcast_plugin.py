# plugins/podcast_plugin.py
import requests
import xml.etree.ElementTree as ET
import os
import urllib.request
from urllib.parse import urlparse
import time
import tempfile
from pydub import AudioSegment
from plugins import BasePlugin
import pygame

class Plugin(BasePlugin):
    """Podcast integration plugin"""
    
    def __init__(self, player):
        super().__init__(player)
        self.name = "Podcast"
        self.command_name = player.env("PODCAST_CMD", default="podcast")
        self.paginate_commands = ['search', 'list', 'feeds']
        
        # Initialize feeds and episodes storage
        self.feeds_list = {}
        self.current_feed_url = None
        self.current_episodes = []
        self.current_episode = None
        self.current_position = 0.0
        self.current_episode_index = None
        self.download_dir = player.env("PODCAST_DOWNLOAD_DIR", default="podcast_downloads")
        # Ensure download_dir is not empty, use default if it is
        if not self.download_dir:
            self.download_dir = "podcast_downloads"
        
        # For temporary file management
        self.temp_dir = tempfile.mkdtemp()
        self.current_temp_file = None
        
        # Create download directory if it doesn't exist
        os.makedirs(self.download_dir, exist_ok=True)
        
        # For tracking playback
        self.track_start_time = 0
        
        # Try to load default feeds if provided in environment
        default_feeds = player.env("DEFAULT_PODCAST_FEEDS", default=None)
        if default_feeds:
            # Split by comma and process each feed URL
            feed_urls = [url.strip() for url in default_feeds.split(",")]
            for feed_url in feed_urls:
                if feed_url:  # Skip empty entries
                    self.add([feed_url])
            
        self.initialized = True
    
    def command_help(self):
        """Return help text for podcast commands"""
        if not self.is_available():
            return "Podcast integration not available"
        
        help_text = """
Available Podcast commands:
  add <url>      - Add a podcast feed by URL
  list [feed]    - List episodes in the current or specified feed
  feeds          - List all added podcast feeds
  play <index>   - Play episode by index
  download <index> - Download episode by index
  info <index>   - Show detailed info about an episode
  search <term>  - Search episodes in current feed
  load <index>   - Switch to a different feed by index
  stop           - Stop playback
  pause          - Pause playback
  resume         - Resume playback
  next           - Skip to next episode
  prev           - Go to previous episode
"""
        return help_text
    
    # Implementation of BasePlugin abstract methods
    def _play_impl(self, args):
        """Play a podcast episode by index"""
        # The pagination system sends the selected index as a list with a single integer
        if isinstance(args, list) and len(args) == 1 and isinstance(args[0], int):
            # Play episode at the selected index
            episode_index = args[0]
            return self._play_episode(episode_index)
        
        # If the argument is a single integer as string (from command line)
        if isinstance(args, list) and len(args) == 1 and isinstance(args[0], str) and args[0].isdigit():
            episode_index = int(args[0])
            return self._play_episode(episode_index)
        
        # If this is called from CLI pagination handler with a tuple
        if isinstance(args, tuple) and len(args) == 3:
            display_text, episode_index, metadata = args
            return self._play_episode(episode_index)
        
        # If passed a list containing a tuple (another pagination pattern)
        if isinstance(args, list) and len(args) == 1 and isinstance(args[0], tuple) and len(args[0]) == 3:
            display_text, episode_index, metadata = args[0]
            return self._play_episode(episode_index)
        
        return self._play_episode(0)  # Default to first episode if no valid args
        # print(f"Invalid arguments for play command: {type(args)}, {args}")
        # return False
    
    def _pause_impl(self, args):
        """Pause playback"""
        return self.pause_audio()  # Use BasePlugin's helper method


    def _set_volume_impl(self, args):
        """Set the Spotify volume"""
        pass
    
    def _stop_impl(self, args):
        """Stop playback"""
        return self.stop_audio()  # Use BasePlugin's helper method
    
    def _next_impl(self, args):
        """Skip to next episode"""
        if not self.current_episodes or self.current_episode_index is None:
            print("No episodes loaded or no current episode")
            return False
            
        next_index = (self.current_episode_index + 1) % len(self.current_episodes)
        return self._play_episode(next_index)
    
    def _prev_impl(self, args):
        """Go to previous episode"""
        if not self.current_episodes or self.current_episode_index is None:
            print("No episodes loaded or no current episode")
            return False
            
        prev_index = (self.current_episode_index - 1) % len(self.current_episodes)
        return self._play_episode(prev_index)
    
    def _play_episode(self, episode_index):
        """Internal method to play a podcast episode by index"""
        if not self.current_episodes:
            print("No episodes loaded. Use 'podcast list' first.")
            return False
            
        # Validate episode index
        if episode_index < 0 or episode_index >= len(self.current_episodes):
            print(f"Invalid episode index. Must be between 0 and {len(self.current_episodes)-1}")
            return False
        
        # IMPORTANT: Ensure exclusive playback before starting
        self.player.plugin_manager.ensure_exclusive_playback('podcast')
        
        # Get the episode
        episode = list(reversed(self.current_episodes))[episode_index]
        self.current_episode = episode
        self.current_episode_index = episode_index

        filename = "".join(c if c.isalnum() or c in ' -_' else '_' for c in episode['title'])
        filename = filename.replace(' ', '_') + '.mp3'
        
        try:
            file_path = self.download(episode['url'], filename, self.download_dir)
            success, temp_file = self.play_audio_file(file_path)
            if not success:
                print(f"Error playing podcast episode: {episode['title']}")
                return False
            
            # If a new temp file was created, track it for cleanup
            if temp_file:
                self.current_temp_file = temp_file
            
            return True
        except Exception as e:
            print(f"Error playing episode: {e}")
            return False
    
    def _cleanup_temp_file(self):
        """Clean up temporary file if it exists"""
        # Use the BasePlugin's cleanup method
        self.cleanup_temp_file()
    
    def _is_playing(self):
        """Override to check if podcast is currently playing"""
        return self.current_episode is not None and self.is_audio_playing()  # Use BasePlugin's helper method

    
    def _can_play(self):
        """Override to check if podcast plugin can play"""
        return self.is_available() and self.current_episodes is not None and len(self.current_episodes) > 0
    
    def add(self, args):
        """Add a podcast feed URL"""
        if not args:
            print("Usage: podcast add <feed_url>")
            return
            
        feed_url = args[0] if isinstance(args, list) else args
        
        try:
            # Fetch and parse the feed
            response = requests.get(feed_url)
            response.raise_for_status()
            
            # Parse the XML feed
            root = ET.fromstring(response.content)
            
            # Get podcast title from channel
            channel = root.find('.//channel')
            title_elem = channel.find('./title') if channel is not None else None
            feed_title = title_elem.text if title_elem is not None else "Unknown Podcast"
            
            # Store feed in our list
            self.feeds_list[feed_url] = {
                'title': feed_title,
                'url': feed_url
            }
            
            # Set as current feed if we don't have one already
            if self.current_feed_url is None:
                self.current_feed_url = feed_url
                self._refresh_current_feed()
            
            print(f"Added podcast feed: {feed_title}")
            return True
        except Exception as e:
            print(f"Error adding podcast feed: {e}")
            return False
    
    def _refresh_current_feed(self):
        """Refresh episodes for the current feed"""
        if not self.current_feed_url:
            print("No feed selected")
            return False
            
        try:
            # Fetch and parse the feed
            response = requests.get(self.current_feed_url)
            response.raise_for_status()
            
            # Parse the XML feed
            root = ET.fromstring(response.content)
            
            # Find all episodes (items in RSS)
            items = root.findall('.//item')
            
            self.current_episodes = []
            for item in items:
                title_elem = item.find('./title')
                title = title_elem.text if title_elem is not None else "Unknown Title"
                
                enclosure = item.find('./enclosure')
                if enclosure is not None and 'url' in enclosure.attrib:
                    audio_url = enclosure.attrib['url']
                    
                    # Get publication date
                    pub_date_elem = item.find('./pubDate')
                    pub_date = pub_date_elem.text if pub_date_elem is not None else "Unknown Date"
                    
                    # Get episode description
                    description_elem = item.find('./description')
                    description = description_elem.text if description_elem is not None else "No description available"
                    
                    # Try to get duration if available
                    duration = 0
                    duration_elem = item.find('./itunes:duration', namespaces={'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'})
                    if duration_elem is not None and duration_elem.text:
                        try:
                            # Try to parse duration in HH:MM:SS format
                            duration_parts = duration_elem.text.split(':')
                            if len(duration_parts) == 3:
                                duration = int(duration_parts[0]) * 3600 + int(duration_parts[1]) * 60 + int(duration_parts[2])
                            elif len(duration_parts) == 2:
                                duration = int(duration_parts[0]) * 60 + int(duration_parts[1])
                            elif len(duration_parts) == 1 and duration_elem.text.isdigit():
                                duration = int(duration_elem.text)
                        except ValueError:
                            duration = 0
                    
                    self.current_episodes.append({
                        'title': title,
                        'url': audio_url,
                        'pub_date': pub_date,
                        'description': description,
                        'feed_url': self.current_feed_url,
                        'feed_title': self.feeds_list[self.current_feed_url]['title'],
                        'duration': duration
                    })
            
            if self.current_feed_url.endswith('/'):
                self.current_feed_url = self.current_feed_url[:-1]
            print(f"Updated {self.current_feed_url.split('/')[-1]} feed.")
            return True
        except Exception as e:
            print(f"Error refreshing feed: {e}")
            return False
    
    def update_playback_info(self):
        """Update the plugin manager with current playback info"""
        if not self.current_episode:
            return
        
        # Get current position using BasePlugin's helper method
        position = self.get_audio_position()
        
        # Create standard playback info
        playback_info = {
            'track_name': self.current_episode['title'],
            'artist': self.current_episode['feed_title'],
            'album': None,
            'position': position,
            'duration': self.current_episode['duration'],
            'state': 'PLAYING' if self.is_audio_playing() else 'STOPPED'
        }
        
        # Update the plugin manager
        self.update_playback_state_from_info(playback_info)
    
    def list(self, args):
        """List episodes in the current feed"""
        if not self.current_feed_url:
            print("No feed selected. Use 'podcast add <url>' to add a feed.")
            return []
            
        if not self.current_episodes:
            if not self._refresh_current_feed():
                return []
        
        # If feed name is specified, try to switch to it
        if args and args[0] in [feed['title'] for feed in self.feeds_list.values()]:
            feed_title = args[0]
            for url, info in self.feeds_list.items():
                if info['title'] == feed_title:
                    self.current_feed_url = url
                    self._refresh_current_feed()
                    break
        
        # Create display items for pagination
        display_items = []
        for i, episode in enumerate(self.current_episodes):
            # Format: (display_text, episode_index, metadata)
            display_items.append((
                f"{episode['title']} ({episode['pub_date']})",
                i,
                {
                    'url': episode['url'],
                    'title': episode['title']
                }
            ))
                
        return display_items
    
    def feeds(self, args):
        """List all added podcast feeds"""
        if not self.feeds_list:
            print("No podcast feeds added. Use 'podcast add <url>' to add a feed.")
            return []
            
        display_items = []
        for i, (url, info) in enumerate(self.feeds_list.items()):
            is_current = url == self.current_feed_url
            # Format: (display_text, feed_url, metadata)
            display_items.append((
                f"{info['title']}{' (current)' if is_current else ''}",
                url,
                {
                    'title': info['title'],
                    'is_current': is_current
                }
            ))
                
        return display_items
    
    def load(self, args):
        """Switch to a different feed by index or URL"""
        if not args:
            print("Usage: podcast load <index or url>")
            return False
            
        # If numeric index, get the feed URL from our list
        if args[0].isdigit():
            index = int(args[0])
            if index < len(self.feeds_list):
                feed_url = list(self.feeds_list.keys())[index]
            else:
                print(f"Invalid feed index: {index}")
                return False
        else:
            # Assume it's a feed URL or name
            feed_url = args[0]
            
            # Check if it's a name instead of URL
            for url, info in self.feeds_list.items():
                if info['title'] == feed_url:
                    feed_url = url
                    break
        
        # Make sure we have this feed
        if feed_url not in self.feeds_list:
            print(f"Feed not found: {feed_url}")
            print("Use 'podcast add <url>' to add it first.")
            return False
            
        # Set as current feed
        self.current_feed_url = feed_url
        self._refresh_current_feed()
        
        print(f"Switched to feed: {self.feeds_list[feed_url]['title']}")
        return True
    
    # def download(self, args):
    #     """Download an episode by index"""
    #     if not args or not args[0].isdigit():
    #         print("Usage: podcast download <episode_index>")
    #         return False
            
    #     if not self.current_episodes:
    #         print("No episodes loaded. Use 'podcast list' first.")
    #         return False
            
    #     episode_index = int(args[0])
    #     if episode_index < 0 or episode_index >= len(self.current_episodes):
    #         print(f"Invalid episode index. Must be between 0 and {len(self.current_episodes)-1}")
    #         return False
            
    #     episode = self.current_episodes[episode_index]
        
    #     # Create a valid filename from the episode title
    #     filename = "".join(c if c.isalnum() or c in ' -_' else '_' for c in episode['title'])
    #     filename = filename.replace(' ', '_') + '.mp3'
    #     filepath = os.path.join(self.download_dir, filename)
        
    #     print(f"Downloading '{episode['title']}' to {filepath}")
    #     try:
    #         urllib.request.urlretrieve(episode['url'], filepath)
    #         print(f"Download complete: {filepath}")
            
    #         # Update episode to include local file path
    #         episode['local_file'] = filepath
    #         self.current_episodes[episode_index] = episode
            
    #         return filepath
    #     except Exception as e:
    #         print(f"Error downloading episode: {e}")
    #         return False
    
    # def search(self, args):
    #     """Search episodes in current feed"""
    #     if not args:
    #         print("Usage: podcast search <search_term>")
    #         return []
            
    #     if not self.current_episodes:
    #         print("No episodes loaded. Use 'podcast list' first.")
    #         return []
            
    #     search_term = " ".join(args).lower()
        
        # Search in titles and descriptions
        # matches = []
        # for i, episode in enumerate(self.current_episodes):
        #     title = episode['title'].lower()
        #     description = episode['description'].lower()
            
        #     if search_term in title or search_term in description:
        #         # Format: (display_text, episode_index, metadata)
        #         matches.append((
        #             f"{episode['title']} ({episode['pub_date']})",
        #             i,
        #             {
        #                 'url': episode['url'],
        #                 'title': episode['title']
        #             }
        #         ))
        
        # if not matches:
        #     print(f"No episodes found matching '{search_term}'")
            
        # return matches

    def resume(self, args):
        """Resume playback"""
        if not self.current_episode:
            print("No episode is paused")
            return False
            
        result = self.resume_audio()  # Use BasePlugin's helper method
        
        # Using BasePlugin's handle_state_transition for state update
        if result:
            self.update_playback_state({'state': 'PLAYING'})
        
        return result
    
    def info(self, args):
        """Show detailed info about an episode"""
        if not args or not args[0].isdigit():
            print("Usage: podcast info <episode_index>")
            return False
            
        if not self.current_episodes:
            print("No episodes loaded. Use 'podcast list' first.")
            return False
            
        episode_index = int(args[0])
        if episode_index < 0 or episode_index >= len(self.current_episodes):
            print(f"Invalid episode index. Must be between 0 and {len(self.current_episodes)-1}")
            return False
            
        episode = self.current_episodes[episode_index]
        
        print(f"Title: {episode['title']}")
        print(f"Published: {episode['pub_date']}")
        print(f"Feed: {episode['feed_title']}")
        print(f"URL: {episode['url']}")
        
        # Format duration if available
        if episode['duration'] > 0:
            minutes = int(episode['duration'] // 60)
            seconds = int(episode['duration'] % 60)
            print(f"Duration: {minutes}:{seconds:02d}")
        
        if 'local_file' in episode:
            print(f"Downloaded: {episode['local_file']}")
        
        print("\nDescription:")
        print(episode['description'])
        
        return True
        
    def get_current_playback(self):
        """Get current playback info for plugin manager"""
        if not self.current_episode:
            return None
        
        # Get position from helper method
        position = self.get_audio_position()
        is_playing = self.is_audio_playing()
        
        # Return playback info
        return {
            'track_name': self.current_episode['title'],
            'artist': self.current_episode['feed_title'],
            'album': None,
            'position': position,
            'duration': self.current_episode['duration'],
            'is_playing': is_playing
        }
    
    def play_track(self, item_data):
        """Play a track selected from search results or episode list"""
        try:
            # Unpack the track data
            display_text, episode_index, metadata = item_data
            
            # Play the episode
            return self._play_episode(episode_index)
        except Exception as e:
            print(f"Error playing episode: {e}")
            return False
    
    def on_play(self, data):
        """Handle play event from the player"""
        # If local player starts playing, we should stop our playback
        if self.current_episode and self._is_playing():
            self.stop([])
    
    def on_shutdown(self, data):
        """Handle shutdown event"""
        # Stop any active playback
        self.stop_audio()
        
        # Try to remove temp directory
        try:
            if os.path.exists(self.temp_dir):
                os.rmdir(self.temp_dir)
        except Exception as e:
            print(f"Warning: Could not remove temp directory: {e}")