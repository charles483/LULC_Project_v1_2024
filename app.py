import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
import geemap.foliumap as geemap
import json
import plotly.graph_objects as go
from ee import batch
import geopandas as gpd
from io import BytesIO

# Path to the service account credentials file
SERVICE_ACCOUNT_FILE = r'C:\Users\c4708\Desktop\LULC_Project_v1_2024\ee-gisandremotesensing22-a03bb2841914.json'

# Initialize session state variables if they do not exist
if 'lulc_map' not in st.session_state:
    st.session_state['lulc_map'] = None
if 'forest_change_map' not in st.session_state:
    st.session_state['forest_change_map'] = None
if 'lulc_image' not in st.session_state:
    st.session_state['lulc_image'] = None

# Initialize Earth Engine API using service account
def initialize_earth_engine():
    try:
        service_account_info = json.load(open(SERVICE_ACCOUNT_FILE))
        credentials = ee.ServiceAccountCredentials(service_account_info['client_email'], SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials)
        st.success("Earth Engine initialized successfully.")
    except Exception as e:
        st.error(f"Failed to initialize Earth Engine: {str(e)}")

# Function to get the correct satellite image collection based on the year
def get_image_collection(year):
    if year <= 2012:
        return ee.ImageCollection("LANDSAT/LT05/C02/T1_L2")  # Landsat 5
    elif 2013 <= year <= 2017:
        return ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")  # Landsat 8
    else:
        return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")  # Sentinel-2

# Function to get LULC image for a specific year
def get_lulc_image(year, classifier_type, area_of_interest, training_samples):
    collection = get_image_collection(year)
    
    # Define bands for different years
    bands = {
        2012: ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7'],
        2017: ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'],
        'default': ['B2', 'B3', 'B4', 'B8']  # Default bands for Sentinel-2
    }
    
    # Get the bands for the specific year
    band_keys = bands.get(year, bands['default'])

    image = collection.filterDate(f'{year}-01-01', f'{year}-12-31').median().clip(area_of_interest)
    image = image.reproject(crs='EPSG:4326', scale=60)
    training = image.sampleRegions(collection=training_samples, properties=['class'], scale=30)

    classifier = {
        'Random Forest': ee.Classifier.smileRandomForest(10),
        'SVM': ee.Classifier.libsvm(),
        'CART': ee.Classifier.smileCart()
    }.get(classifier_type)

    if classifier:
        classifier = classifier.train(training, 'class', band_keys)
        classified = image.classify(classifier)
        return classified
    else:
        st.error("Classifier type is not valid.")
        return None

# Function for forest change detection between two years
def detect_forest_change(start_year, end_year, classifier_type, area_of_interest, training_samples):
    lulc_start = get_lulc_image(start_year, classifier_type, area_of_interest, training_samples)
    lulc_end = get_lulc_image(end_year, classifier_type, area_of_interest, training_samples)

    forest_start = lulc_start.eq(1)  # Class 1 as forest
    forest_end = lulc_end.eq(1)

    # Detect forest loss
    forest_loss = forest_start.And(forest_end.Not())
    return forest_loss, lulc_start, lulc_end

# Function to calculate area of each class
def calculate_area(classified_image, area_of_interest):
    class_values = classified_image.reduceRegion(
        reducer=ee.Reducer.countBands(),
        geometry=area_of_interest,
        scale=30,
        maxPixels=1e9
    ).getInfo()
    
    areas = {key: value * (30 * 30) for key, value in class_values.items()}
    return areas

# Function to export GeoTIFF file
def export_map_as_geotiff(image, description, area_of_interest):
    task = ee.batch.Export.image.toDrive(image=image,
                                         description=description,
                                         folder='GEE_exports',
                                         scale=30,
                                         region=area_of_interest,
                                         fileFormat='GeoTIFF')
    task.start()
    st.success(f"Export started for {description}. Check your Google Drive.")

# Function to plot time series chart
def plot_time_series(years, forest_areas):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=years, y=forest_areas, mode='lines+markers', name='Forest Area (m²)'))
    fig.update_layout(title='Forest Area Change Over Time',
                      xaxis_title='Year',
                      yaxis_title='Area (m²)',
                      xaxis=dict(tickmode='linear'),
                      yaxis=dict(title='Area (m²)'))
    st.plotly_chart(fig)

# Function to upload shapefile
def upload_shapefile():
    uploaded_file = st.file_uploader("Upload Shapefile (.zip)", type=["zip"])
    if uploaded_file:
        with zipfile.ZipFile(uploaded_file, "r") as zip_ref:
            zip_ref.extractall("temp_shapefile")
        gdf = gpd.read_file("temp_shapefile/" + zip_ref.namelist()[0])
        return gdf
    return None

# Streamlit App Interface
st.title("LULC Classification & Forest Change Detection")

# Call the function to initialize Earth Engine
initialize_earth_engine()

# Define GEE assets and AOI (Area of Interest)
training_samples = ee.FeatureCollection('projects/ee-samuelmuturigisdeveloper/assets/training_samplesL8_2015')
area_of_interest = ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level2') \
    .filter(ee.Filter.eq('ADM2_NAME', 'Nyeri')) \
    .first() \
    .geometry()

# Classifier selection
classifier_type = st.selectbox("Select Classifier", ['Random Forest', 'SVM', 'CART'])

# Year range selection
start_year = st.slider('Select start year', 2010, 2024, 2010)
end_year = st.slider('Select end year (for forest change detection)', start_year, 2024, 2024)

# LULC Classification section
st.subheader("Land Use Land Cover (LULC) Classification")
if st.button(f"Classify LULC for {start_year}"):
    st.write(f"Performing LULC classification for the year {start_year} using {classifier_type}...")
    lulc_image = get_lulc_image(start_year, classifier_type, area_of_interest, training_samples)
    
    if lulc_image is not None:
        # Create map for LULC
        map_lulc = geemap.Map(center=[-0.436959, 36.957951], zoom=10)
        map_lulc.addLayer(lulc_image, {'min': 0, 'max': 5, 'palette': ['brown', 'green', 'yellow', 'red']}, f'LULC {start_year} ({classifier_type})')
        
        # Store the LULC image in session state for later use
        st.session_state['lulc_image'] = lulc_image
        st.session_state['lulc_map'] = map_lulc
    else:
        st.error("LULC image generation failed. Please check the parameters.")

# Persist the LULC map after initial classification
if 'lulc_map' in st.session_state and st.session_state['lulc_map'] is not None:
    st.write(f"LULC Map for {start_year} using {classifier_type} is displayed below.")
    st_folium(st.session_state['lulc_map'], width=700, height=500)

    # Area calculation for LULC
    if 'lulc_image' in st.session_state:
        areas = calculate_area(st.session_state['lulc_image'], area_of_interest)
        st.write("Area of each land cover class (in square meters):")
        st.write(areas)

    # Export option
    if st.button(f'Download LULC {start_year} as GeoTIFF'):
        export_map_as_geotiff(st.session_state['lulc_image'], f'lulc_{start_year}', area_of_interest)

# Forest Change Detection section
st.subheader("Forest Change Detection")
if st.button(f"Detect forest changes from {start_year} to {end_year}"):
    st.write(f"Detecting forest changes between {start_year} and {end_year} using {classifier_type}...")
    
    forest_areas = []
    years = list(range(start_year, end_year + 1))
    
    for year in years:
        lulc_image = get_lulc_image(year, classifier_type, area_of_interest, training_samples)
        if lulc_image is not None:
            forest_area = calculate_area(lulc_image, area_of_interest).get(1, 0)  # Assuming class 1 is forest
            forest_areas.append(forest_area)
        else:
            forest_areas.append(0)
    
    # Plotting time series
    plot_time_series(years, forest_areas)

    # Detect forest change
    forest_loss, lulc_start, lulc_end = detect_forest_change(start_year, end_year, classifier_type, area_of_interest, training_samples)
    
    if forest_loss:
        # Create map for forest change
        map_forest_change = geemap.Map(center=[-0.436959, 36.957951], zoom=10)
        map_forest_change.addLayer(forest_loss, {'palette': ['red']}, f'Forest Loss from {start_year} to {end_year}')
        st.session_state['forest_change_map'] = map_forest_change
        
        st_folium(st.session_state['forest_change_map'], width=700, height=500)

        # Export option for forest loss map
        if st.button(f'Download Forest Change Map as GeoTIFF'):
            export_map_as_geotiff(forest_loss, f'forest_change_{start_year}_{end_year}', area_of_interest)

# Upload shapefile section
st.subheader("Upload Shapefile for Custom Area of Interest")
gdf = upload_shapefile()
if gdf is not None:
    st.write("Uploaded shapefile geometry:")
    st.write(gdf.head())
    st.write("Visualizing uploaded shapefile on map...")
    
    # Visualize uploaded shapefile
    map_upload = folium.Map(location=[-0.436959, 36.957951], zoom_start=10)
    folium.GeoJson(gdf).add_to(map_upload)
    st_folium(map_upload, width=700, height=500)

st.write("Made with ❤️ by Charles Churu")
