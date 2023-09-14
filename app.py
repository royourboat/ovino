# coding: utf-8
import os
from flask import Flask,  render_template, request
from flask_googlemaps import GoogleMaps,Map,  get_coordinates
import json
import lcbo
from flask_wtf import FlaskForm
from wtforms.fields import DecimalRangeField, IntegerRangeField, IntegerField, DecimalField
from wtforms.fields import SubmitField, SelectField, StringField
from flask_wtf.csrf import CSRFProtect
import pandas as pd
import vivino
import numpy as np

### ENVIRONMENT and FUNCTION SETUP ###
API_KEY = os.getenv("GOOGLE_API_KEY") # google api key for ovino
sql_address = os.getenv("AUTOVINO_URL")  # postgres database
USERNAME_DEFAULT = ''

app = Flask(__name__, template_folder="templates")
app.config['SECRET_KEY'] = os.urandom(32)
app.config['WTF_CSRF_TIME_LIMIT'] = 100000
app.my_address = None
app.vivino_username = USERNAME_DEFAULT
app.coord = None



csrf = CSRFProtect(app)
csrf.init_app(app)

GoogleMaps(app, key = API_KEY,)
MYLAT = 49.5   # Anchor coordinate
MYLNG = -84.5  # Anchor coordinate

### EXPERIMENTAL ###
# Personal recommender
flist = [f'static/data/all_dense_lcbo.{str(i+1)}_of_4.gz.csv' for i in range(4)]
app.df_dense = pd.concat([pd.read_csv(fname, compression='gzip').drop('Unnamed: 0', axis=1) for fname in flist])
app.user_wdr_dict = {USERNAME_DEFAULT: {}}
app.wine_id_to_sku = lcbo.get_wine_id_dict(sql_address)


# Flask form to collect user input
class InputForm(FlaskForm):
    price_min = IntegerField('$ Min', default = 1)
    price_max = IntegerField('$ Max', default = 30)
    rating_min = DecimalRangeField('Minimum Star Rating', default = 3.6)
    pos_min = IntegerRangeField('Minimum Price Sentiment', default = 7)
    pos_count = IntegerRangeField('Minimum Price Sentiment Votes', default = 20)
    show_count = IntegerField('Show', default = 25)
    submit = SubmitField('Filter')
    search = SubmitField('Search')
    sort_by = SelectField('Sort by', default = 1, choices=[
                                                (1, 'Price Votes'),
                                                (2, 'Recommended Price'),
                                                (3, 'Star Rating'),
                                                (4, 'Price (low-high)'),
                                                (5, 'Price (high-low)'),
                                                (6, 'Calories (low-high)'),
                                            ])
    vivino_username = StringField(USERNAME_DEFAULT)

### FLASK: INDEX.HTML WEB PAGE ###
# Description: 
# Content for th elanding page and wine-cards pages are generated here. 
###
@app.route("/", methods=['POST', 'GET'])
def index():

    # 1. Read URL for queries
    form = InputForm(request.args)

    # 2. Define defaults
    # Wine card pagination
    MAX_WINES_PER_PAGE = 20
    TOTAL_NUM_PAGES = 1
    PAGE = 1
    if request.args.get('page'):
        PAGE = int(request.args.get('page'))
    
    # Google maps store location
    my_address = request.args.get('my_address')
    vivino_username = request.args.get('vivino_username')
    df_store = None
    markers = []
    
    if vivino_username:
        if '/' in vivino_username:
            vivino_username = vivino_username.split('/')[-1]
        app.vivino_username = str(vivino_username)
    else:
        app.vivino_username = USERNAME_DEFAULT

    # Recommended 'cards' of wine from query results
    wine_cards = []
    if my_address:
        if app.my_address != my_address:
            # Get coordinates of user address
            try:
                app.coord = get_coordinates(API_KEY, my_address) 
                app.my_address = my_address
            except:
                app.coord = get_coordinates(API_KEY, "Toronto")
                app.my_address = f"'{my_address}' address not found. Displaying results for Toronto."

        
        if app.vivino_username  and app.vivino_username  not in app.user_wdr_dict.keys():
            best_wdr_wines =  vivino.get_best_wdr_wines(app.df_dense, app.vivino_username )
            common_wine_ids = set(best_wdr_wines.keys()).intersection(set(app.wine_id_to_sku.keys()))
            app.user_wdr_dict[app.vivino_username ] = {app.wine_id_to_sku[wine_id]: best_wdr_wines[wine_id] for wine_id in common_wine_ids}

            
        # Find closest stores to coords
        df_store = lcbo.closest_stores(sql_address, app.coord['lat'], app.coord['lng'], max_stores=1).iloc[0].to_dict()
        
        # Google Maps marker for store location
        markers.append({
            "icon": "/static/images/google_map_icon.png",
            "lat" : df_store['lat'],
            "lng" : df_store['lng'],
            "title": "LCBO",
            "infobox": (
                '<div jstcache="3" class="title full-width" jsan="7.title,7.full-width"><b><b>LCBO</b></b></div>'
                f'<div jstcache="4" jsinstance="0" class="address-line full-width" jsan="7.address-line,7.full-width">{df_store["address"]}</div>'
                f'<div jstcache="4" jsinstance="*1" class="address-line full-width" jsan="7.address-line,7.full-width">{df_store["city"]}</div>'
                f'<div jstcache="4" jsinstance="*1" class="address-line full-width" jsan="7.address-line,7.full-width">{df_store["phone"]}</div>'
                ),
        })
        # Google Maps marker for user location
        markers.append({ 
            "icon": "/static/images/gold_person.png",
            "lat" : app.coord['lat'], 
            "lng" : app.coord['lng'],
            "title": "You",
            "infobox": ('<div jstcache="3" class="title full-width" jsan="7.title,7.full-width"><b><b>You</b></b></div>' ),
        })
        
            
        # Generate recommended wine cards and define pagination
        skus_filter = []
        if app.user_wdr_dict[app.vivino_username ]:
            skus_filter = list(app.user_wdr_dict[app.vivino_username ].keys())
        wine_cards = lcbo.get_wines_from_store(sql_address, df_store['store_id'], page = PAGE, wines_per_page = MAX_WINES_PER_PAGE, form = form, skus_filter = skus_filter)
        TOTAL_NUM_WINES = 0
        if wine_cards:
            TOTAL_NUM_WINES = wine_cards[0]['total_count']
        TOTAL_NUM_PAGES = TOTAL_NUM_WINES/MAX_WINES_PER_PAGE
        TOTAL_NUM_PAGES = int(-(-TOTAL_NUM_PAGES // 1))
                        
    # Define google maps parameters for googlemaps api.
    sndmap = Map(
        identifier="sndmap",
        varname="sndmap",
        region = 'CA',
        lat = MYLAT,
        lng = MYLNG,
        markers=markers,
        zoom = 4,
        fit_markers_to_bounds = True,
        zoom_control = False,
        maptype_control = False,
        scale_control = False,
        streetview_control = False,
        rotate_control = False,
        fullscreen_control = False,
        style = "height:360px;width:90%;margin:0px;color:#242f3e;",
        #styles = json.load( open('dark_mode.json')),
    )

    return render_template(
        "index.html",
        sndmap = sndmap,
        my_address = app.my_address, 
        vivino_username = app.vivino_username,
        my_wdr_dict = app.user_wdr_dict[app.vivino_username],
        len_wine_cards = len(wine_cards),
        wine_cards = wine_cards,
        df_store = df_store,
        form = form, 
        total_num_pages = TOTAL_NUM_PAGES,
    )

### FLASK: ABOUT.HTML WEB PAGE ###
@app.route('/about/')
def about():
    return render_template('about.html')

### FLASK: ABOUT.HTML WEB PAGE ###
@app.route('/username/')
def username():
    return render_template('username.html')

@app.route("/clickpost/", methods=["POST"])
def clickpost():
    # Now lat and lon can be accessed as:
    lat = request.form["lat"]
    lng = request.form["lng"]
    return "ok"

if __name__ == '__main__':
    app.run(debug=False)

#if __name__ == "__main__":
#    app.run(port=5000, debug=True, use_reloader=True)
