import streamlit as st

# --- App Title ---
st.set_page_config(page_title="Travel Itinerary AI", layout="wide")

# --- Sidebar: Role Selection ---
user_role = st.sidebar.selectbox("Select Role", ["Admin", "User"])

# --- Admin Dashboard ---
if user_role == "Admin":
    st.title("Admin Dashboard")

    # Admin Tabs
    tabs = ["Itineraries", "Storage", "Settings"]
    selected_tab = st.radio("Select Tab", tabs)

    # ----------------- ITINERARIES -----------------
    if selected_tab == "Itineraries":
        st.header("Manage Itineraries")
        itineraries = ["Trip to Paris", "Trip to Tokyo", "Trip to New York"]
        selected_itinerary = st.selectbox("Select Itinerary", itineraries)

        st.write(f"Selected Itinerary: {selected_itinerary}")

        st.subheader("Chat Conversation")
        st.text_area("Conversation", "This is where the chat conversation will appear...")

    # ----------------- STORAGE -----------------
    elif selected_tab == "Storage":
        st.header("Admin Storage Management")

        with st.expander("Manage Files", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Upload / Push File")
                uploaded_file = st.file_uploader("Choose a file to upload")
                if st.button("Push File"):
                    if uploaded_file:
                        st.success(f"File '{uploaded_file.name}' pushed successfully!")
                    else:
                        st.warning("Please select a file to upload.")

            with col2:
                st.subheader("Download / Pull File")
                storage_files = ["file1.txt", "file2.pdf", "file3.jpg"]  # Example files
                selected_file = st.selectbox("Select a file to pull", storage_files)
                if st.button("Pull File"):
                    st.success(f"File '{selected_file}' pulled successfully!")

            st.markdown("---")
            st.info("Storage logs and updates will appear here.")

    # ----------------- SETTINGS -----------------
    elif selected_tab == "Settings":
        st.header("Admin Settings")
        st.write("Configure your app settings here...")

# --- User Dashboard ---
else:
    st.title("User Dashboard")

    tabs = ["Itineraries", "Profile"]
    selected_tab = st.radio("Select Tab", tabs)

    # ----------------- ITINERARIES -----------------
    if selected_tab == "Itineraries":
        st.header("Your Itineraries")
        itineraries = ["Trip to Paris", "Trip to Tokyo", "Trip to New York"]
        selected_itinerary = st.selectbox("Select Itinerary", itineraries)

        st.write(f"Selected Itinerary: {selected_itinerary}")

        st.subheader("Chat Conversation")
        st.text_area("Conversation", "This is where user can view chat conversation...")

    # ----------------- PROFILE -----------------
    elif selected_tab == "Profile":
        st.header("User Profile")
        st.write("Profile details go here...")

