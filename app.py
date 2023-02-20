# coding: utf-8
import os
import psycopg2
from flask import Flask, redirect, url_for, render_template, request
from flask_googlemaps import GoogleMaps,Map, icons,get_address, get_coordinates
import json
import lcbo

MYLAT = 49.5
MYLNG = -84.5

app = Flask(__name__, template_folder="templates")

url = os.getenv("DATABASE_URL")  # gets variables from environment
conn = psycopg2.connect(url)
cur = conn.cursor()

API_KEY = os.getenv("GOOGLE_API_KEY")
GoogleMaps(app, key = API_KEY,)

@app.route("/")
def mapview():

    with open('dark_mode.json') as d:
        dark_data = json.load(d)
        
    MYADDRESS = request.args.get("myaddress")
    wine_cards = []
    my_store = None
    fit_markers_to_bounds = False
    
    markers = []
    
    if MYADDRESS:
        coord = get_coordinates(API_KEY, MYADDRESS) #Get coordinates of user address
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
        
        wine_cards, my_store = lcbo.get_wine_cards_from_closest_store(url, coord['lat'], coord['lng'],  wine_limit = 25)
                    
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
        MYADDRESS=request.args.get("myaddress"), 
        len_wine_cards = len(wine_cards),
        wine_cards = wine_cards,
        my_store = my_store
    )



@app.route("/clickpost/", methods=["POST"])
def clickpost():
    # Now lat and lon can be accessed as:
    lat = request.form["lat"]
    lng = request.form["lng"]
    return "ok"


#if __name__ == "__main__":
#    app.run(port=5000, debug=True, use_reloader=True)
