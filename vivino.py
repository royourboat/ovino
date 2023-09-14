import pandas as pd
import requests
import re 
import numpy as np

def get_user_wines_and_ratings(username):
    
    profile_url = f'https://www.vivino.com/users/{username}'
    r = requests.get(profile_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0"
        })
    if r.status_code != 200:
        return None
    
    wineIDs = []
    ratings = []
    
    try:
        # Each username has a unique user ID (integer). Needed to access their ratings.
        user_id = re.search(r'(?<=vivino:\/\/\?user_id=)(\d+)', r.text).group(0)
        page = 1
        while page < 100:
            wineID_sample, rating_sample = scrape_rating(user_id, page)
            if not wineID_sample:
                break
            wineIDs += wineID_sample
            ratings += rating_sample
            page += 1
    except:
        pass

    dict_user_ratings = dict(zip(wineIDs, ratings))

    return dict_user_ratings

def scrape_rating(user_id, page=1):
    ratings_url = f'https://www.vivino.com/users/{user_id}/activities?page={page}&order=top-ratings'
    r = requests.get(ratings_url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:66.0) Gecko/20100101 Firefox/66.0", 
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'text/javascript, application/javascript, application/ecmascript, application/x-ecmascript, */*; q=0.01'
        })
    # Extract first instance of wine ID
    wineIDs = re.findall(r'(?<=\/w\/)(\d+)', r.text)
    seen = set()
    wineIDs_first_occurrence = []
    for i in wineIDs:
        if i not in seen:
            wineIDs_first_occurrence.append(i)
            seen.add(i)
    
    # Extract star ratings
    rating = [float(stars) for stars in re.findall(r'\d.\d(?=★)', r.text)]
        
    return wineIDs_first_occurrence, rating

def get_best_wdr_wines(dense_user_ratings, my_username, top_percentile = 0.3,  min_lcbo_matches = 3):
    dict_user_ratings = get_user_wines_and_ratings(my_username)
    if dict_user_ratings:
        lcbo_cols = set(dense_user_ratings.columns)
        wineIDs = list(set(dict_user_ratings.keys()).intersection(lcbo_cols))
        ratings = np.array([dict_user_ratings[wineID] for wineID in wineIDs])
        
        if len(wineIDs) >= min_lcbo_matches:
            mean_squared_difference_users = np.sum((dense_user_ratings[wineIDs].to_numpy() - ratings)**2, axis = 1)
            row_most_similar_user = mean_squared_difference_users.argmin()
            most_similar_user_ratings = dense_user_ratings.iloc[row_most_similar_user].to_numpy()

            index_ranked = np.argsort(most_similar_user_ratings)[::-1]
            index_ranked = index_ranked[0 : int(len(index_ranked)*top_percentile)]

            ranked_ratings = np.clip(most_similar_user_ratings[index_ranked], 1,5) 
            ranked_ratings = np.around(ranked_ratings, 1) # Round to nearest sig-fig (1)

            ranked_wines = [int(sku) for sku in dense_user_ratings.columns[index_ranked].to_list()]
            ranked_wines_dict = dict(zip(ranked_wines, ranked_ratings))
            
            return ranked_wines_dict
    
    return {}
        
