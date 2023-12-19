from pymongo import MongoClient
import pandas as pd
import datetime
from datetime import datetime, timedelta
import dash
from dash import Dash
from dash import dcc
from dash import html
from dash import dash_table
import dash_bootstrap_components as dbc
import plotly.express as px 
import numpy as np
import requests


# Set up the MongoDB connection
URI = "mongodb+srv://arithakumarasinghe:djR9fnE0rUq0rEox@cluster0.mizgqnm.mongodb.net/"
client = MongoClient(URI)
db = client["VIP"]
collection = db["sensor_status"]
sensors = collection.find({}, {'sensor_number': 1})

token = '6196622485:AAEvPAGe3F_CvW9_gDq5LEBG5VdbHifWDZ0'
userID = '6486526165'
message = ''
url = f'https://api.telegram.org/bot{token}/sendMessage'
data_1 = {'chat_id': userID, 'text': message}
last_message_timestamps = {}

external_stylesheets = [
    dbc.themes.BOOTSTRAP,
    {
        'href': 'https://stackpath.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css',
        'rel': 'stylesheet',
        'integrity': 'sha384-wvfXpqpZZVQGK6TAh5PVlZbbSleM53p9UqcF5WO93/DX4A',
        'crossorigin': 'anonymous'
    }
]

# Initialize the Dash app with Bootstrap styles and external stylesheets
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)


# Initialize a dictionary to store the last sent message timestamps for each sensor
last_message_timestamps = {}
median_results = []

app.layout = html.Div([
    dcc.Interval(
        id="interval-component",
        interval=10 * 1000,  # Refresh every 10 seconds (in milliseconds)
        n_intervals=0
    ),
    html.Div([
        html.Label("Select Sensors:"),
        dcc.Checklist(
                id="sensor-toggle",
                options=[],
                value=[]
            )
    ]),
    html.Div([
        html.Button('Calculate Median Time Difference', id='calculate-median-button', n_clicks=0,
                            style={'borderRadius': 5, 'borderColor': 'black', 'backgroundColor': 'lightblue', 'margin-top': '30px',  'margin-bottom': '10px','margin-right': '40px','margin-left': '20px',
                                   'fontSize': 16}),
        html.Button('Set Expected Delay to Median Delay', id='set-median-delay-button', n_clicks=0,
                            style={'borderRadius': 5, 'borderColor': 'black', 'backgroundColor': 'lightblue', 'margin-top': '30px',  'margin-bottom': '10px',
                                   'fontSize': 16})
    ]),
    html.Div([
        dash_table.DataTable(
            id='sensor-status-table',
            columns=[{"name": i, "id": i} for i in
                     ['Sensor Number', 'Status', 'Time Since Last Transmission(minutes)', 'Last Transmission', 'Expected Delay(minutes)', 'Median Time Difference']],
            data=[],
            editable=True,
            style_table={'height': 'auto', 'width': '100px'},
            style_data_conditional=[
                {
                    'if': {'column_id': 'Status', 'filter_query': '{Status} eq "GOOD"'},
                    'color': 'green'
                },
                {
                    'if': {'column_id': 'Status', 'filter_query': '{Status} eq "LATE"'},
                    'color': 'red'
                }
            ],
            style_cell={'margin': '30px', 'fontSize': 16}
        ),
        html.Div([
            html.Div([
                html.Button('↻', id='update-sensors-button', n_clicks=0,
                            style={'background-color': 'lightblue', 'borderRadius': 5, 'borderColor': 'black', 'margin-left': '1150px',
                                   'fontSize': 30})
            ], style={'display': 'flex', 'justify-content': 'left'}),
            html.Div([
                html.Label("Select Sensor:"),
                dcc.Dropdown(
                    id="sensor-dropdown",
                    options=[],
                    value=None
                ),
                html.Label("Enter Expected Delay (minutes):"),
                dcc.Input(id="delay-input", type="number", value=10),
                html.Button('Set Delay', id='set-delay-button', n_clicks=0)
            ])
        ], style={'font-family': 'Arial, sans-serif', 'margin': 'auto', 'text-align': 'center'})
    ])
],style={'justify-content': 'left'})

@app.callback(
    [
        dash.dependencies.Output('sensor-dropdown', 'options'),
        dash.dependencies.Output('sensor-toggle', 'options')
    ],
    [dash.dependencies.Input('update-sensors-button', 'n_clicks')]
)
def update_sensors_dropdown_and_checklist(n_clicks):
    sensors_data = list(collection.find({}, {'sensor_number': 1}))
    sensor_options = [{'label': f"Sensor {sensor['sensor_number']}", 'value': sensor['sensor_number']} for sensor in sensors_data]
    select_all_option = {'label': 'Select All', 'value': 'select_all'}
    sensor_options.insert(0, select_all_option)
    return [sensor_options, sensor_options]

@app.callback(
    [dash.dependencies.Output('sensor-status-table', 'data')],
    [dash.dependencies.Input('interval-component', 'n_intervals'),
     dash.dependencies.Input('set-delay-button', 'n_clicks'),
     dash.dependencies.Input('calculate-median-button', 'n_clicks'),
     dash.dependencies.Input('set-median-delay-button', 'n_clicks'),
     dash.dependencies.Input('sensor-toggle', 'value')],
    [dash.dependencies.State('sensor-dropdown', 'value'),
     dash.dependencies.State('delay-input', 'value')]
)
def update_table(n_intervals, n_clicks, median_clicks, set_median_delay_clicks, selected_sensors, sensor, delay):
    triggered_id = dash.callback_context.triggered[0]['prop_id'].split('.')[0]
    global median_results
    if triggered_id == 'interval-component':
        room_data = collection.find({}, {'sensor_number': 1, 'expected_delay': 1, 'last_transmission': 1})
        df_room = pd.DataFrame(room_data)
        data = []
        if 'select_all' in selected_sensors:
            selected_sensors = [sensor['sensor_number'] for sensor in collection.find({}, {'sensor_number': 1})]
        for sensor_number in selected_sensors:
            status = "GOOD"
            last_transmission = df_room.loc[df_room['sensor_number'] == sensor_number, 'last_transmission'].iloc[0]
            time_since_last_reading = datetime.now() - last_transmission
            time_since_last_reading_min = time_since_last_reading.total_seconds()/60
            last_transmission = last_transmission.strftime('%Y-%m-%d %H:%M:%S')
            expected_delay = df_room.loc[df_room['sensor_number'] == sensor_number, 'expected_delay'].iloc[0]
            median_time = next((item for item in median_results if item["Sensor Number"] == sensor_number), {"Median Time Difference": 'N/A'})["Median Time Difference"]
            if time_since_last_reading > timedelta(minutes=int(expected_delay)):
                status = "LATE"
                if (sensor_number not in last_message_timestamps or (datetime.now() - last_message_timestamps[sensor_number]) > timedelta(minutes=1)):
                    message = 'Sensor: '+str(sensor_number)+' is LATE'+'\nTime Since Last Transmission(minutes): '+str(time_since_last_reading_min)+'\nLast Transmission: '+str(last_transmission)+'\nExcepted Delay(minutes): '+str(expected_delay)
                    data_1['text'] = message
                    requests.post(url, data_1)
                    # Update the last sent message timestamp for the sensor
                    last_message_timestamps[sensor_number] = datetime.now()
            data.append({'Sensor Number': sensor_number, 'Status': status, 'Time Since Last Transmission(minutes)': time_since_last_reading_min,
                         'Last Transmission': last_transmission, 'Expected Delay(minutes)': expected_delay, 'Median Time Difference': median_time})
        return [data]
    elif triggered_id == 'set-delay-button':
        collection.update_one({'sensor_number': sensor}, {"$set": {'expected_delay': delay}})
        # Notify user about the change in excpeted time delay
        message = 'Expected time delay changed \nSensor: '+str(sensor_number)+' '+'\nNew excepted delay(minutes): '+str(delay)
        data_1['text'] = message
        requests.post(url, data_1)
        room_data = collection.find({}, {'sensor_number': 1, 'expected_delay': 1, 'last_transmission': 1})
        df_room = pd.DataFrame(room_data)
        data = []
        for sensor_number in [sensor]:
            status = "GOOD"
            last_transmission = df_room.loc[df_room['sensor_number'] == sensor_number, 'last_transmission'].iloc[0]
            time_since_last_reading = datetime.now() - last_transmission
            time_since_last_reading = time_since_last_reading.total_seconds()/60
            last_transmission = last_transmission.strftime('%Y-%m-%d %H:%M:%S')
            expected_delay = df_room.loc[df_room['sensor_number'] == sensor_number, 'expected_delay'].iloc[0]
            median_time = next((item for item in median_results if item["Sensor Number"] == sensor_number), {"Median Time Difference": 'N/A'})["Median Time Difference"]
            if time_since_last_reading > timedelta(minutes=int(expected_delay)):
                status = "LATE"
                if (sensor_number not in last_message_timestamps or (datetime.now() - last_message_timestamps[sensor_number]) > timedelta(minutes=1)):
                    message = 'Sensor: '+str(sensor_number)+' is LATE'+'\nTime Since Last Transmission(minutes): '+str(time_since_last_reading_min)+'\nLast Transmission: '+str(last_transmission)+'\nExcepted Delay(minutes): '+str(expected_delay)
                    data_1['text'] = message
                    requests.post(url, data_1)
                    # Update the last sent message timestamp for the sensor
                    last_message_timestamps[sensor_number] = datetime.now()
            data.append({'Sensor Number': sensor_number, 'Status': status, 'Time Since Last Transmission(minutes)': time_since_last_reading_min,
                         'Last Transmission': last_transmission, 'Expected Delay(minutes)': expected_delay, 'Median Time Difference': median_time})
        return [data]
    elif triggered_id == 'calculate-median-button':
        URI = "mongodb+srv://arithakumarasinghe:djR9fnE0rUq0rEox@cluster0.mizgqnm.mongodb.net/"
        client1 = MongoClient(URI)
        db1 = client1["VIP"]
        collection1 = db1["indoor_1"]
        cursor1 = collection1.find()
        sensor1 = pd.DataFrame(cursor1)

        grouped1 = sensor1.groupby('sensor_number')

        median_results = []
        # median time difference
        for name, group1 in grouped1:
            group1 = group1.sort_values('timestamp')
            time_diffs1 = group1['timestamp'].diff().dropna().dt.total_seconds() / 60
            median_time_diff1 = time_diffs1.median()
            if pd.isna(median_time_diff1):
                median_time_diff1 = np.nan
            median_results.append({'Sensor Number': name, 'Median Time Difference': f"{median_time_diff1} minutes"})

        room_data = collection.find({}, {'sensor_number': 1, 'expected_delay': 1, 'last_transmission': 1})
        df_room = pd.DataFrame(room_data)
        data = []
        for sensor_number in [sensor['sensor_number'] for sensor in collection.find({}, {'sensor_number': 1})]:
            status = "GOOD"
            last_transmission = df_room.loc[df_room['sensor_number'] == sensor_number, 'last_transmission'].iloc[0]
            time_since_last_reading = datetime.now() - last_transmission
            time_since_last_reading_min = time_since_last_reading.total_seconds()/60
            last_transmission = last_transmission.strftime('%Y-%m-%d %H:%M:%S')
            expected_delay = df_room.loc[df_room['sensor_number'] == sensor_number, 'expected_delay'].iloc[0]
            median_time = next((item for item in median_results if item["Sensor Number"] == sensor_number), {"Median Time Difference": 'N/A'})["Median Time Difference"]
            if time_since_last_reading > timedelta(minutes=int(expected_delay)):
                status = "LATE"
            data.append({'Sensor Number': sensor_number, 'Status': status, 'Time Since Last Transmission(minutes)': time_since_last_reading_min,
                         'Last Transmission': last_transmission, 'Expected Delay(minutes)': expected_delay, 'Median Time Difference': median_time})
        return [data]
    elif triggered_id == 'set-median-delay-button':
        for result in median_results:
            sensor_number = result["Sensor Number"]
            median_time = result["Median Time Difference"]
            if median_time != 'N/A':
                collection.update_one({'sensor_number': sensor_number}, {"$set": {'expected_delay': float(median_time.split()[0])}})
        return [[]]
    else:
        return [[]]

if __name__ == '__main__':
    app.run_server(debug=True)
