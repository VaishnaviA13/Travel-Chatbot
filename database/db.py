import sqlite3
import os
import hashlib
import csv
from models.itinerary import Itinerary

DB_PATH = 'itineraries.db'
USERS_CSV = 'users.csv'
ITINERARIES_CSV = 'itineraries.csv'
CHAT_CSV = 'chat_messages.csv'

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