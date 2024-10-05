
2. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```bash
   pip install streamlit geemap folium earthengine-api
   ```

4. Set up Google Earth Engine:
   - Obtain the service account credentials JSON file from your GEE account and place it in the project directory.
   - Update the `SERVICE_ACCOUNT_FILE` variable in the code to point to the path of your JSON file.

## Usage
1. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```

2. Open your web browser and go to `http://localhost:8501`.

3. Follow the instructions in the sidebar to:
   - Select a classifier.
   - Choose a year for LULC classification.
   - Detect forest changes between two years.
   - Export classified images or forest change data.

## Instructions
1. Select a classifier (Random Forest, SVM, or CART).
2. Choose a year for LULC classification.
3. Detect forest changes between two years.
4. Export the classified image or forest change data as GeoTIFF to Google Drive.

## Contributing
If you would like to contribute to this project, please fork the repository and create a pull request. Contributions are welcome!

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- [Google Earth Engine](https://earthengine.google.com/)
- [Streamlit](https://streamlit.io/)
- [Folium](https://python-visualization.github.io/folium/)
- [Geemap](https://geemap.org/)
```

### Instructions to Use
- Replace `<repository-url>` with the URL of your GitHub repository.
- Replace `<repository-directory>` with the name of your project directory.
- Ensure you have a `LICENSE` file if you reference it in the README.
- Feel free to add any additional sections as necessary based on your project specifics or any additional instructions you want to include.