from flask import Flask, redirect, session, request, render_template, url_for
from dotenv import load_dotenv
import os
import requests
from requests import post, get
import urllib.parse
from datetime import datetime, timedelta
import logging
import pytz

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Loading environment var
load_dotenv()
client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")




def currently_playing(token):
    url = os.getenv("API_BASE_URL") + 'me/player/currently-playing'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    try:
        response = get(url, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        if response.status_code == 204:  # No content, means no track is currently playing
            logging.info("No track currently playing")
            return None
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching currently playing track: {e}")
        return None





def recently_played(token):
    url = os.getenv("API_BASE_URL") + 'me/player/recently-played?limit=10'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    try:
        response = get(url, headers=headers)
        response.raise_for_status()
        recent_tracks = response.json()

        # Get the local timezone
        local_tz = pytz.timezone("Asia/Kolkata")

        # Format the played_at timestamps
        for track in recent_tracks['items']:
            played_at_utc = track['played_at']
            played_at_dt = datetime.strptime(played_at_utc, '%Y-%m-%dT%H:%M:%S.%fZ')
            played_at_utc_dt = pytz.utc.localize(played_at_dt)
            played_at_local_dt = played_at_utc_dt.astimezone(local_tz)
            track['formatted_played_at'] = played_at_local_dt.strftime('%I:%M %p, %B %d, %Y')

        return recent_tracks
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching recently played tracks: {e}")
        return None

# Fetch recommendations based on recently played tracks
def get_recommendations(token, track_ids):
    url = f"https://api.spotify.com/v1/recommendations?seed_tracks={','.join(track_ids)}&limit=5"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    try:
        response = get(url, headers=headers)
        response.raise_for_status()
        return response.json()['tracks']  # Returns recommended tracks
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching recommendations: {e}")
        return None

import requests

def add_related_tracks_to_queue(token):
    # Fetch currently playing track
    current_track = currently_playing(token)
    
    if not current_track:
        print("No track is currently playing. Fetching recently played tracks instead.")
        recent_tracks = recently_played(token)
        
        if not recent_tracks:
            print("Failed to fetch recently played tracks.")
            return
        
        # Use the most recently played track as seed if available
        seed_track_uri = recent_tracks['items'][0]['track']['uri']
    else:
        # Use currently playing track as seed
        seed_track_uri = current_track['item']['uri']

    # Fetch recommendations based on seed track
    url = f'https://api.spotify.com/v1/recommendations?seed_tracks={seed_track_uri}&limit=5'
    headers = {
        'Authorization': f'Bearer {token}'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        recommended_tracks = response.json()['tracks']
        
        if recommended_tracks:
            # Add each recommended track to the queue
            for track in recommended_tracks:
                track_uri = track['uri']
                add_track_to_queue(token, track_uri)
        else:
            print("No recommended tracks found.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching recommendations: {e}")

def add_track_to_queue(token, track_uri):
    url = f'https://api.spotify.com/v1/me/player/queue?uri={track_uri}'
    headers = {
        'Authorization': f'Bearer {token}'
    }

    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()

        if response.status_code == 204:
            print(f"Successfully added track {track_uri} to queue.")
        else:
            print(f"Failed to add track to queue: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error adding track to queue: {e}")


def check_playback_status(token):
    url = "https://api.spotify.com/v1/me/player"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data['is_playing']:
            return True
        else:
            print("No active playback")
            return False
    else:
        print(f"Error checking playback: {response.status_code}")
        return False





def get_top_tracks(token):
    headers = {
        'Authorization': f'Bearer {token}',
        
    }
    
    # Get the top tracks for the last 30 days (short term)
    response = requests.get( os.getenv("API_BASE_URL") +'me/top/tracks?time_range=short_term&limit=10', headers=headers)
    
    if response.status_code == 200:
        return response.json().get('items', [])
    else:
        logging.error(f"Error fetching top tracks: {response.status_code} - {response.text}")
        return []

def get_similar_tracks(top_tracks, token):
    headers = {
        'Authorization': f'Bearer {token}',
        
    }
    
    # Extract track IDs from the top tracks
    seed_tracks = [track['id'] for track in top_tracks[:5]]  # Using the top 5 tracks as seeds
    
    # Get recommendations based on seed tracks
    response = requests.get(os.getenv("API_BASE_URL") +f'recommendations?seed_tracks={",".join(seed_tracks)}&limit=10', headers=headers)
    
    if response.status_code == 200:
        return response.json().get('tracks', [])
    else:
        logging.error(f"Error fetching recommendations: {response.status_code} - {response.text}")
        return []






def create_playlist(user_id, playlist_name, token):
    headers = {
        'Authorization': f'Bearer {token}',
        
    }
    
    data = {
        'name': playlist_name,
        'description': 'Playlist based on your top songs in the last 30 days',
        'public': False
    }
    
    # Create a new playlist
    response = requests.post(os.getenv("API_BASE_URL") + f'users/{user_id}/playlists', headers=headers, json=data)
    
    if response.status_code == 201:
        return response.json().get('id')
    else:
        logging.error(f"Error creating playlist: {response.status_code} - {response.text}")
        return None

def add_tracks_to_playlist(playlist_id, track_uris, token):
    headers = {
        'Authorization': f'Bearer {token}',
        
    }
    
    data = {
        'uris': track_uris
    }
    
    # Add tracks to the playlist
    response = requests.post(os.getenv("API_BASE_URL") +f'playlists/{playlist_id}/tracks', headers=headers, json=data)
    
    if response.status_code == 201:
        logging.info("Tracks successfully added to playlist")
    else:
        logging.error(f"Error adding tracks to playlist: {response.status_code} - {response.text}")





@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    scope = 'user-read-private user-read-email user-read-currently-playing user-read-playback-state user-modify-playback-state  user-read-recently-played user-top-read playlist-modify-private user-read-playback-position'
    params = {
        'client_id': client_id,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': os.getenv("REDIRECT_URI"),
        'show_dialog': True
    }
    auth_url = f"{os.getenv('AUTH_URL')}?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    if 'error' in request.args:
        return f"Error: {request.args['error']}"
    
    if 'code' in request.args:
        request_body = {
            'code': request.args['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': os.getenv("REDIRECT_URI"),
            'client_id': client_id,
            'client_secret': client_secret
        }
        try:
            response = post(os.getenv("TOKEN_URL"), data=request_body)
            response.raise_for_status()
            token_info = response.json()
            session['access_token'] = token_info['access_token']
            session['refresh_token'] = token_info['refresh_token']
            session['expires_at'] = datetime.now().timestamp() + token_info['expires_in']
            return redirect(url_for('get_playlists'))
        except requests.exceptions.RequestException as e:
            logging.error(f"Error in callback: {e}")
            return "Error: Unable to get token. Please try again."


@app.route('/search', methods=['GET'])
def search():
    if 'access_token' not in session:
        return redirect('/login')

    query = request.args.get('query')
    search_type = request.args.get('type')

    if not query or not search_type:
        return "Please provide a search query and type.", 400

    token = session['access_token']
    url = os.getenv("API_BASE_URL") + "search"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    params = {
        'q': query,
        'type': search_type,
        'limit': 10
    }

    response = get(url, headers=headers, params=params)
    search_results = response.json()

    # Pass results to the template
    return render_template("search_results.html", results=search_results, search_type=search_type)


@app.route('/playlists')
def get_playlists():
    if 'access_token' not in session:
        return redirect(url_for('login'))

    if datetime.now().timestamp() > session['expires_at']:
        return redirect(url_for('refresh_token'))
    
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }

    try:
        # Get user info
        user_info_url = "https://api.spotify.com/v1/me"
        user_response = get(user_info_url, headers=headers)
        user_response.raise_for_status()
        user_info = user_response.json()

        # Get currently playing track
        current_track = currently_playing(session['access_token'])
        logging.debug(f"Current track: {current_track}")

        # Get recently played tracks
        recent_tracks = recently_played(session['access_token'])
        logging.debug(f"Recent tracks: {recent_tracks}")

        # Get playlists
        playlist_response = get(os.getenv("API_BASE_URL") + 'me/playlists', headers=headers)
        playlist_response.raise_for_status()
        playlists = playlist_response.json()

        # Extract only the needed information (name, link, and image)
        playlists_info = []
        for playlist in playlists.get('items', []):  # Safely access 'items'
            if playlist:  # Check if playlist is not None
                playlists_info.append({
                    "name": playlist.get("name", "Unknown Playlist"),
                    "link": playlist.get("external_urls", {}).get("spotify", "#"),
                    "image": playlist.get("images", [{}])[0].get("url") if playlist.get("images") else None
                })

        return render_template(
            "playlists.html",
            user=user_info,
            current_track=current_track,
            recent_tracks=recent_tracks,
            playlists=playlists_info
        )

    except requests.exceptions.RequestException as e:
        logging.error(f"Error in get_playlists: {e}")
        return "An error occurred while fetching your Spotify data. Please try logging in again."
    
    except Exception as e:
        logging.error(f"Unexpected error in get_playlists: {e}")
        return "An unexpected error occurred. Please try again later."

@app.route('/refresh_token')
def refresh_token():
    if 'refresh_token' not in session:
        return redirect(url_for('login'))
    if datetime.now().timestamp() > session['expires_at']:
        req_body = {
            'grant_type': 'refresh_token',
            'refresh_token': session['refresh_token'],
            'client_id': client_id,
            'client_secret': client_secret
        }
        try:
            response = post(os.getenv("TOKEN_URL"), data=req_body)
            response.raise_for_status()
            new_token_info = response.json()
            session['access_token'] = new_token_info['access_token']
            session['expires_at'] = datetime.now().timestamp() + new_token_info['expires_in']
        except requests.exceptions.RequestException as e:
            logging.error(f"Error in refresh_token: {e}")
            return redirect(url_for('login'))

    return redirect(url_for('get_playlists'))
  
@app.route('/playback', methods=['POST'])
def control_playback():
    if 'access_token' not in session:
        return redirect('/login')

    headers = {
        'Authorization': f'Bearer {session["access_token"]}',
        'Content-Type': 'application/json'
    }

    # Get currently playing track details
    current_track = currently_playing(session['access_token'])
    
    # Initialize response variable
    response = None

    if current_track is None:
        return "No track is currently playing.", 400

    # Extract context_uri and position from the currently playing track
    context_uri = current_track.get("context", {}).get("uri")
    position = current_track.get("progress_ms", 0)

    # Determine action based on whether a track is currently playing or paused
    action = 'play' if current_track['is_playing'] is False else 'pause'

    if action == 'play':
        data = {
            "context_uri": context_uri,
            "offset": {"position": 0},
            "position_ms": position
        }
        response = requests.put('https://api.spotify.com/v1/me/player/play', headers=headers, json=data)
    elif action == 'pause':
        response = requests.put('https://api.spotify.com/v1/me/player/pause', headers=headers)

    # Check response status and log any issues

    logging.info(f"Playback {action} action successful")
    return redirect(url_for('get_playlists'))  # Redirect back to playlist page after success
    
@app.route('/recommend_playlist', methods=['POST'])
def recommend_playlist():
    if 'access_token' not in session:
        return redirect('/login')

    token = session['access_token']
    
    # Get the current user's profile info (user_id)
    user_info = requests.get('https://api.spotify.com/v1/me', headers={'Authorization': f'Bearer {token}'}).json()
    user_id = user_info['id']
    
    # Step 1: Get the user's top tracks for the last 30 days
    top_tracks = get_top_tracks(token)
    
    if not top_tracks:
        return "No top tracks found.", 400
    
    # Step 2: Get similar tracks based on the top tracks
    similar_tracks = get_similar_tracks(top_tracks, token)
    
    if not similar_tracks:
        return "No similar tracks found.", 400
    
    # Step 3: Create a new playlist
    playlist_name = "Recommended Playlist Based on Your Top Songs"
    playlist_id = create_playlist(user_id, playlist_name, token)
    
    if not playlist_id:
        return "Failed to create playlist.", 500
    
    # Step 4: Add the recommended tracks to the playlist
    track_uris = [track['uri'] for track in similar_tracks]
    add_tracks_to_playlist(playlist_id, track_uris, token)
    
    return redirect(url_for('get_playlists'))


@app.route('/queue_related', methods=['POST'])
def queue_related_tracks():
    if 'access_token' not in session:
        return redirect('/login')

    token = session['access_token']

    # Get recently played tracks
    recent_tracks = recently_played(token)
    if not recent_tracks:
        return "Could not retrieve recently played tracks", 400

    # Get track IDs from the recently played tracks
    track_ids = [track['track']['id'] for track in recent_tracks['items'][:5]]  # Select top 5 tracks

    # Fetch recommendations based on those tracks
    recommended_tracks = get_recommendations(token, track_ids)
    if not recommended_tracks:
        return "Could not fetch recommended tracks", 400

    # Add recommended tracks to the queue
    for track in recommended_tracks:
        success = add_track_to_queue(token, track['uri'])
        
    return redirect(url_for('get_playlists')) 



def start_app():
    app.run(host='0.0.0.0',port=5000,debug=True)



if __name__=="__main__":
    start_app()
