from neo4j import GraphDatabase
import pandas as pd
import os
import logging

# Set up logger (assuming logger was used previously)
logger = logging.getLogger(__name__)

def fetch_top_rated_nodes(uri, user, password, rating_properties, top_n=20):
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            # Construct the Cypher query to fetch nodes with ratings
            ratings_conditions = " AND ".join([
                f"d.{prop} IS NOT NULL AND toFloat(d.{prop}) IS NOT NULL" 
                for prop in rating_properties
            ])
            average_rating_query = " + ".join([f"toFloat(d.{prop})" for prop in rating_properties])
            num_ratings = len(rating_properties)
            
            result = session.run(f"""
                MATCH (d:Drug)
                WHERE {ratings_conditions}
                WITH d, ({average_rating_query}) / {num_ratings} AS average_rating
                RETURN d.name AS name, d.reason_rating_0 AS reason_rating_0, d.reason_rating_1 AS reason_rating_1, 
                       d.rating_0 AS rating_0, d.rating_1 AS rating_1, d.rating_2 AS rating_2, d.rating_3 AS rating_3,
                       d.rating_4 AS rating_4, d.rating_5 AS rating_5, d.rating_6 AS rating_6, d.rating_7 AS rating_7,
                       d.rating_8 AS rating_8, d.rating_9 AS rating_9,
                       d.pharmacodynamics AS pharmacodynamics,
                       d.mechanismOfAction AS mechanismOfAction, d.indication AS indication, 
                       d.promising AS promising, d.therapeuticallySignificant AS therapeuticallySignificant,
                       d.clinicalDescription AS clinicalDescription,
                       average_rating
                ORDER BY average_rating DESC
                LIMIT {top_n}
            """)

            nodes = []

            for record in result:
                nodes.append({
                    'name': record['name'],
                    'average_rating': record['average_rating'],
                    'reason_rating_0': record['reason_rating_0'],
                    'reason_rating_1': record['reason_rating_1'],
                    'rating_0': record['rating_0'],
                    'rating_1': record['rating_1'],
                    'rating_2': record['rating_2'],
                    'rating_3': record['rating_3'],
                    'rating_4': record['rating_4'],
                    'rating_5': record['rating_5'],
                    'rating_6': record['rating_6'],
                    'rating_7': record['rating_7'],
                    'rating_8': record['rating_8'],
                    'rating_9': record['rating_9'],
                    'pharmacodynamics': record['pharmacodynamics'],
                    'mechanismOfAction': record['mechanismOfAction'],
                    'indication': record['indication'],
                    'promising': record['promising'],
                    'therapeuticallySignificant': record['therapeuticallySignificant'],
                    'clinicalDescription': record['clinicalDescription']
                })

            return nodes

    except Exception as e:
        logger.error(f"An error occurred while fetching top-rated nodes: {str(e)}")
        return []
    finally:
        if 'driver' in locals():
            driver.close()


def export_to_csv(nodes, output_file):
    # Desired column order
    desired_order = [
        'name', 'average_rating', 'reason_rating_0', 'reason_rating_1', 'rating_0', 'rating_1', 'rating_2',
        'rating_3', 'rating_4', 'rating_5', 'rating_6', 'rating_7', 'rating_8', 'rating_9',
        'pharmacodynamics', 'mechanismOfAction', 'indication', 'promising', 'therapeuticallySignificant', 
        'clinicalDescription'
    ]
    
    df = pd.DataFrame(nodes)
    df = df[desired_order]  # Reorder columns
    df.to_csv(output_file, index=False)

# Connection details
uri = os.getenv("uri")
user = os.getenv("username")
password = os.getenv("password")

# List of rating properties to compare
rating_properties = ['rating_0', 'rating_1', 'rating_2', 'rating_3', 'rating_4', 'rating_5', 'rating_6', 'rating_7', 'rating_8', 'rating_9']  # Add more as needed

# Fetch top 20 rated nodes and export to CSV
top_rated_nodes = fetch_top_rated_nodes(uri, user, password, rating_properties, top_n=20)
if top_rated_nodes:
    output_file = 'top_rated_nodes.csv'
    export_to_csv(top_rated_nodes, output_file)
    logger.info(f"Top-rated nodes exported to {output_file}")
else:
    logger.info("No top-rated nodes found.")
