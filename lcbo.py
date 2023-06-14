import psycopg2

def query(sql_address, q):
    conn = psycopg2.connect(sql_address)
    cur = conn.cursor()
    cur.execute(q)
    column_names = [desc[0] for desc in cur.description]
    tbl = cur.fetchall()
    conn.close()

    return tbl, column_names

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
    stores, cols = query(sql_address, q)    
    stores = [dict(zip(get_cols,store)) for store in stores ]

    return stores


def get_top_wines_from_store(
        sql_address, 
        lcbo_id, 
        min_sentiment=8, 
        pos_limit = 0.7, 
        neg_limit=0.3, 
        limit = 100, 
        pos_price_diff_range=[0.9,100], 
        neg_price_diff_range = [0, 1.1],
        wines_per_page = 25,
        page = 1,
        form = None
    ):

    cols = ['name', 'made_in', 'by', 'price', 
                'description', 'abv', 'volume', 'volume_unit', 
                'container', 'varietal', 'calories', 'image',
                'ratings_average', 'ratings_count', 'sku',
               ]
    
    cols_dict = dict(zip(cols,cols))
    cols_dict['description'] =  "COALESCE(description,'No description available') AS description"
    cols_dict['image'] = "REPLACE(image, '319.319', '1280.1280') AS image" #higher resolution images
    #cols_dict['image'] = "image" #low res

    price_min = 1.
    price_max = 5000.
    rating_min = 1.
    order = 1
    if form:
        price_min = float(form.price_min.data)
        price_max = float(form.price_max.data)
        rating_min = float(form.rating_min.data)
        order = int(form.sort_by.data)

    order_by = "ratio desc"
    if order == 2:
        order_by = "ratings_average desc"
    elif order == 3:
        order_by = "price asc"
    elif order == 4:
        order_by = "price desc"

    q = f"""
        DROP TABLE IF EXISTS store_products, store_products_with_sentiment, lcbo_products, ovino_products;
        CREATE TEMP TABLE store_products AS
        SELECT * FROM (
            WITH viv AS (
                WITH ont AS (
                    SELECT distinct vivino_id, sku FROM lcbo.store_{lcbo_id}
                )
                SELECT reviews, positivity, price AS user_price, vivino.reviews.vivino_id, ont.sku, "wine.country" AS country FROM vivino.reviews
                INNER JOIN ont
                ON ont.vivino_id = vivino.reviews.vivino_id 
            ),
            wine AS (
                SELECT price, vivino_id, sku, made_in FROM lcbo.wine
            )
            SELECT viv.reviews, viv.positivity, viv.vivino_id, viv.sku, price, user_price, country, made_in
            FROM viv 
            INNER JOIN wine
            ON viv.vivino_id = wine.vivino_id AND viv.sku = wine.sku
            WHERE made_in LIKE CONCAT('%', country, '%')
            
        ) AS dum;

        CREATE TEMP TABLE store_products_with_sentiment AS
        SELECT * FROM (
            WITH positives AS (
                SELECT vivino_id, sku, COUNT(*) AS pos FROM store_products
                WHERE positivity > 0.7
                group by vivino_id, sku
            ),
            negatives AS (
                SELECT vivino_id, sku, COUNT(*) AS neg FROM store_products
                WHERE positivity < 0.3
                group by vivino_id, sku
            )
            SELECT positives.vivino_id, positives.sku, coalesce(pos,0) AS pos, coalesce(neg,0) AS neg, CAST(pos AS float)/(pos+neg) AS ratio
            FROM positives JOIN negatives
            ON positives.vivino_id = negatives.vivino_id AND positives.sku = negatives.sku
            WHERE (pos+neg)>={min_sentiment}
        ) AS dum2;

        CREATE TEMP TABLE lcbo_products AS
        SELECT * FROM(
            SELECT {', '.join(cols_dict.values())} FROM lcbo.wine 
                WHERE  price >= {price_min} AND price <= {price_max} AND ratings_average >= {rating_min} AND volume <= 751 
        ) AS dum3;

        CREATE TEMP TABLE ovino_products AS
        SELECT * FROM (
            SELECT *
            FROM store_products_with_sentiment
            JOIN lcbo_products using (sku)
        ) AS dum4
        ORDER BY {order_by}
        ;

        CREATE TEMP TABLE ovino_products_count AS
        SELECT COUNT(*) AS len FROM ovino_products;

        ALTER TABLE ovino_products ADD id serial;
        ALTER TABLE ovino_products ADD column total_count integer;
        UPDATE ovino_products set total_count = len FROM ovino_products_count;
        
        SELECT * FROM ovino_products
        WHERE id >= {(page - 1) * wines_per_page + 1} AND id < {page * wines_per_page  + 1}
        ORDER BY id
        limit {limit};
        
        """

    wine_cards, cols = query(sql_address,q)
    wine_cards = [dict(zip(cols,s)) for s in wine_cards ]
    return wine_cards

def get_wine_cards_from_closest_store(sql_address, lat, lon, limit = 50, wines_per_page = 25,
        page = 1, form=None):
    store = closest_stores(sql_address, lat, lon, max_stores = 1, max_distance = 100)[0]
    lcbo_id = store['lcbo_id']
    
    wine_cards = get_top_wines_from_store(sql_address, lcbo_id, limit = limit, wines_per_page = wines_per_page,
        page = page,  form = form)

    return wine_cards, store
    
