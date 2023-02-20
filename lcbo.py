import psycopg2

def query(sql_address, q):
    conn = psycopg2.connect(sql_address)
    cur = conn.cursor()
    cur.execute(q)
    tbl = cur.fetchall()
    conn.close()
    return tbl

def closest_stores(sql_address, lat, lon, max_distance=20, max_stores=3):
    get_cols = ['latitude', 'longitude', 'lcbo_id', 'name', 'address', 'city', 'phone_number']
    q = f"""
            SELECT *, 6371.0*2.0*asin(sqrt(sin(0.5*(lat2-lat1))^2 + cos(lat1)*cos(lat2)*sin(0.5*(lon2-lon1))^2  )) AS distance FROM (
                SELECT {', '.join(get_cols)}, 
                radians({lat}) AS lat1, radians({lon}) AS lon1, 
                radians(latitude) AS lat2, 
                radians(longitude) AS lon2 FROM lcbo.stores
            ) AS dum
            ORDER BY distance
            LIMIT {max_stores};
    
    """
    stores = query(sql_address, q)    
    stores = [dict(zip(get_cols,store)) for store in stores ]

    return stores


def get_top_wines_from_store(sql_address, lcbo_id, min_sentiment=20, pos_limit = 0.7, neg_limit=0.3, limit = 50, pos_price_diff_range=[0.95,100], neg_price_diff_range = [0, 1.05]):
    q = f"""DROP TABLE IF EXISTS curated;
        CREATE TEMP TABLE curated AS
        select * FROM (
            with viv as (
                WITH ont AS (
                    SELECT distinct vivino_id, sku from lcbo.store_{lcbo_id}
                )
                SELECT reviews, positivity, price as user_price, vivino.reviews.vivino_id, ont.sku, "wine.country" as country FROM vivino.reviews
                INNER JOIN ont
                ON ont.vivino_id = vivino.reviews.vivino_id 
            ),
            wine as (
                SELECT price, vivino_id, sku, made_in FROM lcbo.wine
            )
            select viv.reviews, viv.positivity, viv.vivino_id, viv.sku, price, user_price, country, made_in
            FROM viv 
            INNER JOIN wine
            ON viv.vivino_id = wine.vivino_id AND viv.sku = wine.sku
            where made_in LIKE CONCAT('%', country, '%')
            
        ) as dum;

        with positives as (
            SELECT vivino_id, sku, COUNT(*) as pos from curated
            where positivity > {pos_limit}  and user_price > price*{pos_price_diff_range[0]} and user_price < price*{pos_price_diff_range[1]}  
            group by vivino_id, sku
        ),
        negatives as (
            SELECT vivino_id, sku, COUNT(*) as neg from curated
            where positivity < {neg_limit}  and user_price > price*{neg_price_diff_range[0]} and user_price < price*{neg_price_diff_range[1]}  
            group by vivino_id, sku
        )
        select positives.vivino_id, positives.sku, coalesce(pos,0) as pos, coalesce(neg,0) as neg
        FROM positives FULL JOIN negatives
        ON positives.vivino_id = negatives.vivino_id and positives.sku = negatives.sku
        where pos + neg >= {min_sentiment}
        order by CAST(pos as float)/(pos+neg) desc
        limit {limit}
        ;
        """
    #Returns (vivino_id, SKU, pos-sentiment, neg-sentiment)
    sentiments = query(sql_address,q)
    cols = ['vivino_id', 'sku', 'pos','neg']
    sentiments = [dict(zip(cols,s)) for s in sentiments ]
    return sentiments

def get_wine_description(sql_address, sku):
    
    cols = ['name', 'made_in', 'by', 'price', 
                'description', 'abv', 'volume', 'volume_unit', 
                'container', 'varietal', 'calories', 'image',
                'ratings_average', 'ratings_count',
               ]
    
    cols_dict = dict(zip(cols,cols))
    cols_dict['description'] =  "COALESCE(description,'No description available') as description"
    cols_dict['image'] = "REPLACE(image, '319.319', '1280.1280') as image"
    
    q = f"select {', '.join(cols_dict.values())} from lcbo.wine where sku = {sku}"

    wine = query(sql_address,q)
    wine = [dict(zip(cols,w)) for w in wine ]
    
    return wine

def get_wine_cards_from_closest_store(sql_address, lat, lon, wine_limit = 10):
    store = closest_stores(sql_address, lat, lon, max_stores = 1, max_distance = 100)[0]
    lcbo_id = store['lcbo_id']
    
    wine_cards = get_top_wines_from_store(sql_address, lcbo_id, limit = wine_limit, pos_price_diff_range=[0.9, 100], neg_price_diff_range=[0, 1.1])
    
    for w in wine_cards:
        w.update(get_wine_description(sql_address, w['sku'])[0])

    return wine_cards, store
    
    