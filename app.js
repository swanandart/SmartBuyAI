const API = 'http://127.0.0.1:8000/api';
let products = [], selected = null, pref = 'balanced';
const money = n => n == null ? '—' : '₹' + Number(n).toLocaleString('en-IN', {maximumFractionDigits:0});
const esc = s => String(s ?? '').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
async function api(path, options={}) { const r=await fetch(API+path,options); if(!r.ok) throw new Error('API '+r.status); return r.json(); }
function placeholder(title='Product image') { return 'data:image/svg+xml;charset=UTF-8,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="900" height="600"><rect width="100%" height="100%" fill="#eef3f7"/><text x="50%" y="50%" text-anchor="middle" dominant-baseline="middle" fill="#64748b" font-family="Arial" font-size="28">${title}</text></svg>`); }
function bestOffer(p){ return (p.offers||[]).reduce((a,b)=>(!a||b.total_price<a.total_price)?b:a,null); }
function sortProducts(arr){
 const mode=document.getElementById('sort').value; const copy=[...arr];
 if(mode==='price') copy.sort((a,b)=>(bestOffer(a)?.total_price||Infinity)-(bestOffer(b)?.total_price||Infinity));
 else if(mode==='rating') copy.sort((a,b)=>(b.rating||0)-(a.rating||0));
 else if(mode==='discount') copy.sort((a,b)=>Math.max(...(b.offers||[]).map(x=>x.discount_pct||0))-Math.max(...(a.offers||[]).map(x=>x.discount_pct||0)));
 else copy.sort((a,b)=>(b.search_relevance||b.ai_best_offer?.ai_score||0)-(a.search_relevance||a.ai_best_offer?.ai_score||0));
 return copy;
}
function filteredProducts(){
 const max=document.getElementById('priceFilter').value, ret=document.getElementById('retailerFilter').value, rat=document.getElementById('ratingFilter').value, del=document.getElementById('deliveryFilter').value, cat=document.getElementById('categoryFilter').value;
 return products.filter(p=>{const offers=p.offers||[]; return (cat==='All'||p.category===cat) && (ret==='all'||offers.some(o=>o.retailer===ret)) && (max==='all'||offers.some(o=>o.total_price<=+max)) && (rat==='all'||(p.rating||0)>=+rat) && (del==='all'||offers.some(o=>(o.delivery_days||999)<=+del));});
}
function renderCards(){
 const grid=document.getElementById('grid'), empty=document.getElementById('empty');
 const arr=sortProducts(filteredProducts()); document.getElementById('count').textContent=arr.length+' live matches';
 grid.innerHTML=arr.map(p=>{
   const o=bestOffer(p), ai=p.ai_best_offer;
   return `<article class="card" data-id="${p.id}"><div class="pic"><img src="${esc(p.image_url||o?.image_url||placeholder())}" alt="${esc(p.name)}" onerror="this.src='${placeholder('Image unavailable')}'"></div><div class="body"><div class="tag">${esc(p.category||'Product')} · LIVE</div><h3>${esc(p.name)}</h3><div class="rating">${'★'.repeat(Math.round(p.rating||0))}${'☆'.repeat(Math.max(0,5-Math.round(p.rating||0)))} ${p.rating?esc(p.rating):'—'}</div><div class="price-line"><strong>${money(o?.total_price)}</strong><span>${o?esc(o.retailer):'No offer'}</span></div><div class="meta">${o?.delivery_days?`Delivery ${esc(o.delivery_days)} day(s)`:'Delivery unavailable'} · ${o?.discount_pct?esc(o.discount_pct)+'% off':''}</div><div class="card-actions"><button class="primary" data-select="${p.id}">Compare offers</button>${ai?`<span class="ai-badge">AI ${esc(ai.ai_score)}/100</span>`:''}</div></div></article>`;
 }).join('');
 empty.classList.toggle('hidden',arr.length>0);
 if(!arr.length) grid.innerHTML='';
 document.querySelectorAll('[data-select]').forEach(b=>b.onclick=()=>selectProductById(+b.dataset.select));
}
async function selectProductById(id){ const p=products.find(x=>x.id===id); if(p) await selectProduct(p); }
async function selectProduct(p){
 selected=p; document.getElementById('compareTitle').textContent=p.name; document.getElementById('compareImage').src=p.image_url||bestOffer(p)?.image_url||placeholder(); document.getElementById('compareRating').textContent=p.rating?`★★★★★ ${p.rating} / 5`:'Rating unavailable';
 document.getElementById('compareSpecs').innerHTML=[p.brand?`Brand: ${esc(p.brand)}`:'Live retailer listing',p.category?`Category: ${esc(p.category)}`:'Category unavailable',`${p.offers?.length||0} retailer offer(s) found`,'Price and availability refreshed from configured sources'].map(x=>`<li>${x}</li>`).join('');
 document.getElementById('heroProduct').textContent=p.name; const score=p.ai_best_offer?.ai_score; document.getElementById('heroScore').textContent=score!=null?`${score} / 100`:'— / 100'; document.querySelector('.meter span').style.width=(score||0)+'%'; renderOffers(); await updateRecommendation(); await updateHistory(); document.getElementById('compare').scrollIntoView({behavior:'smooth',block:'start'});
}
function renderOffers(){
 const offers=[...(selected?.offers||[])].sort((a,b)=>a.total_price-b.total_price);
 document.getElementById('offers').innerHTML=offers.length?offers.map(o=>`<div class="offer"><div><strong>${esc(o.retailer)}</strong><div style="font-size:12px;color:#64748b">${o.seller_rating?`Seller ${esc(o.seller_rating)}`:'Seller rating unavailable'}${o.delivery_days?` · ${esc(o.delivery_days)} day delivery`:''}</div></div><div style="text-align:right"><b>${money(o.total_price)}</b><div><a class="primary" style="display:inline-block;text-decoration:none;margin-top:5px;padding:7px 10px" target="_blank" rel="noopener" href="${esc(o.product_url||'#')}">View retailer</a></div></div></div>`).join(''):'<div class="panel">No live offers were returned for this product.</div>';
 document.getElementById('tableBody').innerHTML=offers.map(o=>`<tr><td>${esc(o.retailer)}</td><td>${money(o.total_price-(o.shipping||0))}</td><td>${money(o.shipping||0)}</td><td>${o.delivery_days?esc(o.delivery_days)+' day(s)':'—'}</td><td>${o.seller_rating||'—'}</td><td><b>${money(o.total_price)}</b></td></tr>`).join('');
}
async function updateRecommendation(){
 if(!selected){document.getElementById('recommendation').textContent='Search a product to receive an AI recommendation.';return;}
 try{const data=await api(`/products/${selected.id}/recommend?preference=${pref}`); document.getElementById('recommendation').textContent=`${data.retailer} at ${money(data.total_price)} — AI score ${data.ai_score}/100.`; document.getElementById('insight').textContent=data.reason;}catch(e){document.getElementById('recommendation').textContent='Recommendation becomes available after the live result is stored.';}
}
async function updateHistory(){
 if(!selected)return; try{const h=await api(`/products/${selected.id}/history`);document.getElementById('currentPrice').textContent=money(h.current);document.getElementById('lowestPrice').textContent=money(h.lowest);document.getElementById('averagePrice').textContent=money(h.average);}catch(e){document.getElementById('currentPrice').textContent='—';document.getElementById('lowestPrice').textContent='—';document.getElementById('averagePrice').textContent='—';}
}
async function loadProducts(){
 const q=document.getElementById('q').value.trim();
 if(!q){ products=[]; renderCards(); document.getElementById('searchMessage').textContent='Search a product to compare live retailer offers. Demo products are disabled.'; return; }
 document.getElementById('searchMessage').textContent='Querying configured retailer APIs and matching equivalent listings…';
 try{
   const data=await api('/search?q='+encodeURIComponent(q)); products=data.products||[]; renderCards();
   const configured=(data.connectors||[]).filter(x=>x.configured).map(x=>x.retailer); const errors=(data.errors||[]).length;
   document.getElementById('searchMessage').textContent=products.length?`Live results: ${data.retailer_results} retailer listing(s) → ${products.length} matched product group(s). Connected: ${configured.join(', ')||'none'}.`:`No live results returned. Connected: ${configured.join(', ')||'none'}. Configure retailer credentials/feed URLs in .env.`;
   if(errors) toast('One or more retailer connectors returned an error.');
   if(products.length) await selectProduct(products[0]);
 }catch(e){ products=[]; renderCards(); document.getElementById('searchMessage').textContent='Backend unavailable. Start the FastAPI server, then search again.'; toast('Could not connect to SmartBuy AI backend'); }
}
async function renderWatch(){
 let arr=[]; try{arr=(await api('/watchlist')).watchlist||[]}catch(e){}
 document.getElementById('watchCount').textContent=arr.length+' saved'; document.getElementById('watchEmpty').classList.toggle('hidden',arr.length>0);
 document.getElementById('watchList').innerHTML=arr.map(x=>`<article class="watch-row"><div class="watch-row-top"><div><div class="watch-name">${esc(x.name)}</div><div class="watch-meta">Current ${money(x.current_price)} · Target ${money(x.target_price)}</div></div><span class="watch-alert">${x.current_price<=x.target_price?'Target reached':'Watching'}</span></div><button class="remove" data-remove-watch="${x.id}">Remove</button></article>`).join('');
 document.querySelectorAll('[data-remove-watch]').forEach(b=>b.onclick=async()=>{try{await api('/watchlist/'+b.dataset.removeWatch,{method:'DELETE'});renderWatch();}catch(e){}});
}
function toast(t){const x=document.getElementById('toast');x.textContent=t;x.classList.add('show');setTimeout(()=>x.classList.remove('show'),2200)}
async function connectorStatus(){try{const d=await api('/connectors'); const configured=d.connectors.filter(x=>x.configured).length; document.getElementById('connectorStatus').textContent=`${configured}/${d.connectors.length} retailer connector(s) configured`; }catch(e){document.getElementById('connectorStatus').textContent='Backend not connected';}}

document.getElementById('searchForm').onsubmit=e=>{e.preventDefault();loadProducts()};
document.getElementById('sort').onchange=renderCards;
['priceFilter','retailerFilter','ratingFilter','deliveryFilter','categoryFilter'].forEach(id=>document.getElementById(id).onchange=renderCards);
document.querySelectorAll('[data-pref]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-pref]').forEach(x=>x.classList.remove('active'));b.classList.add('active');pref=b.dataset.pref;updateRecommendation()});
document.getElementById('watchForm').onsubmit=async e=>{e.preventDefault(); if(!selected){document.getElementById('watchStatus').textContent='Search and select a live product first.';return;} const target=+document.getElementById('targetPrice').value;const current=bestOffer(selected)?.total_price;if(!target||!current)return;try{await api('/watchlist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:selected.id,target_price:target,current_price:current})});document.getElementById('watchStatus').textContent='Price-drop alert saved.';renderWatch();toast('Price alert saved');}catch(e){document.getElementById('watchStatus').textContent='Could not save alert. Make sure the backend is running.';}};
const modal=document.getElementById('modal');document.getElementById('signin').onclick=()=>modal.classList.add('show');document.getElementById('closeModal').onclick=()=>modal.classList.remove('show');document.getElementById('demoSignin').onclick=()=>{modal.classList.remove('show');toast('Guest mode — account system not enabled in Stage 1')};modal.onclick=e=>{if(e.target===modal)modal.classList.remove('show')};
(async()=>{renderCards();await connectorStatus();await renderWatch();document.getElementById('searchMessage').textContent='Search a product to compare live retailer offers. No demo products are loaded.';})();
