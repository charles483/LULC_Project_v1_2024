import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
import geemap.foliumap as geemap
import json
import plotly.express as px
import pandas as pd

# Path to the service account credentials file
SERVICE_ACCOUNT_FILE = r'D:\LULC_Project_v1_2024\secrets.json'

# Initialize session state variables if they do not exist
if 'lulc_map' not in st.session_state:
    st.session_state['lulc_map'] = None
if 'lulc_year' not in st.session_state:
    st.session_state['lulc_year'] = None
if 'classifier_type' not in st.session_state:
    st.session_state['classifier_type'] = None
if 'lulc_stats' not in st.session_state:
    st.session_state['lulc_stats'] = None
if 'lulc_image' not in st.session_state:
    st.session_state['lulc_image'] = None

# Initialize Earth Engine API using service account
def initialize_earth_engine(retries=3):
    attempt = 0
    message_placeholder = st.empty()  # Placeholder for dynamic messages
    while attempt < retries:
        try:
            service_account_info = json.load(open(SERVICE_ACCOUNT_FILE))
            credentials = ee.ServiceAccountCredentials(service_account_info['client_email'], SERVICE_ACCOUNT_FILE)
            ee.Initialize(credentials)
            message_placeholder.success("Earth Engine initialized successfully.")
            return  # Exit the function after success
        except Exception as e:
            message_placeholder.error(f"Failed to initialize Earth Engine: {str(e)}. Retrying...")
            attempt += 1
    message_placeholder.error("Unable to initialize Earth Engine after multiple attempts.")

# Call the function to initialize Earth Engine
initialize_earth_engine()

# Define GEE assets and AOI (Area of Interest)
training_samples = ee.FeatureCollection('projects/ee-samuelmuturigisdeveloper/assets/training_samplesL8_2015')
area_of_interest = ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level2') \
    .filter(ee.Filter.eq('ADM2_NAME', 'Nyeri')) \
    .first() \
    .geometry()

# Function to mask clouds based on the satellite used
def mask_clouds(image, satellite):
    if satellite == "Landsat 8":
        qa = image.select('QA_PIXEL')
        cloud_mask = qa.bitwiseAnd(1 << 3).eq(0)  # Bit 3 is cloud
        cloud_shadow_mask = qa.bitwiseAnd(1 << 4).eq(0)  # Bit 4 is cloud shadow
        return image.updateMask(cloud_mask).updateMask(cloud_shadow_mask)
    elif satellite == "Sentinel-2":
        qa = image.select('QA60')
        cloud_bit_mask = 1 << 10  # Bit 10 is clouds
        cirrus_bit_mask = 1 << 11  # Bit 11 is cirrus clouds
        mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
        return image.updateMask(mask)
    return image  # No masking for Landsat 5

# Function to get the correct satellite image collection based on the year
def get_image_collection(year):
    if year <= 2012:
        return ee.ImageCollection("LANDSAT/LT05/C02/T1_L2")
    elif 2013 <= year <= 2017:
        return ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").map(lambda img: mask_clouds(img, "Landsat 8"))
    else:
        return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").map(lambda img: mask_clouds(img, "Sentinel-2"))

# Function to get LULC image for a specific year, with cloud masking and gap filling
def get_lulc_image(year, classifier_type):
    collection = get_image_collection(year) \
        .filterDate(f'{year}-01-01', f'{year}-12-31') \
        .median() \
        .clip(area_of_interest)

    # Select appropriate bands and training samples based on the year
    local_training_samples = training_samples if year <= 2024 else None

    if year <= 2012:  # Landsat 5
        bands = ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7']
    elif 2013 <= year <= 2017:  # Landsat 8
        bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
    else:  # Sentinel-2
        bands = ['B2', 'B3', 'B4', 'B8']

    classification_image = collection.select(bands)
    training = classification_image.sampleRegions(collection=local_training_samples, properties=['class'], scale=30)

    classifier = None
    if classifier_type == 'Random Forest':
        classifier = ee.Classifier.smileRandomForest(100).train(training, 'class', bands)
    elif classifier_type == 'SVM':
        classifier = ee.Classifier.libsvm().train(training, 'class', bands)
    elif classifier_type == 'CART':
        classifier = ee.Classifier.smileCart().train(training, 'class', bands)

    if classifier is not None:
        classified = classification_image.classify(classifier)
        return classified
    return None

# Function to calculate LULC statistics
def calculate_lulc_statistics(lulc_image):
    class_values = [0, 1, 2, 3]  # Assuming 4 classes for simplicity
    class_names = ['Bareland', 'Forest', 'Builtup', 'Agriculture']
    pixel_area = ee.Image.pixelArea()

    # Create an empty dictionary to store the results
    lulc_stats = {}

    # Loop through each class and calculate the area
    for class_value, class_name in zip(class_values, class_names):
        class_mask = lulc_image.eq(class_value)
        area = pixel_area.updateMask(class_mask).reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=area_of_interest,
            scale=30,
            maxPixels=1e9
        )
        area_hectares = ee.Number(area.get('area')).divide(10000).getInfo()
        lulc_stats[class_name] = area_hectares
    
    return lulc_stats

# Streamlit App Interface
st.title("LULC Classification & Forest Change Detection")

# Classifier selection
classifier_type = st.selectbox("Select Classifier", ['Random Forest', 'SVM', 'CART'])

# Year selection for LULC classification
start_year = st.slider('Select year for LULC classification', 2010, 2024, 2010)
end_year = st.slider('Select year for change detection', 2010, 2024, 2010)

# LULC Classification section
st.subheader("Land Use Land Cover (LULC) Classification")
if st.button(f"Classify LULC for {start_year}"):
    st.write(f"Performing LULC classification for the year {start_year} using {classifier_type}...")
    with st.spinner("Processing..."):
        lulc_image = get_lulc_image(start_year, classifier_type)
    
    if lulc_image is not None:
        # Calculate LULC statistics
        lulc_stats = calculate_lulc_statistics(lulc_image)
        st.session_state['lulc_stats'] = lulc_stats
        st.session_state['lulc_image'] = lulc_image

        # Create map for LULC
        map_lulc = geemap.Map(center=[-0.436959, 36.957951], zoom=10)
        map_lulc.addLayer(lulc_image, {'min': 0, 'max': 3, 'palette': ['#C2B280', '#4CAF50', '#FFD700', 'red']}, f'LULC {start_year} ({classifier_type})')
        
        # Add a legend
        legend_html = """
        <div style="position: fixed; bottom: 50px; left: 50px; width: 150px; height: 120px;
                background-color: white; border: 2px solid black; z-index:9999; font-size:14px;">
        &nbsp;<b>LULC Legend</b><br>
        &nbsp;<i style="background: #C2B280"></i>&nbsp;Urban<br>
        &nbsp;<i style="background: #4CAF50"></i>&nbsp;Forest<br>
        &nbsp;<i style="background: #FFD700"></i>&nbsp;Water<br>
        &nbsp;<i style="background: red"></i>&nbsp;Agriculture<br>
        </div>
        """
        map_lulc.get_root().html.add_child(folium.Element(legend_html))
        
        map_lulc.addLayerControl()
        st.session_state['lulc_map'] = map_lulc
        st.session_state['lulc_year'] = start_year
        st.session_state['classifier_type'] = classifier_type
    else:
        st.error("LULC image generation failed. Please check the parameters.")

# Functionality for Change Detection
if st.button(f"Detect Change for {end_year}"):
    if st.session_state['lulc_image'] is not None:
        st.write(f"Detecting change in forest cover between {start_year} and {end_year}...")
        with st.spinner("Processing..."):
            lulc_image_end_year = get_lulc_image(end_year, classifier_type)
            if lulc_image_end_year is not None:
                forest_change = lulc_image_end_year.eq(1).subtract(st.session_state['lulc_image'].eq(1))
                
                map_change = geemap.Map(center=[-0.436959, 36.957951], zoom=10)
                map_change.addLayer(forest_change, {'min': -1, 'max': 1, 'palette': ['red', 'white', 'green']}, f'Forest Change {start_year} to {end_year}')
                
                st.write("Change detection completed.")
                st_folium(map_change, width=725)
            else:
                st.error("Change detection failed. Ensure both years have valid data.")
    else:
        st.error("Please run LULC classification first.")

# Display LULC statistics
if st.session_state['lulc_stats']:
    st.subheader("LULC Statistics")
    stats_df = pd.DataFrame(list(st.session_state['lulc_stats'].items()), columns=['LULC Class', 'Area (Hectares)'])
    st.dataframe(stats_df)

# Export functionality
if st.session_state['lulc_image']:
    export_button = st.button('Export Classified Image to Google Drive')
    if export_button:
        # Export classified image to Google Drive
        task = ee.batch.Export.image.toDrive(
            image=st.session_state['lulc_image'],
            description=f'LULC_Classification_{st.session_state["lulc_year"]}',
            scale=30,
            region=area_of_interest,
            maxPixels=1e9
        )
        task.start()
        st.success('Export task started. Check your Google Drive.')

# User feedback messages
if st.session_state['lulc_map']:
    st.subheader("LULC Map")
    st_folium(st.session_state['lulc_map'], width=725)

# Sidebar with instructions
st.sidebar.header("Instructions")
st.sidebar.markdown(""" 
1. Select a classifier (Random Forest, SVM, or CART).
2. Choose a year for LULC classification.
3. Detect forest changes between two years.
4. Export the classified image or forest change data as GeoTIFF to Google Drive.
""")
