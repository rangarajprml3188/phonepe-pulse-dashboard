import json
from collections import defaultdict


INPUT_FILE = "india_states.geojson"
OUTPUT_FILE = "india_states_merged.geojson"


# ------------------------------------------------------------
# Load original GeoJSON
# ------------------------------------------------------------

with open(
    INPUT_FILE,
    "r",
    encoding="utf-8",
) as file:

    data = json.load(file)


# ------------------------------------------------------------
# Group geometries by state name
# ------------------------------------------------------------

state_geometries = defaultdict(list)

for feature in data["features"]:

    state_name = feature["properties"]["ST_NM"]
    geometry = feature["geometry"]

    if geometry is None:
        continue

    if geometry["type"] == "Polygon":

        # Convert Polygon coordinates into MultiPolygon format.
        state_geometries[state_name].append(
            geometry["coordinates"]
        )

    elif geometry["type"] == "MultiPolygon":

        # Add every polygon from the MultiPolygon.
        state_geometries[state_name].extend(
            geometry["coordinates"]
        )


# ------------------------------------------------------------
# Create one MultiPolygon feature per state
# ------------------------------------------------------------

merged_features = []

for state_name, polygons in sorted(
    state_geometries.items()
):

    feature = {
        "type": "Feature",
        "properties": {
            "ST_NM": state_name
        },
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": polygons
        }
    }

    merged_features.append(feature)


# ------------------------------------------------------------
# Create final FeatureCollection
# ------------------------------------------------------------

merged_data = {
    "type": "FeatureCollection",
    "features": merged_features
}


# ------------------------------------------------------------
# Save
# ------------------------------------------------------------

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8",
) as file:

    json.dump(
        merged_data,
        file,
        ensure_ascii=False,
    )


print("Original features :", len(data["features"]))
print("Merged states     :", len(merged_features))
print("Output file       :", OUTPUT_FILE)