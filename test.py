import mpv
import time

def create_streaming_client(url):
    # Create a mpv player instance
    player = mpv.MPV(
        ytdl=False,  # Disable youtube-dl
        input_default_bindings=True,
        input_vo_keyboard=True,
        osc=True
    )
    
    # Set properties for streaming
    player['cache'] = True
    player['cache-secs'] = 10  # Buffer 10 seconds
    player['demuxer-max-back-bytes'] = '10M'
    player['demuxer-readahead-secs'] = 5
    
    # Load the stream
    player.play(url)
    
    # Wait until player is ready
    while not player.core_idle:
        time.sleep(0.1)
    
    return player

create_streaming_client()