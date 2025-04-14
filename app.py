import requests
from flask import Flask
from shapely.geometry import shape, Point
import shapely.wkt
import dash_bootstrap_components as dbc
import dash_leaflet as dl
from dash import Dash, dcc, html, Input, Output
import json
from geojson import Feature, Point, FeatureCollection, Polygon
from dash.dependencies import Output, Input, State
import pandas as pd
import numpy as np
import time
from navbar_ign_insee import Navbar
import ast
import os
import geopandas as gpd
from dash_extensions.javascript import assign

#style densité population

style_handle = assign("""function(feature, context){
    const {classes, colorscale, style, colorProp} = context.hideout;
    const value = feature.properties[colorProp];
    for (let i = classes.length - 1; i >= 0; --i){
        if (value >= classes[i]){
            style.fillColor = colorscale[i];
            break;
        }
    }
    style.fillOpacity = 0.4;  // Augmenter la transparence
    return style;
}""")

on_each_feature = assign("""function(feature, layer, context){
    layer.bindTooltip(`This is <b> html </b>. Foo is [${feature.properties.siret}])`)
    layer.bindTooltip(`<b>Etablissement similaire : </b><br><b>Raison sociale : </b>[${feature.properties.nom_complet}]<br><b>SIRET : </b>[${feature.properties.siret}]<br><b>Activite principale : </b>[${feature.properties.activite_principale}]`)
}""")  # add custom tooltip. Must be done in JavaScript

AUTH_BEARER_INSEE = os.environ.get("AUTH_BEARER_INSEE")

server = Flask(__name__)
app = Dash(__name__, server=server)

app.title = 'Isochrone app'

headers_insee = {'Authorization': AUTH_BEARER_INSEE }

nav = Navbar()

icon = {
    "iconUrl": 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
    "shadowUrl": 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    "iconSize": [25, 41],
    "iconAnchor": [12, 41],
    "popupAnchor": [1, -34],
    "shadowSize": [41, 41]
}


def flip_geojson_coordinates(geo):
    if isinstance(geo, dict):
        for k, v in geo.items():
            if k == "coordinates":
                z = np.asarray(geo[k])
                f = z.flatten()
                geo[k] = np.dstack((f[1::2], f[::2])).reshape(z.shape).tolist()
            else:
                flip_geojson_coordinates(v)
    elif isinstance(geo, list):
        for k in geo:
            flip_geojson_coordinates(k)


type_input = dbc.Row(
    [
        dbc.Alert(
            "Le Siret semble incorrect : veuillez réessayer",
            id="alert-erreur",
            is_open=False,
            duration=2000,
            color="danger",
        ),
        dbc.Label("Types of essential services"),
        dbc.Col(
            dcc.RadioItems(
            id='my-radioitems',
            options=[
                {'label': "NAF 88.91A: Day care or support services for young children", 'value': '88.91A'},
                {'label': "NAF 88.91A: Day care or support services for children with disabilities", 'value': '88.91B'},
                {'label': 'NAF 86.10Z: Hospital-related activities', 'value': '86.10Z'},
                {'label': 'NAF 87.10A: Medicalized housing for eldery individuals', 'value': '87.10A'}       ],
            value='88.91A',
            labelStyle={'display': 'block'}
            ),
            width=10,
        ),
    ],
    className="mb-3",
)

mode_input = dbc.Row(
    [
        dbc.Label("Choose a mode of transport (isochrone)"),
        dbc.Col(
            dcc.RadioItems(
            id='my-mode-radioitems',
            options=[
                {'label': 'Car', 'value': 'car'},
                {'label': 'Pedestrian', 'value': 'pedestrian'}    ],
            value='car',
            labelStyle={'display': 'block'}
            ),
            width=10,
        ),
    ],
    className="mb-3",
)

siret_input = dbc.Row(
    [
        dbc.Label("Enter an address in France"),
        dbc.Col(
            dbc.FormFloating(
            [
                #dbc.Input(id="my-input", placeholder="58 rue didot 75014 PARIS", value='58 rue didot 75014 PARIS', type="text"),
                dbc.Input(
                    type="text",
                    id="my-input",
                    placeholder="17 Rte de Fontaucher, 23000 Guéret",
                    value="17 Rte de Fontaucher, 23000 Guéret",
                    persistence=False,
                    autocomplete="off",
                    list='list-suggested-inputs'),
                dbc.Label("Address"),
                html.Datalist(id='list-suggested-inputs', children=[html.Option(value='empty')])
            ]
        )
        ),
    ],
    className="mb-3",
)

isochrone_input = dbc.Row(
    [
        dbc.Label("Enter a travel time (in minutes)"),
        dbc.Col(
            dbc.FormFloating(
            [
                dbc.Input(id="my_input_isochrone", type="number", placeholder=60, value=60, min=1, max=60),
                dbc.Label("Duration in minutes (max 60)"),
            ], 
        ),
        ),
    ],
    className="mb-3",
)

button_find = dbc.Row(
    [
                html.P(
                dbc.Button("Compute", id="button_find", n_clicks=0, color="primary", size="me-1"),
                style={'textAlign': 'center'}
                 ),
                html.P(
                dcc.Loading(id="ls-loading-1", children=[html.Div(id="ls-loading-output-1")], type="circle"), style={'textAlign': 'center'})
    ],
    className="mb-3",
)


offcanvas_recherche = html.Div(
    [ 
        dbc.Offcanvas(
            dbc.Form([type_input, siret_input, mode_input, isochrone_input, button_find], style={'margin-top':'80px'}),
            id="offcanvas-recherche",
            title="Compute an interactive isochronous zone",
            is_open=False,
            keyboard=True
        ,style={'width': '50vh', 'margin-top':'210px'},),
    ])

jumbotron = html.Div(
    dbc.Container(
        [
            html.P(
                "Mapping inequality in access to essential services in France : This proof of concept uses isochrone analysis to evaluate how easily people across France can reach key services, highlighting spatial inequalities and supporting data-driven planning."
                , style={'textAlign': 'center'}
            ),
            html.P(
                dbc.Button("Learn more", id="open-offcanvas", n_clicks=0, color="primary", size="me-1")
                , style={'textAlign': 'center', 'margin-bottom' : '-10px'}
            ),
        ],
        fluid=True,
        className="py-3",
    ), style={'margin-top' : '-10px'},
    className="p-1 bg-light rounded-3"
)

modal = html.Div(
    [
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Please wait")),
                dbc.ModalBody(html.P(["We comply with the National Institute of Statistics and Economic Studies (INSEE) and the National Institute of Geographic and Forest Information (IGN) APIs ", html.A("terms of use", target="_blank", href="https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/pages/item-info.jag?name=Sirene&version=V3&provider=insee") , ", which limit requests to 30 per minute."])),
                dbc.ModalFooter(
                    dbc.Button(
                        "Close", id="close", className="ms-auto", n_clicks=0
                    )
                ),
            ],
            id="modal",
            is_open=False,
        ),
    ]
)


app.layout = html.Div([
    nav,
    modal,
    offcanvas_recherche,
    jumbotron,
    dbc.Row(
            [
                dbc.Col(dbc.Button("Generate a new interactive isochrone", color="primary", id="open-offcanvas-recherche", n_clicks=0), className="me-1", width={"size": 2, "offset": 4}),
                dbc.Col(dbc.Button("Download all official data related to these essential services.", color="primary", id="btn_xlsx", n_clicks=0), className="me-1", width={"size": 2, "offset": 12})
            ],
            align="center", style={"margin-bottom": "15px", "margin-top": "15px", "margin-right": "auto"},
        ),
    html.Div(id='my-output'),
    
    html.Div(id="description"),
    # dcc.Store inside the app that stores the intermediate value
    #dcc.Store(id='feature_collection'),
    dcc.Download(id="download-dataframe-xlsx"),
    dbc.Offcanvas(
            html.P(["Geospatial Analysis of Inequalities in Access to Essential Services Across France : This project investigates geographic disparities in the accessibility of essential services throughout France. By generating isochrone maps around specific addresses, we assess how easily populations can reach vital services such as healthcare, education, and public transport. The goal is to identify underserved areas and provide actionable insights to support more equitable territorial planning and policy-making.",
            html.Br(),
            html.Br(),
            html.Br(),
            "To achieve this, it relies on official, up-to-date, and reliable API data provided by the National Institute of Statistics and Economic Studies (INSEE) and the National Institute of Geographic and Forest Information (IGN).",
            html.Br(),
            html.Br(),
            html.Br(),
            "Don't hesitate to reach out with any feedback on the tool : ", html.A("adrien.frum@gmail.com", href="mailto:adrien.frum@gmail.com?subject=Feedback on the tool"),
            html.Br(),
            html.Br(),
            html.Br(),
            "See you soon :)"
            ]),
            id="offcanvas",
            title="Learn more",
            is_open=False,
            placement='end',
            keyboard=True
            ,style={'width': '50vh', 'margin-top':'210px'}
        ),
], id="layout_full")

#Codes naf 88.91A (garderie) et 86.10Z (hopitaux)
@app.callback(
    Output(component_id='my-output', component_property='children'),
    Input("button_find", "n_clicks"),
    State(component_id='my-input', component_property='value'),
    State(component_id='my-radioitems', component_property='value'),
    State(component_id='my-mode-radioitems', component_property='value'),
    State(component_id='my_input_isochrone', component_property='value'),
)
def update_output_div(n_clicks, input_value, radioitems_value, mode_radioitems_value, input_isochrone_value):
    input_value = input_value.replace(" ", "+")
    #url_siret = f"https://recherche-entreprises.api.gouv.fr/search?q={input_value}"
    url_adresse = f"https://api-adresse.data.gouv.fr/search/?q={input_value}"
    response_adresse = requests.get(url_adresse, verify=False)
    json_data_adresse = response_adresse.json()
    url_near_point = f"https://recherche-entreprises.api.gouv.fr/near_point?lat={json_data_adresse['features'][0]['geometry']['coordinates'][1]}&long={json_data_adresse['features'][0]['geometry']['coordinates'][0]}&radius=50&activite_principale={radioitems_value}&page=1&per_page=25"
    response_url_near_point = requests.get(url_near_point, verify=False)
    json_data_url_near_point = response_url_near_point.json()

    feature_collection = FeatureCollection(json_data_url_near_point["results"])

    center_list = [json_data_adresse['features'][0]['geometry']['coordinates'][1], json_data_adresse['features'][0]['geometry']['coordinates'][0]]
    center_list_leaflet = [round(float(json_data_adresse['features'][0]['geometry']['coordinates'][1]), 4), round(float(json_data_adresse['features'][0]['geometry']['coordinates'][0]), 4)]
    
    #Requête IGN isochrone
    point = f'{center_list[1]},{center_list[0]}'
    costValue = f'{input_isochrone_value * 60}'
    profile = f'{mode_radioitems_value}'
    
    url_ign = f"https://data.geopf.fr/navigation/isochrone?point={point}&resource=bdtopo-valhalla&costValue={costValue}&costType=time&profile=car&direction=departure&constraints=%7B%22constraintType%22%3A%22banned%22%2C%22key%22%3A%22wayType%22%2C%22operator%22%3A%22%3D%22%2C%22value%22%3A%22autoroute%22%7D&distanceUnit=meter&timeUnit=second&crs=EPSG%3A4326"

    # Adding empty header as parameters are being sent in payload
    headers_ign = {'content-type': 'application/json'}
    response_ign = requests.get(url_ign, verify=False)
    full_json_data_ign = json.loads(response_ign.text)    

    flip_geojson_coordinates(full_json_data_ign)

    polygon = list(full_json_data_ign["geometry"]["coordinates"])

    polygon_check = shape(full_json_data_ign['geometry'])    

    new_feature_collection = []
    sirets = []
    for info in json_data_url_near_point["results"]:
        try:
            latitude = info['siege']['latitude']
            longitude = info['siege']['longitude']
            nom_complet = info['nom_complet'].title()
            activite_principale = info['activite_principale']
            siret = info['siege']['siret']
            point = shapely.wkt.loads(f'POINT ({latitude} {longitude})')
            point_leaflet = shapely.wkt.loads(f'POINT ({longitude} {latitude})')
            if polygon_check.contains(point):
                feature_correct = Feature(geometry=point_leaflet, properties={"nom_complet": nom_complet, "siret" : siret, "activite_principale" : activite_principale})
                new_feature_collection.append(feature_correct) 
                sirets.append(info['siege']['siret'])
        except:
            pass

    new_feature_collection = FeatureCollection(new_feature_collection) 

    #Ajout densité population
    
    densite_departements = pd.read_excel("static/densite_departements.xlsx", dtype={"DEP": str})
    densite_departements.columns = densite_departements.columns.str.strip()

    densite_departements = densite_departements.rename(columns={
        'DEP': 'code',
        'Département': 'nom_dep',
        'Densité': 'densite'
    })

    # 2. Charger les géométries des départements
    gdf = gpd.read_file("https://france-geojson.gregoiredavid.fr/repo/departements.geojson")
    gdf['code'] = gdf['code'].astype(str)

    # 3. Fusion des données
    gdf = gdf.merge(densite_departements[['code', 'nom_dep', 'densite']], on='code', how='inner')

    # === 4. Préparer le GeoJSON converti avec .to_crs et .to_json ===
    gdf = gdf.to_crs(epsg=4326)  # S'assurer qu'on est en WGS84
    geojson_data = json.loads(gdf.to_json())

    # === 5. Définir les classes et palette de couleur (style choropleth) ===
    classes = [0, 30, 60, 100, 150, 300, 600, 1000]
    labels = ["0–30", "30–60", "60–100", "100–150", "150–300", "300–600", "600–1000", "1000+"]
    colorscale = ["#ffffff", "#fee5d9", "#fcae91", "#fb6a4a", "#de2d26", "#a50f15", "#67000d", "#3b000a"]

    # === 6. Définir le style JS dynamique par valeur ===
    style = dict(weight=1, opacity=1, color="white", dashArray="3", fillOpacity=0.7)

    # === 7. Créer la légende (colorbar) ===
    legend = html.Div([
    html.Div("Population density in France per km², 2024", style={
        "fontWeight": "bold", "marginBottom": "8px", "fontSize": "14px"
    }),

    # Légende couleurs avec libellés
    html.Div([
        html.Div([
            html.Div(style={
                "backgroundColor": colorscale[i],
                "width": "24px",
                "height": "16px",
                "display": "inline-block",
                "marginRight": "8px",
                "border": "1px solid #ccc"
            }),
            html.Span(labels[i], style={"fontSize": "12px"})
        ], style={"marginBottom": "4px"}) for i in range(len(classes))
    ]),

    # Texte explicatif
    html.Div([
        html.Div("Note: In 2024, Paris has a population density of 20,720 inhabitants per square kilometer."),
        html.Div("Scope: France."),
        html.Div("National Institute of Statistics and Economic Studies (INSEE)")
    ], style={
        "marginTop": "8px",
        "fontSize": "11px",
        "lineHeight": "1.4"
    })
    ], style={
        "position": "absolute",
        "bottom": "10px",
        "right": "10px",
        "zIndex": "1000",
        "backgroundColor": "white",
        "padding": "10px",
        "border": "1px solid #ccc",
        "borderRadius": "5px",
        "boxShadow": "2px 2px 5px rgba(0,0,0,0.1)",
        "maxWidth": "350px",
        "fontFamily": "Arial"
    })




    return dl.Map(center=center_list_leaflet, zoom=9, children=[
    dl.TileLayer(),
    dl.GestureHandling(),
    dl.Marker(icon=icon, position=center_list_leaflet, children=dl.Popup(html.P([html.B("Adresse cible : "),"{}".format(json_data_adresse['features'][0]['properties']['label'])]))),
    dl.GeoJSON(data=new_feature_collection, id="markers", onEachFeature=on_each_feature),  # in-memory geojson (slowest option)
    dl.GeoJSON(
        data=geojson_data,
        id="geojson",
        style=style_handle,
        hideout=dict(colorscale=colorscale, classes=classes, style=style, colorProp="densite")
    ),
    legend,
    dl.Polygon(positions=polygon),
    ], style={'width': '100%', 'height': '656px', 'margin': "auto", "display": "block"}, id="map")
 

@app.callback(
    Output('list-suggested-inputs', 'children'),
    Input('my-input', "value"),
    prevent_initial_call=True
)
def suggest_locs(value):
    if not value or len(value) < 3:
        return []

    url_adresse = f"https://api-adresse.data.gouv.fr/search/?q={value}"
    response_adresse = requests.get(url_adresse, verify=False)
    json_data_adresse = response_adresse.json()

    features = json_data_adresse.get('features', [])
    
    # Si la première suggestion est exactement ce qu'on a tapé, on évite d'en proposer d'autres
    if features and features[0]['properties']['label'].lower() == value.lower():
        return []

    return [html.Option(value=feature['properties']['label']) for feature in features]


'''@app.callback(Output("tooltip", "children"), [Input("markers", "clickData")])
def capital_click(feature):
    print(feature)
    f feature is None:
        return print("toto")
    else:
        return [html.P([html.B("Établissement similaire : "),html.Br(), html.B("Raison sociale : "),"{}".format(feature['features'][0]['nom_complet'].title()),html.Br(),html.B("SIRET : "),"{}".format(feature['features'][0]['siret']),html.Br(),html.B("Activité principale : "),"{}".format(feature['features'][0]['activite_principale'])])]'''

@app.callback(
    Output("download-dataframe-xlsx", "data"),
    Input("btn_xlsx", "n_clicks"),
    State("my-input", "value"),
    prevent_initial_call=True,
)
def func(n_clicks, input_value):
    with open('./sirets.txt') as f:
        sirets = ast.literal_eval(f.read())
        
    input_value = input_value.replace(" ", "")
    sirets.insert(0, input_value)

    appended_data = []
    for siret in sirets:
        url = f"https://api.insee.fr/entreprises/sirene/V3.11/siret/{siret}"
        print(url)
        time.sleep(0.035)
        response= requests.get(url, headers=headers_insee, verify=False)
        if response.status_code == 200:
            json_data = response.json()
            data = pd.json_normalize(json_data["etablissement"])
            appended_data.append(data)
    df = pd.concat(appended_data)
    df = df.reset_index(drop=True)
    return dcc.send_data_frame(df.to_excel, f"export_{sirets[0]}.xlsx", sheet_name="export")


@app.callback(Output("ls-loading-output-1", "children"),Input("button_find", "n_clicks"), State("my-mode-radioitems", "value"), State("my_input_isochrone", "value"))
def input_triggers_spinner(n_clicks, mode, value):
    if mode == "car":
        time.sleep(3)
    else:
        time.sleep(3)


'''@app.callback(
    Output("alert-erreur", "is_open"),
    Input("button_find", "n_clicks"),
    State(component_id='my-input', component_property='value'),
    State("alert-erreur", "is_open"),
    prevent_initial_call=True,
)
def toggle_alert_no_fade(n_clicks,input_value, is_open):
    input_value = input_value.replace(" ", "")
    url_siret = f"https://recherche-entreprises.api.gouv.fr/search?q={input_value}"
    response_siret = requests.get(url_siret, verify=False)
    json_data_siret = response_siret.json()
    url = f"https://recherche-entreprises.api.gouv.fr/near_point?lat={json_data_siret['results'][0]['siege']['latitude']}&long={json_data_siret['results'][0]['siege']['longitude']}&radius=50&activite_principale={json_data_siret['results'][0]['activite_principale']}&page=1&per_page=10"
    response = requests.get(url, verify=False)
    if response.status_code == 200:
        return is_open
    else:
        return not is_open'''

@app.callback(
    Output("offcanvas", "is_open"),
    Input("open-offcanvas", "n_clicks"),
    [State("offcanvas", "is_open")],
)
def toggle_offcanvas(n1, is_open):
    if n1:
        return not is_open
    return is_open


@app.callback(
    Output("offcanvas-recherche", "is_open"),
    Input("open-offcanvas-recherche", "n_clicks"),
    [State("offcanvas-recherche", "is_open")],
)
def toggle_offcanvas(n1, is_open):
    if n1:
        return not is_open
    return is_open

@app.callback(
    Output("modal", "is_open"),
    [Input("btn_xlsx", "n_clicks"), Input("close", "n_clicks")],
    [State("modal", "is_open")],
)
def toggle_modal(btn_xlsx, close, is_open):
    if btn_xlsx or close:
        return not is_open
    return is_open


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080),
