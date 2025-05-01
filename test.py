from modules import spotify
import environ

env = environ.Env()
environ.Env.read_env()

sp = spotify.Spotify(env)

print(sp.current_playback())