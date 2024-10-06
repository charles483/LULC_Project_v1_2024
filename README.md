Here's a more concise version of the project setup with acknowledgments:

---

# LULC Classification and Forest Change Detection App

## Setup

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Create a Virtual Environment** (optional):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: `venv\Scripts\activate`
   ```

3. **Install Dependencies**:
   ```bash
   pip install streamlit geemap folium earthengine-api
   ```

4. **Set Up Google Earth Engine (GEE)**:
   - Obtain your **service account credentials** JSON file from your GEE account.
   - Place it in the project directory.
   - Update the `SERVICE_ACCOUNT_FILE` variable in your code with the path to the JSON file:
     ```python
     SERVICE_ACCOUNT_FILE = 'path/to/your/credentials-file.json'
     ```

## Usage

1. **Run the App**:
   ```bash
   streamlit run app.py
   ```

2. **Open in Browser**: Go to `http://localhost:8501`.

3. **Instructions**:
   - Select a classifier (Random Forest, SVM, or CART).
   - Choose a year for LULC classification.
   - Detect forest changes between two years.
   - Export results as GeoTIFF to Google Drive.

## Acknowledgments
- [Google Earth Engine](https://earthengine.google.com/)
- [Streamlit](https://streamlit.io/)
- [Folium](https://python-visualization.github.io/folium/)
- [Geemap](https://geemap.org/)

---
