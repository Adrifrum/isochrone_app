import dash_bootstrap_components as dbc
from dash import html

logo = "https://upload.wikimedia.org/wikipedia/commons/a/a2/OECD_logo.svg"

def Navbar():
    navbar = dbc.Navbar(
        [
            html.A(
                # Use row and col to control vertical alignment of logo / brand
                dbc.Row(
                    [
                        dbc.Col(html.Img(src=logo, height="80px")),
                        dbc.Col(dbc.NavbarBrand("Adrien FRUMENCE Portfolio", className="ml-2")),
                    ],
                    align="center",
                ),
            ),
        ],
        color="white",
        style={'background-image': 'url("static/background-header.png")'}
    )

    return navbar
