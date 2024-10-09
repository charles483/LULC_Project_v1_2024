
import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
import geemap.foliumap as geemap
# import json    if you want to use authentication file from google earth engine service account json file uncomment this line and the function below

# Path to the service account credentials file
SERVICE_ACCOUNT_FILE = r'D:\LULC_Project_v1_2024\secrets.json'

# Initialize session state variables
session_vars = ['lulc_map', 'lulc_year', 'classifier_type', 'lulc_image', 'forest_change_image', 'forest_change_map']
for var in session_vars:
    if var not in st.session_state:
        st.session_state[var] = None

# Authenticate and initialize Earth Engine with a specific project
ee.Authenticate()  # This opens a browser for OAuth2 authentication
ee.Initialize(project='ee-gisandremotesensing22')  # Replace with your actual project ID

# Your further Earth Engine code goes here
print("Earth Engine has been initialized with the project ID.")
# # Function to initialize Earth Engine API
# def initialize_earth_engine(retries=3):
#     message_placeholder = st.empty()
#     attempt = 0
#     while attempt < retries:
#         try:
#             service_account_info = json.load(open(SERVICE_ACCOUNT_FILE))
#             credentials = ee.ServiceAccountCredentials(service_account_info['client_email'], SERVICE_ACCOUNT_FILE)
#             ee.Initialize(credentials)
#             message_placeholder.success("Earth Engine initialized successfully.")
#             return
#         except Exception as e:
#             message_placeholder.error(f"Failed to initialize Earth Engine: {str(e)}. Retrying...")
#             attempt += 1
#     message_placeholder.error("Unable to initialize Earth Engine after multiple attempts.")

# initialize_earth_engine()

# Define GEE assets and AOI
samples_by_year = {
    2010: ee.FeatureCollection('projects/glassy-compiler-400707/assets/samples2010'),
    2015: ee.FeatureCollection('projects/ee-gisandremotesensing22/assets/Landsat8_2015_Sampled_Region'),
    2020: ee.FeatureCollection('projects/glassy-compiler-400707/assets/samples2020'),
    2024: ee.FeatureCollection('projects/glassy-compiler-400707/assets/samples2020')
}

# Define Area of Interest (AOI) for Nyeri region
area_of_interest = ee.FeatureCollection('FAO/GAUL_SIMPLIFIED_500m/2015/level2') \
    .filter(ee.Filter.eq('ADM2_NAME', 'Nyeri')) \
    .first() \
    .geometry()

# Function to mask clouds based on satellite type
def mask_clouds(image, satellite):
    if satellite == "Landsat 5" or satellite == "Landsat 7":
        # Use the pixel QA band to mask clouds and shadows for Landsat 5 and 7
        qa = image.select('QA_PIXEL')
        cloud_mask = qa.bitwiseAnd(1 << 5).eq(0)  # Cloud bit
        cloud_shadow_mask = qa.bitwiseAnd(1 << 3).eq(0)  # Cloud shadow bit
        return image.updateMask(cloud_mask).updateMask(cloud_shadow_mask)
    elif satellite == "Landsat 8":
        # Use the pixel QA band for Landsat 8
        qa = image.select('QA_PIXEL')
        cloud_mask = qa.bitwiseAnd(1 << 3).eq(0)  # Cloud bit
        cloud_shadow_mask = qa.bitwiseAnd(1 << 4).eq(0)  # Cloud shadow bit
        return image.updateMask(cloud_mask).updateMask(cloud_shadow_mask)
    elif satellite == "Sentinel-2":
        # Use the QA60 band for cloud and cirrus masking for Sentinel-2
        qa = image.select('QA60')
        cloud_bit_mask = 1 << 10
        cirrus_bit_mask = 1 << 11
        mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
        return image.updateMask(mask)
    return image

# Function to retrieve image collection for a specific year
def get_image_collection(year):
    if year <= 2012:
        return ee.ImageCollection("LANDSAT/LT05/C02/T1_L2").map(lambda img: mask_clouds(img, "Landsat 5"))
    elif 2013 <= year <= 2017:
        return ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").map(lambda img: mask_clouds(img, "Landsat 8"))
    else:
        return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").map(lambda img: mask_clouds(img, "Sentinel-2"))

# Now the cloud masking will be applied before median compositing


# Function to retrieve and classify LULC image using year-specific samples
def get_lulc_image(year, classifier_type):
    collection = get_image_collection(year).filterDate(f'{year}-01-01', f'{year}-12-31').median().clip(area_of_interest)
    
    if year <= 2012:
        bands = ['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7']
    elif 2013 <= year <= 2017:
        bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
    else:
        bands = ['B2', 'B3', 'B4', 'B8']

    classification_image = collection.select(bands)
    training_samples = samples_by_year.get(year)
    if not training_samples:
        st.error(f"No training samples available for the year {year}")
        return None

    training = classification_image.sampleRegions(collection=training_samples, properties=['class'], scale=30)
    classifier = None
    if classifier_type == 'Random Forest':
        classifier = ee.Classifier.smileRandomForest(100).train(training, 'class', bands)
    elif classifier_type == 'SVM':
        classifier = ee.Classifier.libsvm().train(training, 'class', bands)
    elif classifier_type == 'CART':
        classifier = ee.Classifier.smileCart().train(training, 'class', bands)

    if classifier is not None:
        classified_image = classification_image.classify(classifier)
        return classified_image
    return None

## Function to calculate forest change between two years
def calculate_forest_change(start_year, end_year, classifier_type):
    start_image = get_lulc_image(start_year, classifier_type)
    end_image = get_lulc_image(end_year, classifier_type)
    
    if start_image is None or end_image is None:
        st.error(f"Unable to retrieve classified images for the years {start_year} or {end_year}")
        return None

    # Create binary masks for forests (assuming 0 indicates forest cover)
    forest_start = start_image.eq(0)  # Forests in the start year
    forest_end = end_image.eq(0)      # Forests in the end year

    # Calculate area covered by forest in both years
    initial_forest_area = forest_start.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=start_image.geometry(),
        scale=30  # Adjust scale as necessary for your data
    ).getInfo().get('classification')  # Replace 'classification' with the correct property name

    final_forest_area = forest_end.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=end_image.geometry(),
        scale=30  # Adjust scale as necessary for your data
    ).getInfo().get('classification')  # Replace 'classification' with the correct property name

    # Ensure initial_forest_area and final_forest_area are numeric
    initial_forest_area = int(initial_forest_area) if initial_forest_area is not None else 0
    final_forest_area = int(final_forest_area) if final_forest_area is not None else 0

    # Calculate the change in forest area
    forest_change = final_forest_area - initial_forest_area

    # Create a forest change image
    forest_change_image = forest_end.subtract(forest_start).rename('forest_change')

    # Determine gain or loss
    if forest_change > 0:
        change_description = f"Gain of {forest_change} pixels of forest cover."
    elif forest_change < 0:
        change_description = f"Loss of {-forest_change} pixels of forest cover."
    else:
        change_description = "No change in forest cover."

    # Output the results
    st.success(change_description)
    st.write(f"Initial forest area: {initial_forest_area} pixels")
    st.write(f"Final forest area: {final_forest_area} pixels")

    return forest_change_image  # Return the forest change image for visualization

import pandas as pd

# Authenticate and initialize Earth Engine with a specific project
ee.Authenticate()  # This opens a browser for OAuth2 authentication
ee.Initialize(project='ee-gisandremotesensing22')  # Replace with your actual project ID

import pandas as pd
# import streamlit as st

# Function to display a legend table below the map
def display_legend_table(legend_dict, title):
    # Create a DataFrame for the legend
    legend_data = {
        'Class': list(legend_dict.keys()),
        'Color': list(legend_dict.values())
    }
    df_legend = pd.DataFrame(legend_data)

    # Define a function to apply background colors
    def colorize(row):
        return ['background-color: ' + row['Color']] * len(row)

    # Display the table with styling
    st.write(f"<h4 style='text-align:center;'>{title}</h4>", unsafe_allow_html=True)
    st.table(df_legend.style.apply(colorize, axis=1))


# Function to display forest change image
def display_forest_change(forest_change_image):
    map_change = geemap.Map(center=[-0.436959, 36.957951], zoom=10)
    map_change.addLayer(forest_change_image, {'min': -1, 'max': 1, 'palette': ['#FF0000', '#FFFFFF', '#006400']}, 'Forest Change')
    st_folium(map_change, width=700, height=500)
    
    # Forest Change Legend as a Dictionary
    forest_change_legend = {
        "Loss": "#FF0000",  # Red for forest loss
        "No Change": "#FFFFFF",  # White for no change
        "Gain": "#006400"  # Dark green for forest gain
    }
    display_legend_table(forest_change_legend, "Forest Change Detection Legend")

# Streamlit UI
st.title("Land Use and Land Cover Classification & Forest Change Detection")

# Initialize session state
if 'lulc_image' not in st.session_state:
    st.session_state['lulc_image'] = None
if 'forest_change_image' not in st.session_state:
    st.session_state['forest_change_image'] = None
if 'lulc_map' not in st.session_state:
    st.session_state['lulc_map'] = None

classifier_type = st.selectbox("Select Classifier", ['Random Forest', 'SVM', 'CART'])
available_years = [2010, 2015, 2020, 2024]

start_year = st.select_slider("Select year for LULC classification", options=available_years, value=available_years[0])
end_year = st.select_slider("Select year for change detection", options=available_years, value=start_year)

# LULC Classification Palette
lulc_palette = {
    "Forest": "#228B22",
    "Bareland": "#D2B48C",
    "Built-up": "#FF6347",
    "Others": "#808080"
}

# Display LULC Classification
st.subheader("LULC Classification")
if st.button(f"Classify LULC for {start_year}"):
    with st.spinner(f"Classifying LULC for {start_year} using {classifier_type}..."):
        lulc_image = get_lulc_image(start_year, classifier_type)
        if lulc_image:
            st.session_state['lulc_image'] = lulc_image
            map_lulc = geemap.Map(center=[-0.436959, 36.957951], zoom=10)
            map_lulc.addLayer(lulc_image, {'min': 0, 'max': 3, 'palette': list(lulc_palette.values())}, f"LULC {start_year}")
            st.session_state['lulc_map'] = map_lulc
            st_folium(map_lulc, width=700, height=500)
            st.success(f"LULC Classification for {start_year} completed!")
            
            # LULC Legend Table
            display_legend_table(lulc_palette, f"LULC {start_year} Legend")
        else:
            st.error("LULC Classification failed. Please check the logs for details.")


# Display previously classified LULC map if available
if st.session_state['lulc_map']:
    st.subheader(f"Persisted LULC Classification Map for {start_year}")
    st_folium(st.session_state['lulc_map'], width=700, height=500)
    display_legend_table(lulc_palette, f"LULC {start_year} Legend")

# Forest Change Detection Section
st.subheader("Forest Change Detection")
if st.button(f"Detect Forest Change from {start_year} to {end_year} using {classifier_type}"):
    with st.spinner(f"Detecting forest change from {start_year} to {end_year}..."):
        forest_change_image = calculate_forest_change(start_year, end_year, classifier_type)
        if forest_change_image:
            st.session_state['forest_change_image'] = forest_change_image  # Store in session state
            display_forest_change(forest_change_image)
            st.success(f"Forest change detection from {start_year} to {end_year} completed!")
        else:
            st.error("Forest change detection failed. Please check the logs for details.")

# Display previously detected forest change map if available
if st.session_state['forest_change_image']:
    st.subheader(f"Persisted Forest Change Map from {start_year} to {end_year}")
    display_forest_change(st.session_state['forest_change_image'])

# Display Maps
if st.session_state['lulc_map']:
    st.subheader(f"LULC Map for {start_year}")
    st_folium(st.session_state['lulc_map'], width=700, height=500)

if st.session_state['forest_change_map']:
    st.subheader(f"Forest Change Map from {start_year} to {end_year}")
    st_folium(st.session_state['forest_change_map'], width=700, height=500)

# Add a reset button to clear the session state
if st.button("Reset"):
    for var in session_vars:
        st.session_state[var] = None
    st.success("Session state has been reset.")

# Add the necessary imports
import os

# Function to export image to GeoTIFF
def export_to_geotiff(image, filename):
    try:
        # Ensure the filename has the correct .tif extension
        if not filename.endswith('.tif'):
            filename += '.tif'
        
        # Define the export task
        task = ee.batch.Export.image.toDrive(
            image=image,
            description=filename,
            scale=30,
            region=image.geometry().bounds(),
            fileFormat='GeoTIFF'
        )
        task.start()
        
        # Wait for the task to complete
        while task.active():
            print('Exporting to GeoTIFF...')
        
        st.success(f"Exported {filename} successfully!")
        
    except Exception as e:
        st.error(f"Failed to export image: {str(e)}")


# Export buttons
if st.session_state['lulc_image']:
    if st.button("Export LULC Image to GeoTIFF"):
        filename = st.text_input("Enter filename for LULC GeoTIFF", "LULC_{}.tif".format(start_year))
        export_to_geotiff(st.session_state['lulc_image'], filename)

if st.session_state['forest_change_image']:
    if st.button("Export Forest Change Image to GeoTIFF"):
        filename = st.text_input("Enter filename for Forest Change GeoTIFF", "Forest_Change_{}_to_{}.tif".format(start_year, end_year))
        export_to_geotiff(st.session_state['forest_change_image'], filename)

# Sidebar with instructions
st.sidebar.header("Instructions")
st.sidebar.markdown(""" 
1. Select a classifier (Random Forest, SVM, or CART).
2. Choose a year for LULC classification.
3. Detect forest changes between two years.
4. Export the classified image or forest change data as GeoTIFF to Google Drive.
""")
def display_links():
    st.sidebar.header("Contact & Resources")
    st.sidebar.markdown(
        """
        - **Email**: [charleschuru94@gmail.com](mailto:charleschuru94@gmail.com)
        - **GitHub Repository**: [View Repository](https://github.com/charles483/LULC_Project_v1_2024/)
        - **Documentation Site**: [Documentation](https://charles483.github.io/pages/)
        """
    )

# Call the function to display the links
display_links()

# Footer CSS
footer_css = """
<style>
.sticky-footer {
    position: fixed;
    left: 0;
    bottom: 0;
    width: 100%;
    background: linear-gradient(to right, #4CAF50, #2196F3);
    color: #FFFFFF;
    text-align: center;
    font-size: 1em;
    padding: 15px 0;
    border-top: 2px solid #FFC107;
    box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.3);
}

a {
    color: #FFFFFF;
    text-decoration: none;
}

.footer-links {
    margin-top: 10px;
}

.footer-links a {
    color: #FFC107;
}
</style>
"""
st.markdown(footer_css, unsafe_allow_html=True)
st.markdown("<div class='sticky-footer'>Made with ❤️ by Charles Churu | <a href='#'>Project Details</a></div>", unsafe_allow_html=True)
