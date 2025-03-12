import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates
import matplotlib.pyplot as plt
from PIL import Image
from google.cloud import bigquery
from google.oauth2 import service_account
import json
import uuid

# Inject custom CSS for global styling and full-width buttons
st.markdown(
    """
    <style>
    /* Global styling */
    .stApp {
        background-color: black;
        color: white;
    }
    /* Full-width blue-outlined buttons with orange background */
    .stButton>button {
        background-color: orange;
        color: black;
        border: 2px solid blue;
        padding: 10px 20px;
        border-radius: 5px;
        width: 100%;
        margin-bottom: 10px;
    }
    /* Title styling: no extra margin-bottom */
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
    .game-details-container h2 {
        color: orange;
        text-align: center;
    }
    .game-details-container input {
        background-color: black;
        color: white;
        border: 1px solid #444;
        padding: 8px;
        border-radius: 5px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Display the logo image at the top
st.image("fuel_logo.jpeg", use_container_width=True)

# Display the title below the logo without extra margin
st.markdown("<h1 class='page-title'>Log At Bat</h1>", unsafe_allow_html=True)

# =============================================================================
# BIGQUERY FUNCTIONS
# =============================================================================
def get_bigquery_client():
    # Access the service account info from Streamlit secrets
    service_account_info = st.secrets["bigquery"]
    credentials = service_account.Credentials.from_service_account_info(service_account_info)
    return bigquery.Client(credentials=credentials, project=credentials.project_id)

def log_to_bigquery(hit_info):
    client = get_bigquery_client()
    table_id = "hit-tracker-453205.hit_tracker_data.fact_hit_log"
    errors = client.insert_rows_json(table_id, [hit_info])
    if errors:
        st.error(f"Error logging data: {errors}")
    else:
        st.success("Hit logged!")

# --- Initialize session state ---
for key in ["stage", "hit_data", "img_click_data", "date", "opponent",
            "hitter_name", "outcome", "batted_result", "contact_type"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key=="hit_data" else (None if key != "stage" else "game_details")

# --- Button callbacks ---
def submit_game_details():
    if st.session_state.opponent and st.session_state.hitter_name:
        st.session_state.stage = "select_outcome"
    else:
        st.error("Please fill in all details before proceeding.")

def select_outcome(outcome):
    st.session_state.outcome = outcome
    if outcome == "Batted Ball":
        st.session_state.stage = "select_batted_result"
    else:
        hit_info = {
            "id": str(uuid.uuid4()),
            "date": str(st.session_state.date),
            "opponent": st.session_state.opponent,
            "hitter_name": st.session_state.hitter_name,
            "outcome": outcome,
            "batted_result": None,
            "contact_type": None,
            "x_coordinate": None,
            "y_coordinate": None
        }
        st.session_state.hit_data.append(hit_info)
        log_to_bigquery(hit_info)
        st.session_state.stage = "reset"

def select_batted_result(result):
    st.session_state.batted_result = result
    st.session_state.stage = "select_contact_type"

def select_contact_type(contact):
    st.session_state.contact_type = contact
    st.session_state.stage = "log_hit_location"
    st.session_state.img_click_data = None

def log_another_at_bat():
    st.session_state.stage = "game_details"
    st.session_state.img_click_data = None

# --- UI Starts here ---
if st.session_state.stage == "game_details":
    with st.container():
        st.markdown("<div class='game-details-container'>", unsafe_allow_html=True)
        st.markdown("<h2>Enter Game Details</h2>", unsafe_allow_html=True)
        st.session_state.date = st.date_input("Select Date")
        st.session_state.opponent = st.text_input("Opponent")
        st.session_state.hitter_name = st.text_input("Hitter Name")
        st.button("Next", on_click=submit_game_details)
        st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.stage == "select_outcome":
    st.header("Select At-bat Outcome")
    # Remove the "SO" button; only one option remains:
    st.button("SO Looking", on_click=select_outcome, args=("Strikeout Looking",), key="so_looking")
    st.button("Walk", on_click=select_outcome, args=("Walk",), key="walk")
    st.button("Batted Ball", on_click=select_outcome, args=("Batted Ball",), key="batted_ball")

elif st.session_state.stage == "select_batted_result":
    st.header("Select Hit Result")
    st.button("Error", on_click=select_batted_result, args=("Error",), key="error")
    st.button("Single", on_click=select_batted_result, args=("Single",), key="single")
    st.button("Double", on_click=select_batted_result, args=("Double",), key="double")
    st.button("Triple", on_click=select_batted_result, args=("Triple",), key="triple")
    st.button("Homerun", on_click=select_batted_result, args=("Homerun",), key="homerun")
    st.button("Out", on_click=select_batted_result, args=("Out",), key="out")

elif st.session_state.stage == "select_contact_type":
    st.header("Select Contact Type")
    st.button("Weak Ground Ball", on_click=select_contact_type, args=("Weak Ground Ball",), key="weak_ground_ball")
    st.button("Hard Ground Ball", on_click=select_contact_type, args=("Hard Ground Ball",), key="hard_ground_ball")
    st.button("Weak Line Drive", on_click=select_contact_type, args=("Weak Line Drive",), key="weak_line_drive")
    st.button("Hard Line Drive", on_click=select_contact_type, args=("Hard Line Drive",), key="hard_line_drive")
    st.button("Weak Fly Ball", on_click=select_contact_type, args=("Weak Fly Ball",), key="weak_fly_ball")
    st.button("Hard Fly Ball", on_click=select_contact_type, args=("Hard Fly Ball",), key="hard_fly_ball")

elif st.session_state.stage == "log_hit_location":
    st.header("Double press on the field to log location")
    img = Image.open("baseball_field_image.png")
    click_data = streamlit_image_coordinates(img)
    if click_data and click_data.get("x") is not None:
        st.session_state.img_click_data = click_data
        hit_info = {
            "id": str(uuid.uuid4()),
            "date": str(st.session_state.date),
            "opponent": st.session_state.opponent,
            "hitter_name": st.session_state.hitter_name,
            "outcome": st.session_state.outcome,
            "batted_result": st.session_state.batted_result,
            "contact_type": st.session_state.contact_type,
            "x_coordinate": click_data["x"],
            "y_coordinate": click_data["y"]
        }
        st.session_state.hit_data.append(hit_info)
        log_to_bigquery(hit_info)
        st.session_state.stage = "plot_hit_location"
        st.experimental_rerun()

elif st.session_state.stage == "plot_hit_location":
    st.header(f"Hit Location for {st.session_state.hitter_name}")
    img = Image.open("baseball_field_image.png").convert("RGB")
    fig, ax = plt.subplots()
    ax.imshow(img)
    ax.axis('off')
    ax.set_xlim(0, img.width)
    ax.set_ylim(img.height, 0)  # Match Streamlit image coordinate system
    for hit in st.session_state.hit_data:
        if hit["x_coordinate"] is not None and hit["y_coordinate"] is not None:
            ax.scatter(hit["x_coordinate"], hit["y_coordinate"], color='red', s=100)
    st.pyplot(fig)
    st.button("Log Another At-Bat", on_click=log_another_at_bat)

elif st.session_state.stage == "reset":
    st.header("At-Bat Recorded")
    st.write(f"Hitter: {st.session_state.hitter_name}")
    st.write(f"Date: {st.session_state.date}")
    st.write(f"Opponent: {st.session_state.opponent}")
    st.write(f"Outcome: {st.session_state.outcome}")
    if st.session_state.outcome == "Batted Ball":
        st.write(f"Batted Result: {st.session_state.batted_result}")
        st.write(f"Contact Type: {st.session_state.contact_type}")
    st.button("Log Another At-Bat", on_click=log_another_at_bat)
