import re
from typing import Iterable
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

WEIGHTS = {'price': 0.45, 'seller_rating': 0.20, 'delivery': 0.15, 'product_rating': 0.20}


def _norm(v, lo, hi, reverse=False):
    if v is None: return 0.5
    if hi == lo: return 1.0
    x = (v - lo) / (hi - lo)
    return 1 - x if reverse else x


def offer_score(p, o):
    offers = p.get('offers', [])
    prices = [x['total_price'] for x in offers if x.get('total_price') is not None]
    sellers = [x['seller_rating'] for x in offers if x.get('seller_rating') is not None]
    dels = [x['delivery_days'] for x in offers if x.get('delivery_days') is not None]
    cost = _norm(o.get('total_price'), min(prices), max(prices), True) if prices else 0.5
    seller = _norm(o.get('seller_rating'), min(sellers), max(sellers)) if sellers and o.get('seller_rating') is not None else 0.5
    delivery = _norm(o.get('delivery_days'), min(dels), max(dels), True) if dels and o.get('delivery_days') is not None else 0.5
    product_rating = p.get('rating')
    product = (product_rating - 1) / 4 if product_rating is not None else 0.5
    score = 100 * (WEIGHTS['price'] * cost + WEIGHTS['seller_rating'] * seller + WEIGHTS['delivery'] * delivery + WEIGHTS['product_rating'] * product)
    return round(score, 2), {'price': round(cost, 3), 'seller_rating': round(seller, 3), 'delivery': round(delivery, 3), 'product_rating': round(product, 3)}


def rank_products(q, products):
    if not q or not products: return products
    corpus = [p.get('name', '') + ' ' + p.get('category', '') + ' ' + p.get('description', '') for p in products]
    vec = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
    mat = vec.fit_transform(corpus + [q])
    sims = cosine_similarity(mat[-1], mat[:-1]).flatten()
    out = []
    query_tokens = set(re.findall(r'[a-z0-9]+', q.lower()))
    for p, s in zip(products, sims):
        p = dict(p)
        text_tokens = set(re.findall(r'[a-z0-9]+', (p.get('name','') + ' ' + p.get('category','')).lower()))
        overlap = len(query_tokens & text_tokens)
        relevance = float(s) + (0.18 if overlap else 0)
        p['search_relevance'] = round(relevance, 4)
        p['ai_rank_score'] = round(relevance * 100, 2)
        out.append(p)
    return sorted(out, key=lambda x: x['search_relevance'], reverse=True)


def recommend_offer(p, preference='balanced'):
    offers = p.get('offers', [])
    if not offers: return None
    if preference == 'cost':
        o = min(offers, key=lambda x: x['total_price']); reason = 'Lowest total listed price.'
    elif preference == 'delivery':
        with_delivery = [x for x in offers if x.get('delivery_days') is not None]
        o = min(with_delivery or offers, key=lambda x: (x.get('delivery_days', 999), x['total_price']))
        reason = 'Fastest listed delivery with price used as a tie-breaker.'
    else:
        scored = [(offer_score(p, o)[0], o) for o in offers]
        _, o = max(scored, key=lambda x: x[0]); reason = 'Balances price, seller rating, delivery and product rating using weighted criteria.'
    score, components = offer_score(p, o)
    return {'product_id': p['id'], 'retailer': o['retailer'], 'total_price': o['total_price'], 'delivery_days': o.get('delivery_days'), 'seller_rating': o.get('seller_rating'), 'ai_score': score, 'criterion_contributions': components, 'weights': WEIGHTS, 'reason': reason}


def normalized_title(title: str) -> str:
    s = re.sub(r'[^a-z0-9]+', ' ', title.lower())
    s = re.sub(r'\b(amazon|flipkart|croma|reliance digital)\b', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def group_listings(listings):
    """Research-oriented cross-retailer entity matching.
    First tries shared strong model/identifier tokens, then TF-IDF cosine similarity.
    """
    if not listings: return []
    groups = []
    for item in listings:
        title = normalized_title(item.title)
        placed = False
        tokens = set(re.findall(r'[a-z0-9]+', title))
        strong = {t for t in tokens if len(t) >= 5 and any(c.isdigit() for c in t)}
        for g in groups:
            gt = g['_titles'][0]
            gtokens = set(re.findall(r'[a-z0-9]+', gt))
            if strong & {t for t in gtokens if len(t) >= 5 and any(c.isdigit() for c in t)}:
                g['listings'].append(item); g['_titles'].append(title); placed = True; break
            vec = TfidfVectorizer(analyzer='char_wb', ngram_range=(3,5), min_df=1)
            mat = vec.fit_transform([title, gt])
            sim = float(cosine_similarity(mat[0:1], mat[1:2])[0,0])
            shared = len(tokens & gtokens) / max(1, min(len(tokens), len(gtokens)))
            if sim >= 0.76 or (sim >= 0.68 and shared >= 0.55):
                g['listings'].append(item); g['_titles'].append(title); placed = True; break
        if not placed:
            groups.append({'_titles':[title], 'listings':[item]})
    result=[]
    for i,g in enumerate(groups,1):
        ls=g['listings']
        name=max((x.title for x in ls), key=len)
        result.append({'match_id': f'match-{i}', 'name': name, 'listings': ls})
    return result
