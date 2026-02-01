# Overview
The script hosted in this repo will downloads logos from fanart.tv for the artists in your Plex library, makes the pictures square, and sets them as the artist picture in Plex.

You can either run the script in your local python environment (for which you'll need to edit the variables in the script itself), or run it inside a Docker container for which you can find the compose file in this repo, as well the environment variables example file.

# Details
The script does the following:

1. Connects to your Plex instance to get a list of your artists (it'll skip artists without a MusicBrainz ID)
2. It uses this list to connect to fanart.tv where it will download the most popular HD ClearLOGO for each artist
3. It will make each downloaded picture square, and add a black background to it
4. It will set this square picture as the artist's picture in Plex
5. Logs and stats will be available at the end of each run.

# Notes
There's no undo function, so make sure you've taken a backup/snapshot of Plex before running this script, unless you're absolutely sure you want to replace the artist photos with their logos.

# Screenshots
![alt text](https://github.com/joakimkingstrom/plex-artist-logo-sync/blob/main/screenshot1.png)
![alt text](https://github.com/joakimkingstrom/plex-artist-logo-sync/blob/main/screenshot2.png)