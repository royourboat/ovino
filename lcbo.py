import psycopg2

def query(sql_address, q):
    conn = psycopg2.connect(sql_address)
    cur = conn.cursor()
    cur.execute(q)
    column_names = [desc[0] for desc in cur.description]
    tbl = cur.fetchall()
    conn.close()

    return tbl, column_names

def command(sql_address, q):
    connection = psycopg2.connect(sql_address)
    cur = connection.cursor()
    cur.execute(q)
    connection.commit()
    connection.close()

def closest_stores(sql_address, lat, lon, max_distance=20, max_stores=3):
    get_cols = ['lat', 'lng', 'store_id', 'name', 'address', 'city', 'phone']
    q = f"""
            SELECT *, 6371.0*2.0*asin(sqrt(sin(0.5*(lat2-lat1))^2 + cos(lat1)*cos(lat2)*sin(0.5*(lon2-lon1))^2  )) AS distance FROM (
                SELECT {', '.join(get_cols)}, 
                radians({lat}) AS lat1, radians({lon}) AS lon1, 
                radians(lat) AS lat2, 
                radians(lng) AS lon2 FROM stores
            ) AS dum
            ORDER BY distance
            LIMIT {max_stores};
    
    """
    stores, cols = query(sql_address, q)    
    stores = [dict(zip(get_cols,store)) for store in stores ]
    return stores


def get_top_wines_from_store(
        sql_address, 
        store_id, 
        min_votes=8, 
        limit = 100, 
        wines_per_page = 25,
        page = 1,
        form = None
    ):
   
    cols = [
        'name',
        'varietal',
        'category',
        'region',
        'country',
        'brand',
        'url_thumbnail',
        'description',
        'abv',
        'calories',
        'volume',
        'sku',
        'url',
    ]
   
    order_dict = {
        1: 'positivity desc',
        2: 'votes desc',
        3: 'ratings_average desc',
        4: 'promo_price_cents asc',
        5: 'promo_price_cents desc',
        6: 'calories asc',
    }
    
    price_min = 1.
    price_max = 5000.
    rating_min = 1.
    order = 1
    price_delta = 0.05

    if form:
        if form.price_min.data:
            price_min = float(form.price_min.data)*(1 - price_delta)
        if form.price_max.data:
            price_max = float(form.price_max.data)*(1 + price_delta)
        rating_min = float(form.rating_min.data)
        order = int(form.sort_by.data)

    order_by = order_dict[order]

    q = f"""
        DROP VIEW IF EXISTS num_store_products;
        DROP VIEW IF EXISTS store_products_sentiment;
        DROP VIEW IF EXISTS store_products;
        DROP VIEW IF EXISTS available_products;


        CREATE VIEW available_products AS
        SELECT SKU FROM inventory
        WHERE store_id = {store_id} and quantity > 0;

        -- Reminder: Use "USING" instead of a.sku = b.sku when joining in VIEW. 
        CREATE VIEW store_products AS
        SELECT * FROM (
            -- Get product details, if products available in store
            SELECT * FROM (SELECT {', '.join(cols)} FROM products) as dummy
            INNER JOIN (
                SELECT sku, promo_price_cents FROM prices
                INNER JOIN (
					SELECT sku, MAX(checktime) AS checktime FROM prices
					GROUP BY sku
				) as recent_prices
				USING (sku, checktime)
            ) as pr
            USING (sku)
            INNER JOIN (
                SELECT sku, vivid2 FROM index_matches
                WHERE vivid2 IS NOT NULL
            ) as im
            USING (sku)
            INNER JOIN (
                SELECT sku FROM available_products
            ) as ap
            USING (sku)
            INNER JOIN(
                SELECT * FROM vivino_lcbo_ratings
            ) as vlr
            USING (vivid2)
            
        ) as dum;

        CREATE VIEW store_products_sentiment AS (
            SELECT * FROM (
                SELECT *, (pos+neg) as votes, CAST(pos AS float)/(pos+neg) AS positivity FROM (
                    SELECT sku, SUM(sentiment_pos) AS pos, SUM(sentiment_neg) AS neg
                    FROM vivino_lcbo_sentiment
                    GROUP BY sku
                ) as wine_sentiments
                INNER JOIN (
                    SELECT * FROM store_products
                ) AS sp 
                using (sku)
            ) as ddum
            WHERE votes > {min_votes}
            AND promo_price_cents >= {int(price_min*100)}
            AND promo_price_cents <= {int(price_max*100)}
            AND ratings_average >= {rating_min}
            ORDER BY {order_by}
        ) ;
        
        CREATE VIEW num_store_products AS
        SELECT COUNT(*) AS total_count FROM store_products_sentiment;
        
        SELECT * FROM (
            SELECT ROW_NUMBER() OVER () as rownumber, * FROM store_products_sentiment
            CROSS JOIN num_store_products
        ) as dum
        WHERE rownumber >= {(page - 1) * wines_per_page + 1} AND rownumber < {page * wines_per_page  + 1}
        ORDER BY rownumber
        limit {limit};
    """

    wine_cards, cols = query(sql_address, q)
    wine_cards = [dict(zip(cols,s)) for s in wine_cards ]

    for wine_card in wine_cards:
        wine_card['price'] = wine_card['promo_price_cents']/100.
        wine_card['url_thumbnail'] = wine_card['url_thumbnail'].replace('319.319', '1280.1280')
        if not wine_card['description']:
            wine_card['description'] = 'No description available'
        
        if wine_card['region']:
            wine_card['made_in'] = f"{wine_card['region']}, {wine_card['country']}"
        else:
            wine_card['made_in'] = f"{wine_card['country']}"
    return wine_cards

def get_wine_cards_from_closest_store(sql_address, my_store, lat, lng, limit = 50, wines_per_page = 25,
        page = 1, form=None):
    
    store_id = my_store['store_id']
    
    wine_cards = get_top_wines_from_store(sql_address, store_id, limit = limit, wines_per_page = wines_per_page,
        page = page,  form = form)

    return wine_cards
    
