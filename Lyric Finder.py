import spotipy, os, string, asyncio
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import lyricsgenius
import threading, time, logging, concurrent.futures
from musixmatch import Musixmatch

load_dotenv()

genius = lyricsgenius.Genius(os.getenv('GENIUS_TOKEN'),skip_non_songs=True,verbose=False, excluded_terms=["(Remix)", "(Live)"], remove_section_headers=True)
musixmatch = Musixmatch(os.getenv('MUSIXMATCH_KEY'))
dictionary = {}
array = []
search = ''

class Song:
    title = ''
    artist = ''
    lyrics = ''

    words = 0
    percentage = 0.0

    def __init__(self, title_, artist_):
        self.title = title_
        self.artist = artist_

    def get_title(self):
        return self.title
    def get_artist(self):
        return self.artist


    def find_lyrics(self, search_phrase, Continue = False):
        self.lyrics=self.lyrics.translate(str.maketrans('', '', string.punctuation))
        self.lyrics = self.lyrics.lower()
        search_phrase = search_phrase.lower()
        words = search_phrase.split()
        if search_phrase in self.lyrics:
            self.words = len(search_phrase)
            self.percentage = 1.0
            print("< found in ", self.get_title(), "-" ,  self.get_artist(), ">")
            if not Continue:
                inp = input("keep searching? (?/n)")
                if inp == 'n':
                    exit()

class LyricGrabber:
    def __init__(self):
        self.value = 0
        self._lock = threading.Lock()

    def locked_update(self, name):
        logging.info("Thread %s: starting update", name)
        logging.debug("Thread %s about to lock", name)
        local_copy = 0
        with self._lock:
            logging.debug("Thread %s has lock", name)
            local_copy = self.value

            local_copy += 1
            time.sleep(0.1)
            self.value = local_copy
            logging.debug("Thread %s about to release lock", name)
        global array
        song = array[index]
        if get_lyrics_in_spotify_track(song):
            song.find_lyrics(search)
        logging.debug("Thread %s after release", name)
        logging.info("Thread %s: finishing update", name)

    async def async_with_lyrics(self):
        global array, search
        lock = asyncio.Lock()
        local_val = 0
        async with lock:
            local_val = self.value
            self.value +=1
        song = array[local_val]
        if get_lyrics_in_spotify_track(song):
            #logging.info(str(local_val) + ") found lyrics: " + song.title + " - " + song.artist)
            song.find_lyrics(search)

    async def run(self):
        await self.async_with_lyrics()


    def get_lyrics(self, index):
        print("getting lyrics")
        global array
        song = array[index]
        if get_lyrics_in_spotify_track(song):
            song.find_lyrics(search)
        
def get_spotify_tracks():
    scope = 'user-library-read'
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope))
    arr = []
    dic = {}
    offset = 0
    limit = 50
    count = 0
    while True:
        results = sp.current_user_saved_tracks(limit, offset)
        if len(results['items']) == 0:
            print("we're at the end here")
            break
        for idx, item in enumerate(results['items']):
            track = item['track']
            #print(count, track['artists'][0]['name'], " – ", track['name'])
            arr.append(Song(track['name'], track['artists'][0]['name']))
            if dic.get(track['name'].lower()) == None:
                dic[track['name'].lower()] = []
            dic[track['name'].lower()].append(arr[-1])
            #print(track['name'].lower())
            count += 1
        offset += limit
    return arr, dic

    thing_to_remove = ["remastered", "-"]

def get_az_lyrics(artist, song):
    artist = artist.lower().replace(" ", "")
    song = song.lower().replace(" ", "")
    url = "https://www.azlyrics.com/lyrics/"+artist+"/"+song+".html"

    req = requests.get(url, headers=headers)
    soup = BeautifulSoup(req.content, "html.parser")
    lyrics = soup.find_all("div", attrs={"class": None, "id": None})
    if not lyrics:
        return {'Error': 'Unable to find '+song+' by '+artist}
    elif lyrics:
        lyrics = [x.getText() for x in lyrics]
        return lyrics


def search_azlyrics(song):
    lyrics = get_az_lyrics(song.artist, song.title)
    if type(lyrics) == type([]):
        string = ''
        for para in lyrics:
            string += para.strip()
        song.lyrics = string
        return True
    return False

def search_genius(song):
    try:
        artist = (genius.search_artist(song.get_artist(), 0, get_full_info=False))
        song_id = (genius.search_artist_songs(artist.id, song.get_title() )['songs'][0]['id'])
        song.lyrics = genius.lyrics(song_id).strip()
        song.lyrics = song.lyrics.replace('\n',' ')
        return True
    except:
        return False

def search_musixmatch_long(song):
    results = (musixmatch.track_search(q_track=song.get_title(),q_artist=song.get_artist(), page_size=10, page=1, s_track_rating='desc'))
    for i in results['message']['body']['track_list']:
        ii = i['track']
        print(i['track']['track_name'])
        print(song.title.strip())
        #if ii['track_name'] == song.title and i[i['artist_name'] == song.artist:
        if True:
            print(ii['track_id'])
            if(ii['has_lyrics']):
                print(musixmatch.track_lyrics_get(5850832)['message']['body']['lyrics']['lyrics_body'].strip())

def search_musixmatch(song):
    for i in musixmatch.matcher_lyrics_get(song.title, song.artist)['message']['body']['lyrics']:
              print(i)
    print(musixmatch.matcher_lyrics_get(song.title, song.artist)['message']['body']['lyrics']['lyrics_body'])

def get_lyrics_in_spotify_track(song):
    if search_musixmatch(song):
        return True
    elif search_azlyrics(song):
        return True
    elif search_genius(song) :
        return True
    else:
        logging.info("No lyrics found for " + song.get_title() + " by " + song.get_artist())
        try_again = False
        to_remove = [" -", " (with", "(from", "(feat"]
        to_replace = [(': ', ':'),('&', 'and'), ('-', ' ')]
        for rem in to_remove:
            if rem in song.get_title():
                song.title = song.title.split(rem)[0]
                try_again = True
        if not try_again:
            for rep in to_replace:
                if rep[0] in song.get_title():
                    song.title = song.title.replace(rep[0],rep[1])
                    try_again = True
        if try_again:
            logging.info("attempting with new title: " + song.title)
            get_lyrics_in_spotify_track(song)
        return False
 
def songs_with_same_title(search_phrase, dictionary):
    print("> searching for songs with same title...")
    title_songs = dictionary.get(search)
    if title_songs != None:
        print("found ",len(title_songs), " songs")
        for song in title_songs:
            if get_lyrics_in_spotify_track(song):
                song.find_lyrics(search) 
        
        print(". . . . .")   
    else:
        print("no songs found with matching title")
        
        print(". . . . .")
        return False

def thread_function(name):

    logging.info("Thread %s: starting", name)

    time.sleep(2)

    logging.info("Thread %s: finishing", name)

def serial(): 
    search = "border steady your boats"

    search = "happiness"
    #search = input("Enter search phrase: ").lower()

    #songs_with_same_title(search, dictionary)
    logging.info("searching the rest of the library")
    for song in array:
        if get_lyrics_in_spotify_track(song):
            logging.info("found lyrics: " + song.title + " - " + song.artist)
            song.find_lyrics(search)

def multithread(no_of_threads):
    database = LyricGrabber()
    logging.info("> searching through library using %d threads", no_of_threads)
    while database.value < len(array):
        with concurrent.futures.ThreadPoolExecutor(max_workers=no_of_threads) as executor:
            for index in range(no_of_threads):
                executor.submit(asyncio.run, database.run())
    logging.info("Testing update. Ending value is %d.", database.value)

def filter(word):
    words_to_ignore = [] #['the', 'a', 'of', 'i', 'you', 'or', 'me', 'her']
    output = []
    print(word)
    for w in word:
        if w not in words_to_ignore:
            output.append(w)
    if len(output) <= 0:
        print("< poor choice of search term - rejected >")
        exit()
    return output

def songs_with_similar_title(search_phrase, dictionary):
    print("> searching for songs with similar titles...")
    words = filter(search_phrase.split())
    count = 0
    print(words)
    for key in dictionary:
        for w in words:
            if (w + " ") in key or (" " + w) in key:
                for song in dictionary[key]:
                    #logging.info("looking at song <" + song.title + " - " + song.artist + ">")
                    count += 1
                    if get_lyrics_in_spotify_track(song):
                        song.find_lyrics(search, True) 
    if count == 0:
        print("no songs found with a similar title")
    print(". . . . .")
    cont = input("so stop? (y/?)")
    if cont ==  "y":
        exit()

def init():
    global array, dictionary
    logging.info("loading spotify library...")
    array, dictionary = get_spotify_tracks()
    output = "spotify library loaded: " + str(len(array)) + " songs"
    logging.info(output)

if __name__ == "__main__":
    format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=format, level=logging.INFO,
                        datefmt="%H:%M:%S")

    #5print(musixmatch.track_lyrics_get(5850832)['message']['body']['lyrics']['lyrics_body'].strip())

    init()
    search = input("Enter search phrase: ").lower()

    search = search.translate(str.maketrans('', '', string.punctuation))

    print("search phrase: ", search)
    songs_with_same_title(search, dictionary)
    #songs_with_similar_title(search, dictionary)
    multithread(10)
    #main()
    
