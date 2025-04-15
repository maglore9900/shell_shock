import spotipy
from spotipy.oauth2 import SpotifyOAuth
from requests.exceptions import ConnectionError, HTTPError
import time
import functools
import socket

def handle_spotify_errors_and_device(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        attempts = 3
        for attempt in range(attempts):
            try:
                # Fetch the active device before calling the function
                device_id = self.set_active_device()
                if device_id is None:
                    print("No active device found.")
                    return None

                # Inject the device_id into the kwargs
                kwargs['device_id'] = device_id

                return func(self, *args, **kwargs)
            except (spotipy.exceptions.SpotifyException, ConnectionError, HTTPError) as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if "token" in str(e).lower():
                    self.refresh_token()
                time.sleep(2)  # Wait before retrying
            except Exception as e:
                print(f"Unexpected error: {e}")
                break
    return wrapper

class Spotify:
    def __init__(self, env):
        spotify_client_id = env("SPOTIFY_CLIENT_ID", default=None)
        spotify_client_secret = env("SPOTIFY_CLIENT_SECRET", default=None)
        spotify_redirect_uri = env("SPOTIFY_REDIRECT_URI", default=None)
        if not (spotify_client_id and spotify_client_secret and spotify_redirect_uri):
            print("Spotify environment variables missing. Skipping Spotify initialization.")
            return
        self.auth_manager = SpotifyOAuth(
            client_id=env("spotify_client_id"),
            client_secret=env("spotify_client_secret"),
            redirect_uri=env("spotify_redirect_uri"),
            scope="user-modify-playback-state user-read-playback-state user-library-modify user-library-read"
        )
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)
        self.play_lists = self.get_user_playlists()
        
    def set_active_device(self):
        try:
            devices = self.sp.devices()
            hostname = socket.gethostname()
            if devices['devices']:
                # active_device_id = devices['devices'][0]['id']
                for each in devices['devices']:
                    if each["name"].lower() in hostname.lower():
                        active_device_id = each["id"]
                return active_device_id
            else:
                return None
        except spotipy.exceptions.SpotifyException as e:
            print(f"Error fetching devices: {e}")
            return None

    def get_active_device(self):
        try:
            devices = self.sp.devices()
            hostname = socket.gethostname()
            if devices['devices']:
                active_device_id = devices['devices'][0]['id']
                return active_device_id
            else:
                return None
        except spotipy.exceptions.SpotifyException as e:
            print(f"Error fetching devices: {e}")
            return None

    def refresh_token(self):
        try:
            self.sp = spotipy.Spotify(auth_manager=self.auth_manager)
        except spotipy.exceptions.SpotifyException as e:
            print(f"Failed to refresh token: {e}")
    
    @handle_spotify_errors_and_device
    def play(self, device_id=None):
        result = self.current_playback()
        status = None
        if result:
            status = result.get('is_playing')
        if not status:
            if device_id:
                self.sp.start_playback(device_id=device_id)
            else:
                print("No active device found.")

    @handle_spotify_errors_and_device
    def pause(self, device_id=None):
        result = self.current_playback()
        status = result.get('is_playing')
        if status:
            if device_id:
                self.sp.pause_playback(device_id=device_id)
            else:
                print("No active device found.")
            
    @handle_spotify_errors_and_device       
    def next_track(self, device_id=None):
        if device_id:
            self.sp.next_track(device_id=device_id)
        else:
            print("Failed to skip to the next track")
            
    @handle_spotify_errors_and_device
    def previous_track(self, device_id=None):
        if device_id:
            self.sp.previous_track(device_id=device_id)
        else:
            print("Failed to go to the previous track")
            
    @handle_spotify_errors_and_device
    def favorite_current_song(self, device_id=None):
        if device_id:
            current_track = self.current_playback()
            if current_track and current_track['item']:
                track_id = current_track['item']['id']
                self.sp.current_user_saved_tracks_add([track_id])
                print(f"Added '{current_track['item']['name']}' to favorites")
            else:
                print("No song is currently playing")
        else:
            print("Failed to add current song to favorites")
            
    @handle_spotify_errors_and_device
    def search_song_and_play(self, song_name, device_id=None):
        try:
            results = self.sp.search(q='track:' + song_name, type='track')
            if results['tracks']['items']:
                track_uri = results['tracks']['items'][0]['uri']
                if device_id:
                    self.sp.start_playback(device_id=device_id, uris=[track_uri])
                else:
                    print("No active device found. Please start Spotify on a device and try again.")
            else:
                print(f"No results found for song: {song_name}")
        except Exception as e:
            print(f"Failed to search and play song '{song_name}': {e}")
            
    @handle_spotify_errors_and_device
    def search_artist_and_play(self, artist_name, device_id=None):
        try:
            results = self.sp.search(q='artist:' + artist_name, type='artist')
            if results['artists']['items']:
                artist_uri = results['artists']['items'][0]['uri']
                if device_id:
                    self.sp.start_playback(device_id=device_id, context_uri=artist_uri)
                else:
                    print("No active device found. Please start Spotify on a device and try again.")
            else:
                print(f"No results found for artist: {artist_name}")
        except Exception as e:
            print(f"Failed to search and play artist '{artist_name}': {e}")
            
    @handle_spotify_errors_and_device
    def search_album_and_play(self, album_name, device_id=None):
        try:
            results = self.sp.search(q='album:' + album_name, type='album')
            if results['albums']['items']:
                album_uri = results['albums']['items'][0]['uri']
                if device_id:
                    self.sp.start_playback(device_id=device_id, context_uri=album_uri)
                else:
                    print("No active device found. Please start Spotify on a device and try again.")
            else:
                print(f"No results found for album: {album_name}")
        except Exception as e:
            print(f"Failed to search and play album '{album_name}': {e}")

    def get_artist_info(self, artist_id):
        """
        Retrieve detailed information about a specified artist.
        
        Args:
            artist_id (str): The Spotify ID of the artist
        """
        try:
            return self.sp.artist(artist_id)
        except Exception as e:
            print(f"Failed to fetch artist info: {e}")
            return None

    def get_user_playlists(self):
        """
        Retrieve all playlists for the authenticated user.
        
        Returns:
            list: A list of dictionaries containing playlist information
        """
        results = []
        playlists = []
        
        # Initial request
        response = self.sp.current_user_playlists(limit=50)
        playlists.extend(response['items'])
        
        # Paginate through all playlists
        while response['next']:
            response = self.sp.next(response)
            playlists.extend(response['items'])
        
        for playlist in playlists:
            playlist_info = {
                'id': playlist['id'],
                'name': playlist['name'],
                'owner': playlist['owner']['display_name'],
                'public': playlist['public'],
                'collaborative': playlist['collaborative'],
                'tracks_total': playlist['tracks']['total'],
                'description': playlist['description'],
                'uri': playlist['uri'],
                'snapshot_id': playlist['snapshot_id'],
                'href': playlist['href'],
                'images': playlist['images'] if 'images' in playlist else []
            }
            results.append(playlist_info)
        
        return results

    def get_playlist_tracks(self, playlist_id):
        """
        Retrieve all tracks with detailed information from a specified playlist.
        
        Args:
            playlist_id (str): The Spotify ID of the playlist
            
        Returns:
            list: A list of dictionaries containing detailed track information
        """
        results = []
        tracks = []
        
        # Initial request
        response = self.sp.playlist_items(
            playlist_id,
            fields='items.track.id,items.track.name,items.track.artists,items.track.album,items.track.duration_ms,'
                'items.track.popularity,items.track.explicit,items.track.external_ids,items.track.external_urls,'
                'items.track.href,items.track.uri,items.track.is_local,items.track.preview_url,items.track.available_markets,'
                'items.added_at,items.added_by,next',
            additional_types=['track'],
            limit=100
        )
        
        if 'items' in response:
            tracks.extend(response['items'])
        
        # Paginate through all tracks
        while response['next']:
            response = self.sp.next(response)
            if 'items' in response:
                tracks.extend(response['items'])
        
        # Process tracks in batches for audio features (max 100 per request)
        valid_track_ids = []
        track_id_to_index = {}
        
        # First pass - collect valid track IDs and build results without audio features
        for index, item in enumerate(tracks):
            # Skip None tracks (can happen with local files or removed tracks)
            if not item['track']:
                continue
                
            track = item['track']
            
            # Only collect IDs for valid tracks (not local, has an ID)
            if track['id'] and not track['is_local']:
                valid_track_ids.append(track['id'])
                track_id_to_index[track['id']] = index
            
            # Extract artist information
            artists = []
            for artist in track['artists']:
                artists.append({
                    'id': artist['id'],
                    'name': artist['name'],
                    'uri': artist['uri']
                })
            
            # Extract album information
            album = {
                'id': track['album']['id'],
                'name': track['album']['name'],
                'release_date': track['album']['release_date'],
                'total_tracks': track['album']['total_tracks'],
                'type': track['album']['album_type'],
                'uri': track['album']['uri'],
                'images': track['album']['images'] if 'images' in track['album'] else []
            }
            
            # Build track info dictionary
            track_info = {
                'id': track['id'],
                'name': track['name'],
                'artists': artists,
                'album': album,
                'duration_ms': track['duration_ms'],
                'popularity': track['popularity'],
                'explicit': track['explicit'],
                'external_ids': track['external_ids'],
                'uri': track['uri'],
                'preview_url': track['preview_url'],
                'is_local': track['is_local'],
                'added_at': item['added_at'],
                'added_by': item['added_by']['id'] if 'added_by' in item and item['added_by'] else None,
                'audio_features': None  # Will be populated later for valid tracks
            }
            
            results.append(track_info)
        
        # Now fetch audio features in batches of 100 max (Spotify API limit)
        for i in range(0, len(valid_track_ids), 100):
            batch_ids = valid_track_ids[i:i+100]
            try:
                # Get audio features for this batch
                audio_features_batch = self.sp.audio_features(batch_ids)
                
                # Process each track's audio features
                for j, features in enumerate(audio_features_batch):
                    if features:
                        track_id = batch_ids[j]
                        track_index = track_id_to_index[track_id]
                        
                        results[track_index]['audio_features'] = {
                            'danceability': features.get('danceability'),
                            'energy': features.get('energy'),
                            'key': features.get('key'),
                            'loudness': features.get('loudness'),
                            'mode': features.get('mode'),
                            'speechiness': features.get('speechiness'),
                            'acousticness': features.get('acousticness'),
                            'instrumentalness': features.get('instrumentalness'),
                            'liveness': features.get('liveness'),
                            'valence': features.get('valence'),
                            'tempo': features.get('tempo'),
                            'time_signature': features.get('time_signature')
                        }
            except Exception as e:
                print(f"Error fetching batch audio features: {str(e)}")
                # Continue with the next batch even if this one fails
                
        return results

    def get_songs_from_playlists(self):
        """
        Retrieve all songs from the user's playlists.
        
        Returns:
            list: A list of dictionaries containing detailed track information
        """
        all_songs = []
        playlists_info = []
        playlists = sp.get_user_playlists()
        for i, playlist in enumerate(playlists):
            playlist_id = playlist["id"]
            playlist_name = playlist["name"]
            print(f"\nProcessing playlist {i+1}/{len(playlists)}: {playlist_name}")
            try:
                # Get tracks for this playlist
                playlist_tracks = sp.get_playlist_tracks(playlist_id)
                
                if not playlist_tracks:
                    print(f"No tracks returned for playlist: {playlist_name}")
                    continue
                    
                # Add playlist context to each track
                for track in playlist_tracks:
                    track["playlist_id"] = playlist_id
                    track["playlist_name"] = playlist_name
                    all_songs.append(track)
                    
                print(f"Added {len(playlist_tracks)} tracks from playlist: {playlist_name}")
                
            except Exception as e:
                print(f"Error processing playlist {playlist_name}: {str(e)}")
                # Optional: prompt to continue or retry this playlist
                sp.refresh_token()
                retry = input("Retry this playlist? (y/n): ")
                if retry.lower() == 'y':
                    # Decrease counter to retry this playlist
                    i -= 1
                    continue
            
            print(f"Progress saved. Total tracks so far: {len(all_songs)}")
            return all_songs
    
    def get_liked_songs(self):
        """
        Retrieve all saved/liked tracks for the authenticated user.
        
        Args:
            sp: The Spotify client instance
            
        Returns:
            list: A list of dictionaries containing track information
        """
        results = []
        tracks = []
        
        # Initial request
        limit = 50  # Max is 50 for this endpoint
        offset = 0
        response = self.sp.current_user_saved_tracks(limit=limit, offset=offset)
        
        # First batch
        if 'items' in response:
            tracks.extend(response['items'])
        
        # Paginate through all saved tracks
        total = response['total']
        while offset + limit < total:
            offset += limit
            print(f"Fetching liked songs: {offset}/{total}")
            try:
                response = self.sp.current_user_saved_tracks(limit=limit, offset=offset)
                if 'items' in response:
                    tracks.extend(response['items'])
                # Add a small delay to avoid rate limiting
                time.sleep(0.5)
            except Exception as e:
                print(f"Error fetching liked songs at offset {offset}: {e}")
                time.sleep(5)  # Longer delay on error
        
        # Process the tracks
        for item in tracks:
            track = item['track']
            
            # Extract artist information
            artists = []
            for artist in track['artists']:
                artists.append({
                    'id': artist['id'],
                    'name': artist['name'],
                    'uri': artist['uri']
                })
            
            # Extract album information
            album = {
                'id': track['album']['id'],
                'name': track['album']['name'],
                'release_date': track['album']['release_date'],
                'total_tracks': track['album']['total_tracks'],
                'type': track['album']['album_type'],
                'uri': track['album']['uri'],
                'images': track['album']['images'] if 'images' in track['album'] else []
            }
            
            # Build track info dictionary
            track_info = {
                'id': track['id'],
                'name': track['name'],
                'artists': artists,
                'album': album,
                'duration_ms': track['duration_ms'],
                'popularity': track['popularity'],
                'explicit': track['explicit'],
                'external_ids': track.get('external_ids', {}),
                'uri': track['uri'],
                'preview_url': track.get('preview_url'),
                'is_local': track.get('is_local', False),
                'added_at': item['added_at'],
                'source': 'Liked Songs'  # To distinguish from playlist tracks
            }
            
            results.append(track_info)
        
        return results

    def get_history(self, limit=50):
        response = self.sp.current_user_recently_played(limit=limit)
        list_of_tracks = []
        seen = set()  # To track unique entries
        
        for each in response['items']:
            track_info = f"Artist: {each['track']['artists'][0]['name']} - {each['track']['name']}"
            
            # Only add if we haven't seen this track before
            if track_info not in seen:
                seen.add(track_info)
                list_of_tracks.append(track_info)
        
        # Reverse the list before returning
        list_of_tracks.reverse()
        
        return list_of_tracks

    def current_playback(self):
        result = self.sp.current_playback()
        return result

    def search(self, q, type='track', limit=10):
        results = self.sp.search(q=q, type=type, limit=limit)
        return results

    @handle_spotify_errors_and_device
    def play_song_by_id(self, track_id, device_id=None):
        # Check if this is a track URI or just an ID
        if not track_id.startswith('spotify:'):
            track_uri = [f"spotify:track:{track_id}"]
        else:
            track_uri = [track_id]
        
        # device_id = self.set_active_device()
        if device_id:
            self.sp.start_playback(device_id=device_id, uris=track_uri)
        else:
            print("No active device found for playback")

    @handle_spotify_errors_and_device
    def set_volume(self, volume, device_id=None):
        try:
            self.sp.volume(volume)
        except spotipy.exceptions.SpotifyException as e:
            print(f"Failed to set volume: {e}")