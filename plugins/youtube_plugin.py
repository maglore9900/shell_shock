# plugins/youtube_plugin.py
import tempfile
import os
import time
from pytubefix import YouTube
from plugins import BasePlugin

class Plugin(BasePlugin):
    """YouTube streaming plugin"""
    
    def __init__(self, player):
        super().__init__(player)
        self.name = "YouTube"
        self.command_name = player.env("YOUTUBE_CMD", default="youtube")
        
        # Initialize storage for YouTube videos
        self.current_video = None
        self.download_dir = player.env("YOUTUBE_DOWNLOAD_DIR", default="youtube_downloads")
        
        # For temporary file management
        self.temp_dir = tempfile.mkdtemp()
        self.current_temp_file = None
        
        # Create download directory if it doesn't exist
        os.makedirs(self.download_dir, exist_ok=True)
        
        self.initialized = True
    
    def command_help(self):
        """Return help text for YouTube commands"""
        if not self.is_available():
            return "YouTube integration not available"
        
        help_text = """
Available YouTube commands:
  play <url>     - Play audio from a YouTube video URL
  stop           - Stop playback
  pause          - Pause playback
  resume         - Resume playback
  volume <0-100> - Set playback volume
  download_audio <url> - Download audio from a YouTube video URL and convert to MP3
"""
        return help_text
    
    def _play_impl(self, args):
        """Play audio from a YouTube URL"""
        if not args:
            print("Usage: youtube play <url>")
            return False
        
        url = args[0] if isinstance(args, list) else args
        
        try:
            # Ensure exclusive playback
            self.player.plugin_manager.ensure_exclusive_playback('youtube')
            
            # Clean up any previous temp file
            self.cleanup_temp_file()
            
            print(f"Processing YouTube URL: {url}")
            
            # Use pytube to get the audio stream
            yt = YouTube(url)
            audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
            
            if not audio_stream:
                print("No audio stream found for this YouTube video")
                return False
            
            # Create a temp file name
            temp_filename = f"yt_audio_{int(time.time())}.{audio_stream.subtype}"
            temp_filepath = os.path.join(self.temp_dir, temp_filename)
            
            # Download to a temporary file (required for pygame)
            print(f"Downloading audio from: {yt.title}")
            audio_stream.download(output_path=self.temp_dir, filename=temp_filename)
            
            # Create a video info dictionary
            self.current_video = {
                'title': yt.title,
                'author': yt.author,
                'url': url,
                'duration': yt.length,
                'local_file': temp_filepath
            }
            
            # Play the downloaded audio file
            success, temp_file = self.play_audio_file(temp_filepath)
            
            if success:
                if temp_file:
                    self.current_temp_file = temp_file
                print(f"Now playing: {yt.title} by {yt.author}")
                return True
            else:
                print(f"Error playing YouTube audio")
                return False
        except Exception as e:
            print(f"Error playing YouTube audio: {e}")
            return False
    
    def download_audio(self, args):
        """Download audio from a YouTube URL and convert to MP3"""
        if not args:
            print("Usage: youtube play <url>")
            return False
        
        url = args[0] if isinstance(args, list) else args
        
        try:
            # Ensure exclusive playback
            self.player.plugin_manager.ensure_exclusive_playback('youtube')
            
            # Use pytube to get the audio stream
            yt = YouTube(url)
            audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
            
            if not audio_stream:
                print("No audio stream found for this YouTube video")
                return False
            
            # Create temp file names for WebM and MP3
            temp_filename = f"temp_{yt.title}.{audio_stream.subtype}"
            temp_filepath = os.path.join(self.temp_dir, temp_filename)
            
            # Final MP3 filename
            mp3_filename = f"{yt.title} by {yt.author}.mp3"
            mp3_filepath = os.path.join(self.download_dir, mp3_filename)
            
            # Download to a temporary WebM file
            print(f"Downloading {temp_filename}")
            audio_stream.download(output_path=self.temp_dir, filename=temp_filename)
            
            # Convert WebM to MP3
            print(f"Converting to MP3...")
            success = self.player.media_handler.convert_to_mp3(temp_filepath, mp3_filepath)
            
            # Create a video info dictionary
            self.current_video = {
                'title': yt.title,
                'author': yt.author,
                'url': url,
                'duration': yt.length,
                'local_file': mp3_filepath
            }
            
            if success:
                self.current_temp_file = temp_filepath
                self.cleanup_temp_file()
                print(f"Download Successful: {yt.title} by {yt.author}")
                return True
            else:
                print(f"Error playing converted audio")
                return False
        except Exception as e:
            print(f"Error processing YouTube audio: {e}")
            return False

    def _pause_impl(self, args):
        """Pause playback"""
        return self.pause_audio()
    
    def _stop_impl(self, args):
        """Stop playback"""
        result = self.stop_audio()
        self.current_video = None
        return result
    
    def _next_impl(self, args):
        """Skip to next track (not applicable for YouTube)"""
        print("Next track not available for YouTube")
        return False
    
    def _prev_impl(self, args):
        """Go to previous track (not applicable for YouTube)"""
        print("Previous track not available for YouTube")
        return False
    
    def _set_volume_impl(self, volume):
        """Set volume level"""
        return self.set_audio_volume(volume / 100.0)
    
    def update_playback_info(self):
        """Update playback info"""
        if not self.current_video:
            return
        
        position = self.get_audio_position()
        
        playback_info = {
            'track_name': self.current_video['title'],
            'artist': self.current_video['author'],
            'album': 'YouTube',
            'position': position,
            'duration': self.current_video['duration'],
            'state': 'PLAYING' if self.is_audio_playing() else 'STOPPED'
        }
        
        self.update_playback_state_from_info(playback_info)
    
    def get_current_playback(self):
        """Get current playback info"""
        if not self.current_video:
            return None
        
        position = self.get_audio_position()
        
        return {
            'track_name': self.current_video['title'],
            'artist': self.current_video['author'],
            'album': 'YouTube',
            'position': position,
            'duration': self.current_video['duration'],
            'is_playing': self.is_audio_playing()
        }
    
    def play_track(self, track_data):
        """Play a track from data"""
        print("This method is not implemented for YouTube")
        return False
    
    def on_shutdown(self, data):
        """Handle shutdown"""
        self.stop_audio()
        
        # Clean up temp directory
        try:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    try:
                        os.remove(os.path.join(self.temp_dir, file))
                    except:
                        pass
                os.rmdir(self.temp_dir)
        except Exception as e:
            print(f"Warning: Could not remove temp directory: {e}")

    

