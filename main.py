# main.py
from modules.player import MusicPlayer
from modules.cli import MusicPlayerCLI
import environ

env = environ.Env()
environ.Env.read_env()

def main():
    """Main entry point for the music player"""
    player = MusicPlayer(env)
    cli = MusicPlayerCLI(player)
    cli.run()

if __name__ == "__main__":
    main()