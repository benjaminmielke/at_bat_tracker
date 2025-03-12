import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image
from google.cloud import bigquery
from google.oauth2 import service_account
import uuid

# Helper to rerun the app if possible.
def rerun_app():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

# =============================================================================
# BigQuery helper functions for options, metrics, and hits
# =============================================================================
def get_bigquery_client():
    service_account_info = st.secrets["bigquery"]
    credentials = service_account.Credentials.from_service_account_info(service_account_info)
    return bigquery.Client(credentials=credentials, project=credentials.project_id)

def load_opponent_options():
    client = get_bigquery_client()
    query = "SELECT opponent FROM `hit-tracker-453205.hit_tracker_data.dim_opponents`"
    results = client.query(query).result()
    return [row.opponent for row in results]

def load_hitter_options():
    client = get_bigquery_client()
    query = "SELECT hitter FROM `hit-tracker-453205.hit_tracker_data.dim_hitters`"
    results = client.query(query).result()
    return [row.hitter for row in results]

def save_opponent_to_bigquery(new_opponent):
    client = get_bigquery_client()
    table_id = "hit-tracker-453205.hit_tracker_data.dim_opponents"
    row = {"opponent": new_opponent}
    errors = client.insert_rows_json(table_id, [row])
    if errors:
        st.error("Error saving opponent: " + str(errors))

def save_hitter_to_bigquery(new_hitter):
    client = get_bigquery_client()
    table_id = "hit-tracker-453205.hit_tracker_data.dim_hitters"
    row = {"hitter": new_hitter}
    errors = client.insert_rows_json(table_id, [row])
    if errors:
        st.error("Error saving hitter: " + str(errors))

def log_to_bigquery(hit_info):
    client = get_bigquery_client()
    table_id = "hit-tracker-453205.hit_tracker_data.fact_hit_log"
    errors = client.insert_rows_json(table_id, [hit_info])
    if errors:
        st.error(f"Error logging data: {errors}")
    else:
        st.success("Hit logged!")

def load_hits_for_player(hitter_name):
    client = get_bigquery_client()
    query = f"""
        SELECT * FROM `hit-tracker-453205.hit_tracker_data.fact_hit_log`
        WHERE hitter_name = '{hitter_name}'
    """
    results = client.query(query).result()
    return [dict(row) for row in results]

def load_metrics_for_player(hitter_name):
    """Query the view vw_hitting_metrics to retrieve Hard Hit % and Weak Hit %."""
    client = get_bigquery_client()
    query = f"""
      SELECT `Hard Hit %` as hard_hit, `Weak Hit %` as weak_hit
      FROM `hit-tracker-453205.hit_tracker_data.vw_hitting_metrics`
      WHERE hitter_name = '{hitter_name}'
    """
    results = client.query(query).result()
    for row in results:
        return row.hard_hit, row.weak_hit
    return None, None

# =============================================================================
# Load Options on Startup
# =============================================================================
if "opponent_options" not in st.session_state:
    try:
        st.session_state["opponent_options"] = load_opponent_options() or ["Team A", "Team B"]
    except Exception as e:
        st.session_state["opponent_options"] = ["Team A", "Team B"]

if "hitter_options" not in st.session_state:
    try:
        st.session_state["hitter_options"] = load_hitter_options() or ["Hitter 1", "Hitter 2"]
    except Exception as e:
        st.session_state["hitter_options"] = ["Hitter 1", "Hitter 2"]

if "adding_opponent" not in st.session_state:
    st.session_state["adding_opponent"] = False
if "adding_hitter" not in st.session_state:
    st.session_state["adding_hitter"] = False

# =============================================================================
# Global CSS
# =============================================================================
st.markdown(
    """
    <style>
    /* Global styling */
    .stApp {
        background-color: black;
        color: white;
    }
    /* Main buttons: full-width blue-outlined with orange background */
    .stButton > button {
        background-color: orange;
        color: black;
        border: 2px solid blue;
        padding: 10px 20px;
        border-radius: 5px;
        width: 100%;
        margin-bottom: 10px;
    }
    /* Title styling */
    .page-title {
        text-align: center;
        color: orange;
        font-size: 2.5em;
        margin-bottom: 0;
    }
    /* Game Details Form Container */
    .game-details-container {
        background-color: #121212;
        padding: 20px;
        border-radius: 10px;
        margin: 20px auto;
        max-width: 500px;
    }
    .game-details-container input,
    .game-details-container select {
        background-color: black;
        color: white;
        border: 1px solid #444;
        padding: 8px;
        border-radius: 5px;
        width: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Display the logo image and title.
st.image("fuel_logo.jpeg", use_container_width=True)
st.markdown("<h1 class='page-title'>Log At Bat</h1>", unsafe_allow_html=True)

# =============================================================================
# Initialize other session state variables for flow.
# =============================================================================
for key in ["stage", "hit_data", "img_click_data", "date", "opponent",
            "hitter_name", "outcome", "batted_result", "contact_type"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key=="hit_data" else (None if key!="stage" else "game_details")

# =============================================================================
# Button Callbacks
# =============================================================================
def submit_game_details():
    st.session_state["opponent"] = st.session_state.get("selected_opponent", "")
    st.session_state["hitter_name"] = st.session_state.get("selected_hitter", "")
    if st.session_state["opponent"] and st.session_state["hitter_name"]:
        st.session_state["stage"] = "select_outcome"
    else:
        st.error("Please fill in all details before proceeding.")

def select_outcome(outcome):
    st.session_state["outcome"] = outcome
    if outcome == "Batted Ball":
        st.session_state["stage"] = "select_batted_result"
    else:
        hit_info = {
            "id": str(uuid.uuid4()),
            "date": str(st.session_state["date"]),
            "opponent": st.session_state["opponent"],
            "hitter_name": st.session_state["hitter_name"],
            "outcome": outcome,
            "batted_result": None,
            "contact_type": None,
            "x_coordinate": None,
            "y_coordinate": None
        }
        st.session_state["hit_data"].append(hit_info)
        log_to_bigquery(hit_info)
        st.session_state["stage"] = "reset"

def select_batted_result(result):
    st.session_state["batted_result"] = result
    st.session_state["stage"] = "select_contact_type"

def select_contact_type(contact):
    st.session_state["contact_type"] = contact
    st.session_state["stage"] = "log_hit_location"
    st.session_state["img_click_data"] = None

def log_another_at_bat():
    st.session_state["stage"] = "game_details"
    st.session_state["img_click_data"] = None

# =============================================================================
# UI Flow
# =============================================================================
if st.session_state["stage"] == "game_details":
    with st.container():
        st.markdown("<div class='game-details-container'>", unsafe_allow_html=True)
        st.session_state["date"] = st.date_input("Select Date")
        # Opponent select box with plus button in a row
        col_opponent, col_opponent_plus = st.columns([4, 1])
        col_opponent.selectbox("Opponent", st.session_state["opponent_options"], key="selected_opponent")
        if col_opponent_plus.button("➕", key="add_opponent"):
            st.session_state["adding_opponent"] = True
        if st.session_state["adding_opponent"]:
            new_opponent = st.text_input("New Opponent", key="new_opponent")
            if st.button("Save Opponent", key="save_opponent"):
                if new_opponent and new_opponent not in st.session_state["opponent_options"]:
                    save_opponent_to_bigquery(new_opponent)
                    st.session_state["opponent_options"].append(new_opponent)
                st.session_state["adding_opponent"] = False
                rerun_app()
        # Hitter select box with plus button in a row
        col_hitter, col_hitter_plus = st.columns([4, 1])
        col_hitter.selectbox("Hitter", st.session_state["hitter_options"], key="selected_hitter")
        if col_hitter_plus.button("➕", key="add_hitter"):
            st.session_state["adding_hitter"] = True
        if st.session_state["adding_hitter"]:
            new_hitter = st.text_input("New Hitter", key="new_hitter")
            if st.button("Save Hitter", key="save_hitter"):
                if new_hitter and new_hitter not in st.session_state["hitter_options"]:
                    save_hitter_to_bigquery(new_hitter)
                    st.session_state["hitter_options"].append(new_hitter)
                st.session_state["adding_hitter"] = False
                rerun_app()
        st.button("Next", on_click=submit_game_details)
        st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state["stage"] == "select_outcome":
    st.header("Select At-bat Outcome")
    st.button("SO Looking", on_click=select_outcome, args=("Strikeout Looking",), key="so_looking")
    st.button("SO Swinging", on_click=select_outcome, args=("Strikeout Swinging",), key="so_swinging")
    st.button("Walk", on_click=select_outcome, args=("Walk",), key="walk")
    st.button("Batted Ball", on_click=select_outcome, args=("Batted Ball",), key="batted_ball")

elif st.session_state["stage"] == "select_batted_result":
    st.header("Select Hit Result")
    st.button("Error", on_click=select_batted_result, args=("Error",), key="error")
    st.button("Single", on_click=select_batted_result, args=("Single",), key="single")
    st.button("Double", on_click=select_batted_result, args=("Double",), key="double")
    st.button("Triple", on_click=select_batted_result, args=("Triple",), key="triple")
    st.button("Homerun", on_click=select_batted_result, args=("Homerun",), key="homerun")
    st.button("Out", on_click=select_batted_result, args=("Out",), key="out")

elif st.session_state["stage"] == "select_contact_type":
    st.header("Select Contact Type")
    st.button("Weak Ground Ball", on_click=select_contact_type, args=("Weak Ground Ball",), key="weak_ground_ball")
    st.button("Hard Ground Ball", on_click=select_contact_type, args=("Hard Ground Ball",), key="hard_ground_ball")
    st.button("Weak Line Drive", on_click=select_contact_type, args=("Weak Line Drive",), key="weak_line_drive")
    st.button("Hard Line Drive", on_click=select_contact_type, args=("Hard Line Drive",), key="hard_line_drive")
    st.button("Weak Fly Ball", on_click=select_contact_type, args=("Weak Fly Ball",), key="weak_fly_ball")
    st.button("Hard Fly Ball", on_click=select_contact_type, args=("Hard Fly Ball",), key="hard_fly_ball")

elif st.session_state["stage"] == "log_hit_location":
    st.header("Double press on the field to log location")
    img = Image.open("baseball_field_image.png")
    click_data = streamlit_image_coordinates(img)
    if click_data and click_data.get("x") is not None:
        st.session_state["img_click_data"] = click_data
        hit_info = {
            "id": str(uuid.uuid4()),
            "date": str(st.session_state["date"]),
            "opponent": st.session_state["opponent"],
            "hitter_name": st.session_state["hitter_name"],
            "outcome": st.session_state["outcome"],
            "batted_result": st.session_state["batted_result"],
            "contact_type": st.session_state["contact_type"],
            "x_coordinate": click_data["x"],
            "y_coordinate": click_data["y"]
        }
        st.session_state["hit_data"].append(hit_info)
        log_to_bigquery(hit_info)
        st.session_state["stage"] = "plot_hit_location"
        st.experimental_rerun()

elif st.session_state["stage"] == "plot_hit_location":
    st.header(f"Hit Location for {st.session_state['hitter_name']}")
    # Load all hits for the current hitter from BigQuery.
    hits = load_hits_for_player(st.session_state["hitter_name"])
    # Also load the metrics from the view.
    hard_hit, weak_hit = load_metrics_for_player(st.session_state["hitter_name"])
    img = Image.open("baseball_field_image.png").convert("RGB")
    fig, ax = plt.subplots()
    ax.imshow(img)
    ax.axis('off')
    ax.set_xlim(0, img.width)
    ax.set_ylim(img.height, 0)
    # Add the title on the image: "<Hitter Name> Spray Chart"
    ax.set_title(f"{st.session_state['hitter_name']} Spray Chart", fontsize=20, color='black', pad=20)
    # Add metrics text below the title.
    if hard_hit is not None and weak_hit is not None:
        # Format the two lines: first the labels, then the values.
        label_line = f"{'Hard Hit':^12}{'Weak Hit':^12}"
        value_line = f"{hard_hit%:^12}%{weak_hit:^12}%"
        # Place these lines closer to the title (adjust y coordinates as needed).
        ax.text(0.5, 0.99, label_line, transform=ax.transAxes, ha='center', fontsize=8, color='black')
        ax.text(0.5, 0.95, value_line, transform=ax.transAxes, ha='center', fontsize=8, color='black')
    # Define color mapping for contact type.
    contact_color = {
        "Weak Ground Ball": "#CD853F",  # light brown
        "Hard Ground Ball": "#8B4513",  # dark brown
        "Weak Line Drive": "#90EE90",   # light green
        "Hard Line Drive": "#006400",   # dark green
        "Weak Fly Ball": "#ADD8E6",     # light blue
        "Hard Fly Ball": "#00008B"      # dark blue
    }
    # Plot each hit dot with specified styling.
    for hit in hits:
        if hit["x_coordinate"] is not None and hit["y_coordinate"] is not None:
            color = contact_color.get(hit.get("contact_type", ""), "red")
            ax.scatter(hit["x_coordinate"], hit["y_coordinate"], color=color, s=50,
                       edgecolors="black", linewidths=1)
    # Create a legend using Line2D objects with dot markers.
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label=label,
               markerfacecolor=color, markersize=8)
        for label, color in contact_color.items()
    ]
    ax.legend(handles=legend_elements, loc="lower left", prop={'size': 8}, frameon=False)
    st.pyplot(fig)
    st.button("Log Another At-Bat", on_click=log_another_at_bat)

elif st.session_state["stage"] == "reset":
    st.header("At-Bat Recorded")
    st.write(f"Hitter: {st.session_state['hitter_name']}")
    st.write(f"Date: {st.session_state['date']}")
    st.write(f"Opponent: {st.session_state['opponent']}")
    st.write(f"Outcome: {st.session_state['outcome']}")
    if st.session_state["outcome"] == "Batted Ball":
        st.write(f"Batted Result: {st.session_state['batted_result']}")
        st.write(f"Contact Type: {st.session_state['contact_type']}")
    st.button("Log Another At-Bat", on_click=log_another_at_bat)
