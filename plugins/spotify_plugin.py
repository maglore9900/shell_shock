# plugins/spotify_plugin.py
import time
from plugins import BasePlugin
from modules import spotify

class Plugin(BasePlugin):
    """Spotify integration plugin"""
    
    def __init__(self, player):
        super().__init__(player)
        self.name = "Spotify"
        self.command_name = player.env("SPOTIFY_CMD", default="spotify")
        self.paginate_commands = ['search', 'playlists', 'albums']
        
        # Initialize Spotify client
        try:
            self.spotify = spotify.Spotify(player.env)
        except Exception as e:
            print(f"Error initializing Spotify: {e}")
            self.initialized = False
    
    def command_help(self):
        """Return help text for Spotify commands"""
        if not self.is_available():
            return "Spotify integration not available"
        
        help_text = """
Available Spotify commands:
  play [track]   - Play or resume playback (optionally search for track)
  pause          - Pause playback
  next           - Skip to next track
  prev           - Go to previous track
  search <query> - Search for tracks
  playlists      - List your playlists
  volume <0-100> - Set playback volume
  stop           - Stop playback
"""
        return help_text
    
    # Implementation of BasePlugin abstract methods
    def _play_impl(self, args):
        """Play or resume Spotify playback"""
        if args:
            # Play specific track/playlist
            query = " ".join(args)
            return self.spotify.search_song_and_play(query)
        else:
            # Resume playback
            return self.spotify.play()
    
    def _pause_impl(self, args):
        """Pause Spotify playback"""
        return self.spotify.pause()
    
    def _stop_impl(self, args):
        """Stop Spotify playback - same as pause for Spotify"""
        return self.spotify.pause()
    
    def _next_impl(self, args):
        """Skip to next track"""
        return self.spotify.next_track()
    
    def _prev_impl(self, args):
        """Go to previous track"""
        return self.spotify.previous_track()
    
    def update_playback_info(self):
        """Update the plugin manager with current Spotify playback info"""
        try:
            track = self.spotify.current_playback()
            if track and track.get('item'):
                # Extract and convert data to the standard format expected by base class
                playback_info = {
                    'track_name': track['item']['name'],
                    'artist': track['item']['artists'][0]['name'] if track['item'].get('artists') else None,
                    'album': track['item']['album']['name'] if track['item'].get('album') else None,
                    'position': track.get('progress_ms', 0) / 1000.0,  # Convert to seconds
                    'duration': track['item']['duration_ms'] / 1000.0 if track['item'].get('duration_ms') else 0,  # Convert to seconds
                    'state': 'PLAYING' if track.get('is_playing', False) else 'PAUSED'
                }
                # Send standardized info to base class
                self.update_playback_state_from_info(playback_info)
        except Exception as e:
            print(f"Error updating playback info: {e}")
    
    def search(self, args):
        """Search for tracks on Spotify"""
        if not args:
            print("Usage: spotify search <query>")
            return []
        
        query = " ".join(args)
        try:
            results = self.spotify.search(q=query, type='track', limit=20)
            
            if not results or 'tracks' not in results or 'items' not in results['tracks'] or not results['tracks']['items']:
                print("No results found")
                return []
                    
            tracks = results['tracks']['items']
            display_items = []
            
            for track in tracks:
                artists = ", ".join(artist['name'] for artist in track['artists'])
                # Format: (display_text, track_id, metadata)
                display_items.append((
                    f"{track['name']} - {artists} [{track['album']['name']}]",
                    track['id'],
                    {
                        'artist': artists, 
                        'album': track['album']['name'],
                        'uri': track['uri']
                    }
                ))
                
            return display_items
        except Exception as e:
            print(f"Error searching Spotify: {e}")
            return []
    
    def playlists(self, args):
        """List Spotify playlists"""
        try:
            playlists = self.spotify.play_lists
            if not playlists:
                print("No playlists found or not logged in")
                return []
                
            display_items = []
            for playlist in playlists:
                # Format: (display_text, playlist_id, metadata)
                display_items.append((
                    f"{playlist['name']} ({playlist['tracks_total']} tracks)",
                    playlist['id'],
                    {
                        'uri': playlist['uri'],
                        'tracks': playlist['tracks_total']
                    }
                ))
                
            return display_items
        except Exception as e:
            print(f"Error listing playlists: {e}")
            return []

    def is_playing(self):
        """Check if Spotify is currently playing"""
        try:
            track = self.spotify.current_playback()
            return track is not None and track.get('is_playing', False)
        except Exception as e:
            print(f"Error checking Spotify playback: {e}")
            return False
            
    def get_current_playback(self):
        """Get current Spotify playback information"""
        try:
            track = self.spotify.current_playback()
            if track and track.get('item'):
                return {
                    'track_name': track['item']['name'],
                    'artist': track['item']['artists'][0]['name'],
                    'album': track['item']['album']['name'],
                    'duration_ms': track['item']['duration_ms'],
                    'progress_ms': track.get('progress_ms', 0),
                    'is_playing': track.get('is_playing', False)
                }
        except Exception as e:
            print(f"Error getting Spotify playback: {e}")
        return None
        
    def _set_volume_impl(self, volume):
        """Set the Spotify volume"""
        self.spotify.set_volume(volume)
        print(f"Spotify volume set to {volume}%")
        return True
    
    # Single hook method to handle source changes - stops Spotify when another source becomes active
    def on_source_changed_hook(self, data):
        """Handle source change events"""
        # If another source became active, pause Spotify
        if data['previous_source'] == 'spotify' and data['new_source'] != 'spotify':
            try:
                self.spotify.pause()
            except Exception as e:
                print(f"Error pausing Spotify: {e}")

    def play_track(self, track_data):
        """Play a track selected from search results"""
        try:
            # Unpack the track data
            display_text, track_id, metadata = track_data
            
            # Use the base plugin's state transition handler
            return self.handle_state_transition(
                action_func=lambda: self.spotify.play_song_by_id(track_id),
                wait_time=0.5,
                state_update={
                    'state': 'PLAYING',
                    'track_name': display_text.split(' - ')[0] if ' - ' in display_text else display_text,
                    'artist': metadata.get('artist')
                }
            )
        except Exception as e:
            print(f"Error playing track: {e}")
            return False
        
    def play_playlist(self, playlist_data):
        """Play a playlist selected from the list"""
        try:
            # Unpack the playlist data
            display_text, playlist_id, metadata = playlist_data
            
            def start_playlist():
                device_id = self.spotify.set_active_device()
                if device_id:
                    self.spotify.sp.start_playback(
                        device_id=device_id, 
                        context_uri=metadata['uri']
                    )
                    return True
                return False
            
            # Use the base plugin's state transition handler
            return self.handle_state_transition(
                action_func=start_playlist,
                wait_time=1.0,  # Give a bit more time for playlist to start
                state_update={'state': 'PLAYING'}
            )
        except Exception as e:
            print(f"Error playing playlist: {e}")
            return False