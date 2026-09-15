"""Initialize an empty Stage 1 database schema. No demo products or fake prices are inserted."""
import os, sqlite3
BASE=os.path.dirname(os.path.dirname(__file__)); DB=os.path.join(BASE,'data','smartbuy.db')
os.makedirs(os.path.dirname(DB),exist_ok=True)
con=sqlite3.connect(DB)
con.executescript('''DROP TABLE IF EXISTS watchlist; DROP TABLE IF EXISTS price_history; DROP TABLE IF EXISTS offers; DROP TABLE IF EXISTS products;
CREATE TABLE products(id INTEGER PRIMARY KEY AUTOINCREMENT, external_key TEXT UNIQUE, name TEXT NOT NULL, category TEXT, rating REAL, image_url TEXT, description TEXT, updated_at TEXT);
CREATE TABLE offers(id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, retailer TEXT NOT NULL, external_id TEXT, total_price REAL, shipping REAL DEFAULT 0, delivery_days INTEGER, seller_rating REAL, product_rating REAL, rating_count INTEGER, discount_pct REAL, image_url TEXT, product_url TEXT, availability INTEGER, updated_at TEXT, UNIQUE(retailer,external_id), FOREIGN KEY(product_id) REFERENCES products(id));
CREATE TABLE price_history(id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, recorded_at TEXT NOT NULL, price REAL NOT NULL, retailer TEXT, FOREIGN KEY(product_id) REFERENCES products(id));
CREATE TABLE watchlist(id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, target_price REAL NOT NULL, current_price REAL NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(product_id) REFERENCES products(id));''')
con.commit(); con.close(); print(f'Empty SmartBuy AI Stage 1 database created: {DB}')
