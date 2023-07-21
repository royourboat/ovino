# coding: utf-8
import os
import psycopg2
from flask import Flask, redirect, url_for, render_template, request, session
from flask_googlemaps import GoogleMaps,Map, icons,get_address, get_coordinates
import json
import lcbo

from flask_wtf import FlaskForm
from wtforms.fields import DecimalRangeField, IntegerRangeField, IntegerField, DecimalField
from wtforms.fields import SubmitField, StringField, SelectField
from flask_wtf.csrf import CSRFProtect


API_KEY = os.getenv("GOOGLE_API_KEY") # google api key for ovino
url = os.getenv("AUTOVINO_URL")  # postgres database

app = Flask(__name__, template_folder="templates")
app.config['SECRET_KEY'] = os.urandom(32)
app.config['WTF_CSRF_TIME_LIMIT'] = 100000
csrf = CSRFProtect(app)
csrf.init_app(app)

GoogleMaps(app, key = API_KEY,)
MYLAT = 49.5   # Anchor coordinate
MYLNG = -84.5  # Anchor coordinate

with open('dark_mode.json') as d:
    dark_data = json.load(d)


# form to collect user input:
class InputForm(FlaskForm):
    price_min = DecimalField('$ Min', default = 1.)
    price_max = DecimalField('$ Max', default = 30.)
    rating_min = DecimalRangeField('Minimum Star Rating', default = 3.6)
    pos_min = IntegerRangeField('Minimum Price Sentiment', default = 7)
    pos_count = IntegerRangeField('Minimum Price Sentiment Votes', default = 20)
    show_count = IntegerField('Show', default = 25)
    submit = SubmitField('Filter')
    search = SubmitField('Search')
    sort_by = SelectField('Sort by', default = 1, choices=[
                                                (1, 'Recommended Price'),
                                                (2, 'Star Rating'),
                                                (3, 'Price (low-high)'),
                                                (4, 'Price (high-low)'),
                                                (5, 'Calories (low-high)'),
                                            ])

@app.route("/", methods=['POST', 'GET'])
def index():

    form = InputForm(request.args)

    TOTAL_NUM_PAGES = 1
    PAGE = 1
    if request.args.get('page'):
        PAGE = int(request.args.get('page'))
    MYADDRESS = request.args.get('myaddress')
    MAX_WINES_PER_PAGE = 20

    wine_cards = []
    my_store = None
    fit_markers_to_bounds = False    
    markers = []
    
    if MYADDRESS:
        try:
            coord = get_coordinates(API_KEY, MYADDRESS) #Get coordinates of user address
        except:
            coord = get_coordinates(API_KEY, "Lake Ontario")
            MYADDRESS = f"'{MYADDRESS}' address not found."
        closest_stores = lcbo.closest_stores(url, coord['lat'], coord['lng'], max_stores=1) #Find closest stores to coords

        if len(closest_stores)>0:
            fit_markers_to_bounds = True
        
        for store in closest_stores: #Add a marker for each store on google maps
            markers.append({
                "icon": "/static/images/google_map_icon.png",
                "lat" : store['latitude'],
                "lng" : store['longitude'],
                "title": "LCBO",
                "infobox": (
                    '<div jstcache="3" class="title full-width" jsan="7.title,7.full-width"><b><b>LCBO</b></b></div>'
                    f'<div jstcache="4" jsinstance="0" class="address-line full-width" jsan="7.address-line,7.full-width">{store["address"]}</div>'
                    f'<div jstcache="4" jsinstance="*1" class="address-line full-width" jsan="7.address-line,7.full-width">{store["city"]}</div>'
                    f'<div jstcache="4" jsinstance="*1" class="address-line full-width" jsan="7.address-line,7.full-width">{store["phone_number"]}</div>'
                    ),
            })

        
        markers.append({ #Add user location
            "icon": "/static/images/gold_person.png",
            "lat" : coord['lat'], 
            "lng" : coord['lng'],
            "title": "You",
            "infobox": ('<div jstcache="3" class="title full-width" jsan="7.title,7.full-width"><b><b>You</b></b></div>' ),
        })
        

        wine_cards, my_store = lcbo.get_wine_cards_from_closest_store(url, coord['lat'], coord['lng'],  page= PAGE, wines_per_page = MAX_WINES_PER_PAGE, form = form)
        TOTAL_NUM_WINES = 0
        if wine_cards:
            TOTAL_NUM_WINES = wine_cards[0]['total_count']
        
        TOTAL_NUM_PAGES = TOTAL_NUM_WINES/MAX_WINES_PER_PAGE
        TOTAL_NUM_PAGES = int(-(-TOTAL_NUM_PAGES // 1))


    #Define google maps parameters for googlemaps api.
    sndmap = Map(
        identifier="sndmap",
        varname="sndmap",
        region = 'CA',
        lat=MYLAT,
        lng=MYLNG,
        
        markers=markers,
        #cluster = True,
        fit_markers_to_bounds = fit_markers_to_bounds,
        #center_on_user_location = True, #This conflicts with fit_markers_to_bounds=True
        zoom = 4,
        zoom_control=False,
        maptype_control=False,
        scale_control=False,
        streetview_control=False,
        rotate_control=False,
        fullscreen_control=False,
        style="height:360px;width:90%;margin:0px;color:#242f3e;",
        styles=dark_data,
    )

    return render_template(
        "index.html",
        sndmap=sndmap,
        MYADDRESS=MYADDRESS, 
        len_wine_cards = len(wine_cards),
        wine_cards = wine_cards,
        my_store = my_store,
        form=form, 
        total_num_pages = TOTAL_NUM_PAGES,
    )


@app.route('/about/')
def about():
    return render_template('about.html')

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
