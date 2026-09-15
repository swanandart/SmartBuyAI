import asyncio
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .connectors import FlipkartConnector, AmazonConnector, CromaConnector, RelianceDigitalConnector
from .research import group_listings, rank_products, recommend_offer, offer_score

BASE = os.path.dirname(os.path.dirname(__file__))
DB = os.path.join(BASE, 'data', 'smartbuy.db')
load_dotenv(os.path.join(BASE, '.env'))

app = FastAPI(title='SmartBuy AI API', version='2.0.0', description='Live-retailer-ready research-oriented shopping decision and price comparison API')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

CONNECTORS = [FlipkartConnector(), AmazonConnector(), CromaConnector(), RelianceDigitalConnector()]

class WatchRequest(BaseModel):
    product_id: int
    target_price: float = Field(gt=0)
    current_price: float = Field(gt=0)


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = db()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        external_key TEXT UNIQUE,
        name TEXT NOT NULL,
        category TEXT,
        rating REAL,
        image_url TEXT,
        description TEXT,
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        retailer TEXT NOT NULL,
        external_id TEXT,
        total_price REAL,
        shipping REAL DEFAULT 0,
        delivery_days INTEGER,
        seller_rating REAL,
        product_rating REAL,
        rating_count INTEGER,
        discount_pct REAL,
        image_url TEXT,
        product_url TEXT,
        availability INTEGER,
        updated_at TEXT,
        UNIQUE(retailer, external_id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    );
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        recorded_at TEXT NOT NULL,
        price REAL NOT NULL,
        retailer TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );
    CREATE TABLE IF NOT EXISTS watchlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        target_price REAL NOT NULL,
        current_price REAL NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );
    ''')
    con.commit(); con.close()

init_db()


def listing_dict(x):
    return {
        'retailer': x.retailer, 'external_id': x.external_id, 'title': x.title,
        'price': x.price, 'mrp': x.mrp, 'shipping': x.shipping, 'delivery_days': x.delivery_days,
        'seller_rating': x.seller_rating, 'product_rating': x.product_rating, 'rating_count': x.rating_count,
        'discount_pct': x.discount_pct, 'image_url': x.image_url, 'product_url': x.product_url,
        'brand': x.brand, 'category': x.category, 'availability': x.availability, 'description': x.description
    }


def persist_groups(groups):
    con = db(); now = datetime.now(timezone.utc).isoformat()
    products=[]
    for group in groups:
        ls=group['listings']
        canonical=max(ls, key=lambda x: len(x.title))
        signature='||'.join(sorted(x.retailer+':'+x.external_id for x in ls)); external_key='match:'+hashlib.sha256(signature.encode()).hexdigest()[:24]
        row=con.execute('SELECT id FROM products WHERE external_key=?',(external_key,)).fetchone()
        if row: pid=row['id']; con.execute('UPDATE products SET name=?,category=?,rating=?,image_url=?,description=?,updated_at=? WHERE id=?',(canonical.title,canonical.category,canonical.product_rating,canonical.image_url,canonical.description,now,pid))
        else:
            cur=con.execute('INSERT INTO products(external_key,name,category,rating,image_url,description,updated_at) VALUES(?,?,?,?,?,?,?)',(external_key,canonical.title,canonical.category,canonical.product_rating,canonical.image_url,canonical.description,now)); pid=cur.lastrowid
        for x in ls:
            total=(x.price or 0)+(x.shipping or 0)
            con.execute('''INSERT INTO offers(product_id,retailer,external_id,total_price,shipping,delivery_days,seller_rating,product_rating,rating_count,discount_pct,image_url,product_url,availability,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(retailer,external_id) DO UPDATE SET product_id=excluded.product_id,total_price=excluded.total_price,shipping=excluded.shipping,delivery_days=excluded.delivery_days,seller_rating=excluded.seller_rating,product_rating=excluded.product_rating,rating_count=excluded.rating_count,discount_pct=excluded.discount_pct,image_url=excluded.image_url,product_url=excluded.product_url,availability=excluded.availability,updated_at=excluded.updated_at''',
                (pid,x.retailer,x.external_id,total,x.shipping,x.delivery_days,x.seller_rating,x.product_rating,x.rating_count,x.discount_pct,x.image_url,x.product_url,1 if x.availability is not False else 0,now))
            if x.price is not None: con.execute('INSERT INTO price_history(product_id,recorded_at,price,retailer) VALUES(?,?,?,?)',(pid,now,x.price,x.retailer))
        products.append(pid)
    con.commit(); con.close(); return products


def product_dict(row, con):
    p=dict(row)
    offers=[dict(x) for x in con.execute('SELECT * FROM offers WHERE product_id=? AND availability=1 ORDER BY total_price',(p['id'],)).fetchall()]
    for o in offers:
        o['retailer_url']=o.get('product_url')
    p['offers']=offers
    p['rating']=p.get('rating') or (max([o.get('product_rating') or 0 for o in offers], default=0) or None)
    if offers:
        scored=[]
        for o in offers:
            score, components=offer_score(p,o); o['ai_score']=score; o['criterion_contributions']=components
        p['best_offer']=min(offers,key=lambda x:x['total_price'])
        p['ai_best_offer']=max(offers,key=lambda x:x.get('ai_score',0))
    else:
        p['best_offer']=None; p['ai_best_offer']=None
    return p


@app.get('/api/health')
def health():
    return {'status':'ok','service':'SmartBuy AI API','mode':'live-retailer-ready','database':'SQLite','research_model':'TF-IDF + cross-retailer entity matching + multi-criteria scoring'}

@app.get('/api/connectors')
def connectors_status():
    return {'connectors':[c.status() for c in CONNECTORS]}

@app.get('/api/search')
async def live_search(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=20)):
    results = await asyncio.gather(*(c.search(q) for c in CONNECTORS), return_exceptions=True)
    listings=[]; errors=[]
    for c,res in zip(CONNECTORS,results):
        if isinstance(res,Exception): errors.append({'retailer':c.name,'error':str(res)}); continue
        listings.extend(res)
    groups=group_listings(listings)
    pids=persist_groups(groups) if groups else []
    con=db(); products=[]
    for pid in pids:
        row=con.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
        if row: products.append(product_dict(row,con))
    con.close()
    products=rank_products(q,products)[:limit]
    return {'query':q,'count':len(products),'products':products,'retailer_results':len(listings),'errors':errors,'connectors':[c.status() for c in CONNECTORS]}

@app.get('/api/products')
def products(q: str = '', category: str = 'All', retailer: str = 'All', max_price: Optional[float] = None, min_rating: Optional[float] = None, max_delivery: Optional[int] = None):
    con=db(); rows=con.execute('SELECT * FROM products ORDER BY updated_at DESC').fetchall(); data=[product_dict(r,con) for r in rows]; con.close()
    if q.strip(): data=rank_products(q,data)
    if category!='All': data=[p for p in data if p.get('category')==category]
    if retailer!='All': data=[p for p in data if any(o['retailer']==retailer for o in p['offers'])]
    if max_price is not None: data=[p for p in data if p['offers'] and min(o['total_price'] for o in p['offers'])<=max_price]
    if min_rating is not None: data=[p for p in data if (p.get('rating') or 0)>=min_rating]
    if max_delivery is not None: data=[p for p in data if any((o.get('delivery_days') or 999)<=max_delivery for o in p['offers'])]
    return {'count':len(data),'products':data}

@app.get('/api/products/{product_id}')
def product(product_id:int):
    con=db(); row=con.execute('SELECT * FROM products WHERE id=?',(product_id,)).fetchone()
    if not row: con.close(); return {'error':'Product not found'}
    p=product_dict(row,con); con.close(); return p

@app.get('/api/products/{product_id}/recommend')
def recommendation(product_id:int, preference:str=Query('balanced',pattern='^(balanced|cost|delivery)$')):
    con=db(); row=con.execute('SELECT * FROM products WHERE id=?',(product_id,)).fetchone()
    if not row: con.close(); return {'error':'Product not found'}
    p=product_dict(row,con); con.close(); return recommend_offer(p,preference)

@app.get('/api/products/{product_id}/history')
def history(product_id:int):
    con=db(); rows=con.execute('SELECT recorded_at,price,retailer FROM price_history WHERE product_id=? ORDER BY recorded_at',(product_id,)).fetchall(); con.close(); vals=[r['price'] for r in rows]
    return {'product_id':product_id,'history':[dict(r) for r in rows],'lowest':min(vals) if vals else None,'average':round(sum(vals)/len(vals),2) if vals else None,'current':vals[-1] if vals else None}

@app.post('/api/watchlist')
def add_watch(req:WatchRequest):
    con=db(); exists=con.execute('SELECT id FROM products WHERE id=?',(req.product_id,)).fetchone()
    if not exists: con.close(); return {'error':'Search and compare the live product before adding it to watchlist'}
    cur=con.execute('INSERT INTO watchlist(product_id,target_price,current_price) VALUES(?,?,?)',(req.product_id,req.target_price,req.current_price)); con.commit(); new_id=cur.lastrowid; con.close(); return {'id':new_id,'message':'Price alert saved'}

@app.get('/api/watchlist')
def get_watchlist():
    con=db(); rows=con.execute('''SELECT w.id,w.product_id,w.target_price,w.current_price,p.name FROM watchlist w JOIN products p ON p.id=w.product_id ORDER BY w.created_at DESC''').fetchall(); con.close(); return {'watchlist':[dict(r) for r in rows]}

@app.delete('/api/watchlist/{watch_id}')
def delete_watch(watch_id:int):
    con=db(); con.execute('DELETE FROM watchlist WHERE id=?',(watch_id,)); con.commit(); con.close(); return {'message':'Watch item removed'}

@app.get('/api/research/metrics')
def research_metrics():
    return {'research_question':'Can cross-retailer entity matching plus a multi-criteria AI scoring model select a better purchase option than the lowest-price baseline?','method':'Retailer adapters → normalized listing schema → TF-IDF/character similarity entity matching → transparent multi-criteria scoring','criteria':{'price':0.45,'seller_rating':0.20,'delivery':0.15,'product_rating':0.20},'evaluation_plan':['Compare AI ranking with lowest-price baseline','Measure top-1 agreement','Measure average utility score','Evaluate product-match precision/recall on labeled listing pairs','Run sensitivity analysis on criterion weights'],'limitations':['Live data depends on approved retailer APIs/feeds and credentials','Croma and Reliance Digital adapters require an approved JSON feed or partner API URL','Retailer APIs may impose quotas and commercial/affiliate conditions']}
