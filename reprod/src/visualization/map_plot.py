# Please note that if you generate this plot within the pipeline, you will be fetching new data from clinical trials gov
# Therefore, the plot will be slightly different from the one in the paper
# However, given the number of studies (particuarly the number of historical studies that remains the same), it is expected that the plot will be indistinguishable from the one in the paper
# Nevertheless, please be aware of this when generating the plot.

import os
import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless backend for Docker
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from mpl_toolkits.axes_grid1 import make_axes_locatable
import cartopy.crs as ccrs
import cartopy.io.img_tiles as cimgt
from matplotlib.axes import Axes
from neo4j import GraphDatabase
from dotenv import load_dotenv
import logging
import re
from matplotlib.colors import LinearSegmentedColormap

# ---------- Config / Paths ----------
load_dotenv()

EXPORTS_ROOT = os.getenv("EXPORTS_ROOT", "/app/exports")
TRIALS_DIR = os.getenv("CTG_DIR", os.path.join(EXPORTS_ROOT, "clinical_trials_data"))
PLOTS_DIR = os.path.join(EXPORTS_ROOT, "plots")
LOG_DIR = os.path.join("/app", "logs", "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "map_plot.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def extract_coordinates(data, weight):
    # unchanged logic
    coordinates = []
    if isinstance(data, dict):
        locations = data.get('protocolSection', {}).get('contactsLocationsModule', {}).get('locations', [])
        for location in locations:
            geo_point = location.get('geoPoint', {})
            lat = geo_point.get('lat')
            lon = geo_point.get('lon')
            if lat is not None and lon is not None:
                coordinates.extend([(lon, lat)] * weight)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                coordinates.extend(extract_coordinates(item, weight))
    return coordinates

def sanitize_filename(name):
    return name.replace(' ', '_')

def unsanitize_filename(filename):
    return filename.replace('_', ' ').replace('.json', '')

def get_rating_from_neo4j(uri, user, password, drug_name):
    # unchanged semantics
    driver = GraphDatabase.driver(uri, auth=(user, password))
    query = """
        MATCH (n:Drug {name: $name})
        RETURN n.rating_0 AS rating_0, n.rating_1 AS rating_1, n.rating_2 AS rating_2,
               n.rating_3 AS rating_3, n.rating_4 AS rating_4, n.rating_5 AS rating_5,
               n.rating_6 AS rating_6, n.rating_7 AS rating_7, n.rating_8 AS rating_8,
               n.rating_9 AS rating_9
    """
    average_rating = None
    try:
        with driver.session() as session:
            record = session.run(query, name=drug_name).single()
            if record:
                ratings = [record[f'rating_{i}'] for i in range(10)]
                ratings = [r for r in ratings if r is not None]
                if ratings:
                    average_rating = sum(ratings) / len(ratings)
    finally:
        driver.close()
    return average_rating

def main():
    uri = os.getenv("uri")
    username = os.getenv("username")
    password = os.getenv("password")

    logger.info(f"Reading clinical trials JSONs from: {TRIALS_DIR}")
    logger.info(f"Saving plot(s) to: {PLOTS_DIR}")

    all_coordinates = []
    missing_nodes_count = 0
    found_nodes_count = 0

    if not os.path.isdir(TRIALS_DIR):
        logger.error(f"Trials directory does not exist: {TRIALS_DIR}")
        return

    files = [f for f in os.listdir(TRIALS_DIR) if f.endswith('.json')]
    logger.info(f"Found {len(files)} trial JSON files.")

    for filename in files:
        filepath = os.path.join(TRIALS_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                data = json.load(file)
            drug_name = unsanitize_filename(filename)
            avg = get_rating_from_neo4j(uri, username, password, drug_name)
            if avg is None:
                missing_nodes_count += 1
                logger.debug(f"No ratings for '{drug_name}' (skipping).")
                continue
            found_nodes_count += 1
            logger.debug(f"Drug '{drug_name}' average rating: {avg:.3f}")
            weighted_score = int(1 * avg * 10)  # original weighting
            coords = extract_coordinates(data, weighted_score)
            all_coordinates.extend(coords)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in {filename}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error processing {filename}: {e}")

    logger.info(f"Total drugs with ratings found in DB: {found_nodes_count}")
    logger.critical(f"Total drugs missing ratings in DB: {missing_nodes_count}")

    if not all_coordinates:
        logger.warning("No coordinates to plot. Skipping map generation.")
        return

    df = pd.DataFrame(all_coordinates, columns=['Longitude', 'Latitude'])
    df_counts = df.groupby(['Longitude', 'Latitude']).size().reset_index(name='Counts')

    # Basemap with OSM tiles
    tiler = cimgt.OSM()
    mercator = tiler.crs

    fig = plt.figure(figsize=(15, 10))
    ax = plt.axes(projection=mercator)
    plt.title("Regional distribution of the drug trial facilities and rating by the LLM", fontsize=20)

    # Limit poles (unchanged)
    ax.set_extent([-180, 180, -60, 75], crs=ccrs.PlateCarree())
    ax.add_image(tiler, 4)

    cmap = LinearSegmentedColormap.from_list("blue_to_purple", ["#EEE", "#4B0D66"])
    norm = mcolors.LogNorm()

    scatter = ax.scatter(
        df_counts['Longitude'],
        df_counts['Latitude'],
        c=df_counts['Counts'],
        cmap=cmap,
        norm=norm,
        s=5,
        alpha=0.8,
        marker='o',
        edgecolors='none',
        linewidths=0,
        transform=ccrs.PlateCarree()
    )

    divider = make_axes_locatable(ax)
    cax = divider.append_axes("bottom", size="5%", pad=0.5, axes_class=Axes)
    cb = fig.colorbar(scatter, cax=cax, orientation='horizontal')
    cb.set_label('Study Score', fontsize=15)
    cb.ax.xaxis.set_label_position('bottom')
    cb.ax.xaxis.set_ticks_position('bottom')

    out_path = os.path.join(PLOTS_DIR, "map_with_horizontal_colorbar.png")
    plt.savefig(out_path, bbox_inches='tight', dpi=1200)
    plt.close()
    logger.info(f"Saved map plot to: {out_path}")

if __name__ == "__main__":
    main()