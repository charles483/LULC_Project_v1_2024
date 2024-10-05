import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
import geemap.foliumap as geemap
import json

# Path to the service account credentials file
SERVICE_ACCOUNT_FILE = r'C:\Users\c4708\Desktop\LULC_Project_v1_2024\ee-gisandremotesensing22-a03bb2841914.json'
# Initialize session state variables if they do not exist
if 'lulc_map' not in st.session_state:
    st.session_state['lulc_map'] = None
if 'lulc_year' not in st.session_state:
    st.session_state['lulc_year'] = None
if 'classifier_type' not in st.session_state:
    st.session_state['classifier_type'] = None
if 'forest_change_map' not in st.session_state:
    st.session_state['forest_change_map'] = None
if 'start_year' not in st.session_state:
    st.session_state['start_year'] = None
if 'end_year' not in st.session_state:
    st.session_state['end_year'] = None

# Initialize Earth Engine API using service account
def initialize_earth_engine(retries=3):
    attempt = 0
    message_placeholder = st.empty()  # Placeholder for dynamic messages
    while attempt < retries:
        try:
            service_account_info = json.load(open(SERVICE_ACCOUNT_FILE))
            credentials = ee.ServiceAccountCredentials(service_account_info['client_email'], SERVICE_ACCOUNT_FILE)
            ee.Initialize(credentials)

            # Display the success message temporarily
            message_placeholder.success("Earth Engine initialized successfully.")
            return  # Exit the function after success
        except Exception as e:
            message_placeholder.error(f"Failed to initialize Earth Engine: {str(e)}. Retrying...")
            attempt += 1

    # Final error message if retries fail
    message_placeholder.error("Unable to initialize Earth Engine after multiple attempts.")

# Call the function to initialize Earth Engine
initialize_earth_engine()

# Define GEE assets and AOI (Area of Interest)
training_samples = ee.FeatureCollection('projects/ee-samuelmuturigisdeveloper/assets/training_samplesL8_2015')
area_of_interest = ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level2') \
    .filter(ee.Filter.eq('ADM2_NAME', 'Nyeri')) \
    .first() \
    .geometry()

# Function to get the correct satellite image collection based on the year
def get_image_collection(year):
    if year <= 2012:
        # Landsat 5 (1984–2012)
        return ee.ImageCollection("LANDSAT/LT05/C02/T1_L2")
    elif 2013 <= year <= 2017:
        # Landsat 8 (2013–present)
        return ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") 
    else:
        # Sentinel-2 (2015–present)
        return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")

# Function to get LULC image for a specific year, with different bands for each sensor
def get_lulc_image(year, classifier_type):
    collection = get_image_collection(year).filterDate(f'{year}-01-01', f'{year}-12-31').median().clip(area_of_interest)
    
    if year <= 2012:  # Landsat 5
        bands = ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7']
    elif 2013 <= year <= 2017:  # Landsat 8
        bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
    else:  # Sentinel-2
        bands = ['B2', 'B3', 'B4', 'B8']
    
    classification_image = collection.select(bands)
    
    # Sample training data and train the classifier
    training = classification_image.sampleRegions(collection=training_samples, properties=['class'], scale=30)
    
    # Choose the classifier based on the user input
    if classifier_type == 'Random Forest':
        classifier = ee.Classifier.smileRandomForest(10).train(training, 'class', bands)
    elif classifier_type == 'SVM':
        classifier = ee.Classifier.libsvm().train(training, 'class', bands)
    elif classifier_type == 'CART':
        classifier = ee.Classifier.smileCart().train(training, 'class', bands)
    
    # Classify the image
    classified = classification_image.classify(classifier)
    return classified

# Function for forest change detection between two years
def detect_forest_change(start_year, end_year, classifier_type):
    lulc_start = get_lulc_image(start_year, classifier_type)
    lulc_end = get_lulc_image(end_year, classifier_type)
    
    forest_start = lulc_start.eq(1)  # Class 1 as forest
    forest_end = lulc_end.eq(1)
    
    forest_loss = forest_start.And(forest_end.Not())  # Forest loss detection
    return forest_loss

# Function to export GeoTIFF file
def export_map_as_geotiff(image, description):
    task = ee.batch.Export.image.toDrive(image=image,
                                         description=description,
                                         folder='GEE_exports',
                                         scale=30,
                                         region=area_of_interest,
                                         fileFormat='GeoTIFF')
    task.start()
    st.success(f"Export started for {description}. Check your Google Drive.")

# Streamlit App Interface
# Streamlit App Interface
st.title("LULC Classification & Forest Change Detection")

# Classifier selection
classifier_type = st.selectbox("Select Classifier", ['Random Forest', 'SVM', 'CART'])

# Year range selection
start_year = st.slider('Select start year', 2010, 2024, 2010)
end_year = st.slider('Select end year (for forest change detection)', 2010, 2024, 2024)

# LULC Classification section
st.subheader("Land Use Land Cover (LULC) Classification")
if st.button(f"Classify LULC for {start_year}"):
    st.write(f"Performing LULC classification for the year {start_year} using {classifier_type}...")

    lulc_image = get_lulc_image(start_year, classifier_type)
    
    if lulc_image is not None:  # Check if the image was generated
        # Create map for LULC
        map_lulc = geemap.Map(center=[ -0.436959,  36.957951], zoom=10)
        map_lulc.addLayer(lulc_image, {'min': 0, 'max': 5, 'palette': ['brown', 'green', 'yellow', 'red']}, f'LULC {start_year} ({classifier_type})')
        
        # Store map in session state for persistence
        st.session_state['lulc_map'] = map_lulc
        st.session_state['lulc_year'] = start_year
        st.session_state['classifier_type'] = classifier_type
    else:
        st.error("LULC image generation failed. Please check the parameters.")

# Persist the LULC map after initial classification
if 'lulc_map' in st.session_state and st.session_state['lulc_map'] is not None:
    st.write(f"LULC Map for {st.session_state['lulc_year']} using {st.session_state['classifier_type']} is displayed below.")
    st_folium(st.session_state['lulc_map'], width=700, height=500)

    # Export option
    if st.button(f'Download LULC {st.session_state["lulc_year"]} as GeoTIFF'):
        export_map_as_geotiff(get_lulc_image(st.session_state['lulc_year'], st.session_state['classifier_type']), f'lulc_{st.session_state["lulc_year"]}')

# Forest Change Detection section
st.subheader("Forest Change Detection")
if st.button(f"Detect forest changes from {start_year} to {end_year}"):
    st.write(f"Detecting forest changes between {start_year} and {end_year} using {classifier_type}...")

    forest_change = detect_forest_change(start_year, end_year, classifier_type)
    
    if forest_change is not None:  # Check if the forest change detection worked
        # Create map for forest change
        map_forest_change = geemap.Map(center=[ -0.436959,  36.957951], zoom=10)
        map_forest_change.addLayer(forest_change, {'min': 0, 'max': 1, 'palette': ['black', 'red']}, 'Forest Loss')
        
        # Store map in session state for persistence
        st.session_state['forest_change_map'] = map_forest_change
        st.session_state['start_year'] = start_year
        st.session_state['end_year'] = end_year
    else:
        st.error("Forest change detection failed. Please check the parameters.")

# Persist the forest change map after detection
if 'forest_change_map' in st.session_state and st.session_state['forest_change_map'] is not None:
    st.write(f"Forest Change Map from {st.session_state['start_year']} to {st.session_state['end_year']} using {st.session_state['classifier_type']} is displayed below.")
    st_folium(st.session_state['forest_change_map'], width=700, height=500)

    # Export option
    if st.button(f'Download Forest Change {st.session_state["start_year"]}-{st.session_state["end_year"]} as GeoTIFF'):
        export_map_as_geotiff(detect_forest_change(st.session_state['start_year'], st.session_state['end_year'], st.session_state['classifier_type']),
                              f'forest_change_{st.session_state["start_year"]}_{st.session_state["end_year"]}')

# Sidebar with instructions
st.sidebar.header("Instructions")
st.sidebar.markdown(""" 
1. Select a classifier (Random Forest, SVM, or CART).
2. Choose a year for LULC classification.
3. Detect forest changes between two years.
4. Export the classified image or forest change data as GeoTIFF to Google Drive.
""")
