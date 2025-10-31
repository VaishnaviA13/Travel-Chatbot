import sqlite3
import os
import hashlib
import csv
import requests
import json
import io
from models.itinerary import Itinerary

DB_PATH = 'itineraries.db'
USERS_CSV = 'users.csv'
ITINERARIES_CSV = 'itineraries.csv'
CHAT_CSV = 'chat_messages.csv'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GIST_ID_ENV = os.getenv('GIST_ID')
GIST_ID_FILE = '.gist_id'


def _get_stored_gist_id():
    if GIST_ID_ENV:
        return GIST_ID_ENV
    if os.path.isfile(GIST_ID_FILE):
        try:
            with open(GIST_ID_FILE, 'r') as f:
                return f.read().strip()
        except Exception:
            return None
    return None


def init_gist():
    """Ensure a gist exists and return its id. Returns None if no GITHUB_TOKEN is configured."""
    if not GITHUB_TOKEN:
        return None
    headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    gist_id = _get_stored_gist_id()
    # validate existing gist
    if gist_id:
        try:
            r = requests.get(f'https://api.github.com/gists/{gist_id}', headers=headers, timeout=6)
            if r.ok:
                return gist_id
        except Exception:
            pass

    # create a new private gist with initial CSV headers
    initial_files = {
        USERS_CSV: {'content': 'id,username,password_hash\n'},
        ITINERARIES_CSV: {'content': 'id,user_id,name,content,destination,duration,budget,preferences,user_name,is_public,num_people\n'},
        CHAT_CSV: {'content': 'id,itinerary_id,role,content\n'}
    }
    payload = {'description': 'Travel Itinerary AI data backup', 'public': False, 'files': initial_files}
    try:
        resp = requests.post('https://api.github.com/gists', headers=headers, json=payload, timeout=10)
        if resp.ok:
            gist_id = resp.json().get('id')
            try:
                with open(GIST_ID_FILE, 'w') as f:
                    f.write(gist_id)
            except Exception:
                pass
            return gist_id
    except Exception:
        pass
    return None


def _read_gist_file_content(gist_id, filename):
    if not GITHUB_TOKEN or not gist_id:
        return None
    headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    try:
        r = requests.get(f'https://api.github.com/gists/{gist_id}', headers=headers, timeout=6)
        if not r.ok:
            return None
        files = r.json().get('files', {})
        f = files.get(filename)
        if f:
            return f.get('content', '')
    except Exception:
        return None
    return None


def _patch_gist_file(gist_id, filename, content):
    if not GITHUB_TOKEN or not gist_id:
        return False
    headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    payload = {'files': {filename: {'content': content}}}
    try:
        r = requests.patch(f'https://api.github.com/gists/{gist_id}', headers=headers, json=payload, timeout=8)
        return r.ok
    except Exception:
        return False


def _append_row_to_gist_csv(gist_id, filename, data, headers):
    """Append a CSV row (dict) to a file inside the gist. Creates file with headers if missing."""
    if not GITHUB_TOKEN or not gist_id:
        return False
    # Read current content
    existing = _read_gist_file_content(gist_id, filename)
    if existing is None:
        # create with headers
        existing = ','.join(headers) + '\n'
    # Build CSV row
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    # If existing has only headers and no newline, ensure writer doesn't write header again
    # We will always append only the row
    row = {k: ('' if data.get(k) is None else data.get(k)) for k in headers}
    # ensure proper CSV formatting for fields that contain newlines/commas
    out_row_io = io.StringIO()
    csv_writer = csv.DictWriter(out_row_io, fieldnames=headers)
    csv_writer.writerow(row)
    row_text = out_row_io.getvalue()
    # Append to existing content
    if not existing.endswith('\n'):
        existing = existing + '\n'
    new_content = existing + row_text
    return _patch_gist_file(gist_id, filename, new_content)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS itineraries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        content TEXT,
        destination TEXT,
        duration INTEGER,
        budget TEXT,
        preferences TEXT,
        user_name TEXT,
        is_public BOOLEAN DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        itinerary_id INTEGER,
        role TEXT,
        content TEXT,
        FOREIGN KEY (itinerary_id) REFERENCES itineraries (id)
    )''')
    # Try to add user_id column if not exists (for migration)
    try:
        c.execute('ALTER TABLE itineraries ADD COLUMN user_id INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    try:
        c.execute('ALTER TABLE itineraries ADD COLUMN is_public BOOLEAN DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists
    try:
        c.execute('ALTER TABLE itineraries ADD COLUMN num_people INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def save_to_csv(filename, data, headers):
    file_exists = os.path.isfile(filename)
    with open(filename, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)
    # If GITHUB_TOKEN is configured, also append/update the gist file
    try:
        gist_id = init_gist()
        if gist_id:
            _append_row_to_gist_csv(gist_id, filename, data, headers)
    except Exception:
        # Fail silently and keep local CSV as the primary fallback
        pass

def create_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                  (username, hash_password(password)))
        conn.commit()
        user_id = c.lastrowid
        # Save to CSV
        save_to_csv(USERS_CSV, {'id': user_id, 'username': username, 'password_hash': hash_password(password)}, ['id', 'username', 'password_hash'])
    except sqlite3.IntegrityError:
        user_id = None
    conn.close()
    return user_id

def authenticate_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id FROM users WHERE username = ? AND password_hash = ?',
              (username, hash_password(password)))
    user = c.fetchone()
    conn.close()
    return user[0] if user else None

def save_itinerary(itinerary, user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO itineraries (user_id, name, content, destination, duration, budget, preferences, user_name, is_public, num_people)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, itinerary.name, itinerary.content, itinerary.destination, itinerary.duration,
               itinerary.budget, itinerary.preferences, itinerary.user_name, itinerary.is_public, itinerary.num_people))
    itinerary_id = c.lastrowid
    conn.commit()
    conn.close()
    # Save to CSV
    save_to_csv(ITINERARIES_CSV, {
        'id': itinerary_id,
        'user_id': user_id,
        'name': itinerary.name,
        'content': itinerary.content,
        'destination': itinerary.destination,
        'duration': itinerary.duration,
        'budget': itinerary.budget,
        'preferences': itinerary.preferences,
        'user_name': itinerary.user_name,
        'is_public': itinerary.is_public,
        'num_people': itinerary.num_people
    }, ['id', 'user_id', 'name', 'content', 'destination', 'duration', 'budget', 'preferences', 'user_name', 'is_public', 'num_people'])
    return itinerary_id

def get_itineraries(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM itineraries WHERE user_id = ?', (user_id,))
    rows = c.fetchall()
    conn.close()
    return [Itinerary.from_dict({
        'id': row[0],
        'name': row[2],
        'content': row[3],
        'destination': row[4],
        'duration': row[5],
        'budget': row[6],
        'preferences': row[7],
        'user_name': row[8],
        'is_public': row[9] if len(row) > 9 else False,
        'num_people': row[10] if len(row) > 10 else None
    }) for row in rows]

def get_public_itineraries():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM itineraries WHERE is_public = 1')
    rows = c.fetchall()
    conn.close()
    return [Itinerary.from_dict({
        'id': row[0],
        'name': row[2],
        'content': row[3],
        'destination': row[4],
        'duration': row[5],
        'budget': row[6],
        'preferences': row[7],
        'user_name': row[8],
        'is_public': row[9] if len(row) > 9 else False,
        'num_people': row[10] if len(row) > 10 else None
    }) for row in rows]

def save_chat_message(itinerary_id, role, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO chat_messages (itinerary_id, role, content) VALUES (?, ?, ?)',
              (itinerary_id, role, content))
    chat_id = c.lastrowid
    conn.commit()
    conn.close()
    # Save to CSV
    save_to_csv(CHAT_CSV, {'id': chat_id, 'itinerary_id': itinerary_id, 'role': role, 'content': content}, ['id', 'itinerary_id', 'role', 'content'])

def get_chat_history(itinerary_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT role, content FROM chat_messages WHERE itinerary_id = ? ORDER BY id', (itinerary_id,))
    rows = c.fetchall()
    conn.close()
    return [{'role': row[0], 'content': row[1]} for row in rows]