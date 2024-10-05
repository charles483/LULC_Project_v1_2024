import streamlit as st
import pandas as pd

# Import your app functions
import app_functions  # Make sure this file is in the same directory or the Python path

# Custom CSS for buttons and styling
st.markdown("""
    <style>
    .button-container button {
        padding: 15px 40px;
        margin-right: 10px;
        background-color: #f0f0f0;
        border: none;
        cursor: pointer;
        font-size: 18px;
        font-weight: bold;
        border-radius: 8px;
        transition: background-color 0.3s ease;
    }

    .button-container button:hover {
        background-color: #dcdcdc;
    }

    .button-container button.active {
        background-color: #4CAF50;
        color: white;
        border: none;
    }

    .separator-line {
        border-top: 2px solid #ddd;
        margin: 20px 0;
    }
    </style>
""", unsafe_allow_html=True)

# Sidebar menu
st.sidebar.title("Menu")
menu_options = ["About Project", "LULC & forest change detection"]
selection = st.sidebar.radio("Navigate", menu_options)

# Task and Contributor Information
task_data = {
    "Task Name": [
        "Data Selection",
        "Data Collection",
        "Data Preprocessing and Visualization",
        "Model Development and Training",
        "Deployment and Dashboard"
    ],
    "Task Lead Name": [
        "Daria Akhbari",
        "Kaushik Roy",
        "Noelia",
        "Akhil Chibber",
        "Vinod Cherian"
    ]
}

# Create a DataFrame for tasks
task_df = pd.DataFrame(task_data)

# Contributors list
contributors = [
    "Abhi Agarwal", "Akhil Chibber", "Daria Akhbari", 
    "Deepali", "Deepanshu Rajput", "Elias Dzobo", 
    "Getrude Obwoge", "Joseph N. Moturi", "Kaushik Roy", 
    "Noelia", "Rayy Benhin", "Sanjiv", "Sugandaram M", 
    "Vinod Cherian", "Yaninthé"
]

# Sort contributors alphabetically
sorted_contributors = sorted(contributors)

# Track active tab
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = 'About Project'

# Main content
if selection == "About Project":
    st.title("About Project")

    # Create horizontal buttons for tabs
    col1, col2 = st.columns(2)

    with col1:
        if st.button("About Project", key="about"):
            st.session_state.active_tab = "About Project"

    with col2:
        if st.button("Active Team Contributors", key="contributors"):
            st.session_state.active_tab = "Active Team Contributors"

    # Apply CSS class to active button
    st.markdown(f"""
    <script>
        const about_btn = window.parent.document.querySelector('button[data-testid="stButton"][key="about"]');
        const contrib_btn = window.parent.document.querySelector('button[data-testid="stButton"][key="contributors"]');
        
        if ('{st.session_state.active_tab}' == 'About Project') {{
            about_btn.classList.add('active');
            contrib_btn.classList.remove('active');
        }} else {{
            contrib_btn.classList.add('active');
            about_btn.classList.remove('active');
        }}
    </script>
    """, unsafe_allow_html=True)

    # Separation line
    st.markdown('<div class="separator-line"></div>', unsafe_allow_html=True)

    # Display content based on the active tab
    if st.session_state.active_tab == "About Project":
        st.subheader("This project is initiated by the Land View Detectives to solve Real World Problems.")
        st.write(""" 
        ## The Problem
        Mapping land use and land cover categories over time is essential for environmental monitoring, urban planning, and climate adaptation.
        This project aims to build a Machine Learning model to classify Land Use and Land Cover (LULC) in satellite imagery.
        The project results will be open source, connecting local organizations and communities with AI tools to address local challenges like land use monitoring.
        """)
        
        st.write(""" 
        ## The Goals
        The goals of this project are:
        - A Web GIS dashboard containing LULC Map of the region of interest.
        - The best-performing ML model(s).
        - Datasets collected during the project available on Google Drive.
        - A well-documented open-source GitHub repository.
        - Documentation of the work and approach.
        """)
    
    elif st.session_state.active_tab == "Active Team Contributors":
        st.subheader("Active Team Contributors")
        st.write("This section features active contributors to the project and their roles.")
        st.subheader("Task Assignments")
        st.table(task_df)
        st.subheader("Active Contributors (a-z order)")
        st.write(", ".join(sorted_contributors))

# Handle LULC & forest change detection selection
elif selection == "LULC & forest change detection":
    st.title("LULC & Forest Change Detection")
    
    # Call the function from app_functions.py
    app_functions.run_lulc_detection()  # Make sure to define this function in app_functions.py
