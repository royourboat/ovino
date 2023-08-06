import psycopg2
import pandas as pd

def sql_query(sql_address, q):
    '''
    Returns DataFrame from PSQL database
    
    Parameters:
        sql_address (str): Address to PSQL database
        q (str): PSQL commands

    Returns:
        df (DataFrame): PSQL table results
    '''
    conn = psycopg2.connect(sql_address)
    cur = conn.cursor()
    cur.execute(q)
    column_names = [desc[0] for desc in cur.description]
    data = cur.fetchall()
    conn.close()
    df = pd.DataFrame(data, columns = column_names)
    return df

def closest_stores(sql_address, lat, lon, max_distance=20, max_stores=3):
    '''
    Returns the closest LCBO stores given the lat and lon.
    
    Parameters:
        sql_address (str): Address to PSQL database
        lat (float): Latitude
        lon (float): Longitude
        max_distance (float): Maximum search radius in kilometers
        max_stores (int): Limit of store results

    Returns:
        df_stores (DataFrame): PSQL table with stores
    '''
    
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
    df_stores = sql_query(sql_address, q)    
    return df_stores


def get_wines_from_store(sql_address, store_id, min_votes=8, page = 1, wines_per_page = 25,  form = None, limit = 100):
    '''
    Returns wines from a selected store id. Only return wines in a given pagination.
    
    Parameters:
        sql_address (str): Address to PSQL database
        store_id (int): Unique store identifier
        min_votes (int): Minimum number of price-sentiments available per bottle
        page (int): Get the wines between indices [page*wines_per_page, (page+1)*wines_per_page]
        wines_per_page (int): Wines per page
        form (Flask InputForm): Object containing query parameters.
        limit (int): Maximum returned results for safety.

    Returns:
        wine_cards (List of Dict): List of wines with various features. Returned this way due to Flask.
    '''
    
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
        1: 'votes desc',
        2: 'positivity desc',
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

    df_wine_cards = sql_query(sql_address, q)
    df_wine_cards['price'] = df_wine_cards['promo_price_cents'].apply(lambda x: x/100.)
    df_wine_cards['url_thumbnail'] = df_wine_cards['url_thumbnail'].apply(lambda x: x.replace('319.319', '1280.1280'))
    df_wine_cards['description'] = df_wine_cards['description'].apply(lambda x: 'No description available.' if not x.strip() else x)
    
    made_in_text = []
    for i, wine_card in df_wine_cards.iterrows():
        if wine_card['region']:
            made_in_text.append(f"{wine_card['region']}, {wine_card['country']}")
        else:
            made_in_text.append(f"{wine_card['country']}")
    df_wine_cards['made_in'] = made_in_text
            
    wine_cards = [dict(d) for i,d in df_wine_cards.iterrows()]    
    return wine_cards


