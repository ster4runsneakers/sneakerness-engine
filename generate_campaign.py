import streamlit as st

st.set_page_config(page_title="Sneakerness Engine", layout="wide")

# 1. Αρχικοποίηση Session State για τα πεδία
if "brand_input" not in st.session_state:
    st.session_state["brand_input"] = ""
if "model_input" not in st.session_state:
    st.session_state["model_input"] = ""
if "colorway_input" not in st.session_state:
    st.session_state["colorway_input"] = ""
if "uploaded_file_key" not in st.session_state:
    st.session_state["uploaded_file_key"] = 0

# 2. Callback για το κουμπί Clear
def clear_all_inputs():
    st.session_state["brand_input"] = ""
    st.session_state["model_input"] = ""
    st.session_state["colorway_input"] = ""
    st.session_state["uploaded_file_key"] += 1

# Top Bar
col_title, col_clear = st.columns([4, 1])
with col_title:
    st.title("👟 Sneakerness Engine")

with col_clear:
    st.button("🧹 Νέο Παπούτσι / Clear", on_click=clear_all_inputs, use_container_width=True)

st.markdown("---")

# File Uploader & Preview
uploaded_file = st.file_uploader(
    "📷 Ανέβασε φωτογραφία παπουτσιού (Προαιρετικό)",
    type=["jpg", "png", "webp", "jpeg"],
    key=f"uploader_{st.session_state['uploaded_file_key']}"
)

if uploaded_file is not None:
    st.subheader("Προεπισκόπηση")
    st.image(uploaded_file, width=300)

# Detection Action Button
if st.button("🔍 Αυτόματη Ανίχνευση (Specs, Χρώμα, Περιβάλλον & Σενάριο)"):
    if uploaded_file is None:
        st.warning("Παρακαλώ ανέβασε πρώτα μια εικόνα για ανίχνευση.")
    else:
        # Εδώ όταν τρέχει το Vision API, ενημερώνεις απευθείας το session state:
        # st.session_state["brand_input"] = "Brooks"
        # st.session_state["model_input"] = "Hyperion"
        # st.session_state["colorway_input"] = "White / Volt"
        st.info("Εκτέλεση ανίχνευσης...")

# Form Inputs (ΧΩΡΙΣ την παράμετρο value - διαβάζουν μόνο από το key)
col1, col2, col3 = st.columns(3)

with col1:
    st.text_input("Brand / Μάρκα", key="brand_input")

with col2:
    st.text_input("Model Name / Μοντέλο", key="model_input")

with col3:
    st.text_input("Colorway / Χρώμα", key="colorway_input")