from langchain_core.prompts import PromptTemplate
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from dotenv import load_dotenv
import streamlit as st
from models.itinerary import Itinerary
from utils.parsing import display_itinerary
from database.db import (
    init_db, create_user, authenticate_user, save_itinerary, get_itineraries,
    get_public_itineraries, save_chat_message, get_chat_history, get_user,
    set_user_admin, list_users
)
import os
import uuid

# -------------------- Utility --------------------
def safe_rerun():
    try:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
            return
    except Exception:
        pass
    try:
        st.experimental_set_query_params(_refresh=str(uuid.uuid4()))
    except Exception:
        st.warning("Please refresh the page manually.")
    try:
        st.stop()
    except Exception:
        return


# -------------------- Page Config --------------------
st.set_page_config(
    page_title="AI Travel Itinerary Planner",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv()
init_db()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# -------------------- Model Loading --------------------
@st.cache_resource
def _load_model():
    llm = HuggingFaceEndpoint(
        repo_id="mistralai/Mistral-7B-Instruct-v0.3", task="text-generation"
    )
    return ChatHuggingFace(llm=llm)

# Cached global model (fixes NameError)
model = _load_model()

def _get_template():
    return PromptTemplate(
        input_variables=[
            "destination", "duration_days", "budget", "preferences",
            "user_questions", "user_name", "num_people"
        ],
        template="""
You are a friendly, professional travel planner AI.
Generate a detailed, day-wise itinerary for {destination}.

Duration: {duration_days} days
Budget: {budget}
Preferences: {preferences}
User: {user_name}, traveling with {num_people} people.

If user provided questions: {user_questions}

Output clearly structured text with headings:
Day 1, Day 2, etc., including activities, restaurants, timing, and short notes.
Avoid photos or image placeholders.
"""
    )

# -------------------- Auth Section --------------------
if "user_id" not in st.session_state:
    st.title("🔐 Login to AI Travel Itinerary Planner")
    st.image("https://picsum.photos/800/200", use_container_width=True)
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                user_id = authenticate_user(username, password)
                if not user_id:
                    user_id = create_user(username, password)
                    set_user_admin(user_id, True)
                st.session_state.update({
                    "user_id": user_id,
                    "username": username,
                    "is_admin": True,
                })
                st.success("Logged in as admin")
                st.rerun()
            else:
                user_id = authenticate_user(username, password)
                if user_id:
                    st.session_state.update({
                        "user_id": user_id,
                        "username": username,
                        "is_admin": bool(get_user(user_id).get("is_admin", False)),
                    })
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    with tab2:
        new_username = st.text_input("New Username", key="reg_username")
        new_password = st.text_input("New Password", type="password", key="reg_password")
        if st.button("Register"):
            if new_username and new_password:
                user_id = create_user(new_username, new_password)
                if user_id:
                    st.success("Registered successfully! Please login.")
                else:
                    st.error("Username already exists.")
            else:
                st.error("Please fill all fields.")

# -------------------- Main App --------------------
else:
    # ---- Background image and theme ----
    background_image_url = "https://unsplash.com/photos/dark-cloudy-sky-awcue0JHOjc?auto=format&fit=crop&w=1920&q=80"

    st.markdown(f"""
    <style>
    .stApp {{
        background-image: url("{background_image_url}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    * {{
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
    }}
    .stButton button {{
        background: linear-gradient(135deg, #bb86fc 0%, #6200ea 100%) !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        border: none !important;
    }}
    .stTextInput, .stTextArea, .stNumberInput {{
        background-color: rgba(0,0,0,0.5) !important;
        color: white !important;
        border-radius: 10px !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    theme = "Dark"

    col_welcome, col_logout = st.columns([9, 1])
    with col_welcome:
        st.markdown(f"**Welcome, {st.session_state['username']}**")
    with col_logout:
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

    user_id = st.session_state["user_id"]

    # ---- Tabs setup ----
    if st.session_state.get("is_admin"):
        tab_gen, tab_dash, tab_storage = st.tabs(["Generate Itinerary", "Dashboard", "Storage"])
    else:
        tab_gen, tab_dash = st.tabs(["Generate Itinerary", "Dashboard"])
        tab_storage = None

    # -------------------- Generate Itinerary --------------------
    with tab_gen:
        st.title("🌍 Generate Your Travel Itinerary")
        st.image("https://picsum.photos/800/150", use_container_width=True)
        with st.form("itinerary_form"):
            col1, col2 = st.columns(2)
            with col1:
                destination = st.text_input("Destination")
                duration_days = st.number_input("Duration (days)", 1, 30, 5)
                budget = st.text_input("Budget", placeholder="e.g., INR50000")
                num_people = st.number_input("People", 1, 20, 1)
            with col2:
                preferences = st.text_area("Preferences", placeholder="e.g., adventure, food")
                user_questions = st.text_area("Extra Questions", placeholder="Any specific requests?")
            user_name = st.text_input("Your Name")
            submitted = st.form_submit_button("Generate Itinerary")

            if submitted:
                if not destination or not user_name:
                    st.error("Please fill Destination and Name.")
                else:
                    with st.spinner("Generating your itinerary..."):
                        template = _get_template()
                        chain = template | model
                        result = chain.invoke({
                            "destination": destination,
                            "duration_days": duration_days,
                            "budget": budget,
                            "preferences": preferences,
                            "user_questions": user_questions,
                            "user_name": user_name,
                            "num_people": num_people,
                        })
                        st.session_state["generated_itinerary"] = result.content
                        st.session_state["itinerary_details"] = {
                            "destination": destination,
                            "duration": duration_days,
                            "budget": budget,
                            "preferences": preferences,
                            "user_name": user_name,
                            "num_people": num_people,
                        }
                        st.success("Itinerary generated!")
                        st.balloons()

        if "generated_itinerary" in st.session_state:
            st.subheader("📅 Your Generated Itinerary")
            display_itinerary(st.session_state["generated_itinerary"], theme)
            itinerary_name = st.text_input("Name your itinerary", placeholder="e.g., Bali Adventure")
            is_public = st.checkbox("Make this itinerary public", value=False)
            if st.button("Save Itinerary"):
                if itinerary_name:
                    itinerary = Itinerary(
                        name=itinerary_name,
                        content=st.session_state["generated_itinerary"],
                        destination=st.session_state["itinerary_details"]["destination"],
                        duration=st.session_state["itinerary_details"]["duration"],
                        budget=st.session_state["itinerary_details"]["budget"],
                        preferences=st.session_state["itinerary_details"]["preferences"],
                        user_name=st.session_state["itinerary_details"]["user_name"],
                        is_public=is_public,
                        num_people=st.session_state["itinerary_details"].get("num_people", 1),
                    )
                    save_itinerary(itinerary, user_id)
                    del st.session_state["generated_itinerary"]
                    del st.session_state["itinerary_details"]
                    st.success("Itinerary saved!")
                    st.balloons()
                else:
                    st.error("Please name your itinerary.")

    # -------------------- Dashboard --------------------
    with tab_dash:
        st.title("📊 Your Dashboard")
        st.image("https://picsum.photos/800/150", use_container_width=True)
        tab1, tab2 = st.tabs(["My Itineraries", "Public Itineraries"])

        # ---- My Itineraries ----
        with tab1:
            itineraries = get_itineraries(user_id)
            if not itineraries:
                st.info("No itineraries yet.")
            else:
                selected_name = st.selectbox("Select an Itinerary", [it.name for it in itineraries])
                selected_it = next(it for it in itineraries if it.name == selected_name)
                st.subheader(f"📍 {selected_it.name}")
                st.markdown("---")
                st.write(f"Destination: {selected_it.destination}")
                st.write(f"Duration: {selected_it.duration} days")
                st.write(f"Budget: {selected_it.budget}")
                st.write(f"People: {selected_it.num_people or 1}")
                st.write(f"Preferences: {selected_it.preferences or '-'}")

                if st.button("View Itinerary"):
                    display_itinerary(selected_it.content, theme)

                # ✈️ Flight search
                st.markdown("**Find Best Flights**")
                dep_city = st.text_input("Departure city", key=f"dep_my_{selected_it.id}")
                if st.button("Find Flights", key=f"find_flights_my_{selected_it.id}"):
                    origin = dep_city.strip() or "Your nearest major airport"
                    flight_template = PromptTemplate(
                        input_variables=["origin", "destination"],
                        template="""You are a travel assistant. Provide top 3 flight options 
                        from {origin} to {destination}. For each: airline, price (INR), duration, stops, and short note."""
                    )
                    flight_chain = flight_template | model
                    with st.spinner("Fetching flight options..."):
                        flight_resp = flight_chain.invoke({
                            "origin": origin,
                            "destination": selected_it.destination
                        }).content.strip()
                    st.info(flight_resp)

                # 💬 Chat Conversation (kept)
                st.markdown("### 💬 Chat with AI about this itinerary")
                chat_history = get_chat_history(selected_it.id)
                for chat in chat_history:
                    with st.chat_message(chat["role"]):
                        st.markdown(chat["content"])

                if prompt := st.chat_input("Ask something about your itinerary..."):
                    save_chat_message(selected_it.id, "user", prompt)
                    with st.chat_message("user"):
                        st.markdown(prompt)

                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            chat_prompt = PromptTemplate(
                                input_variables=["itinerary", "question"],
                                template="You are a travel assistant. Given this itinerary: {itinerary}. Answer: {question}"
                            )
                            chat_chain = chat_prompt | model
                            answer = chat_chain.invoke({
                                "itinerary": selected_it.content,
                                "question": prompt
                            }).content.strip()
                            st.markdown(answer)
                            save_chat_message(selected_it.id, "assistant", answer)

        # ---- Public Itineraries ----
        with tab2:
            public_itins = get_public_itineraries()
            if not public_itins:
                st.info("No public itineraries yet.")
            else:
                selected_pub_name = st.selectbox("Select Public Itinerary", [it.name for it in public_itins])
                selected_pub = next(it for it in public_itins if it.name == selected_pub_name)
                st.subheader(f"🌍 {selected_pub.name}")
                st.markdown("---")
                display_itinerary(selected_pub.content, theme)
                st.write(f"Destination: {selected_pub.destination}")
                st.write(f"Duration: {selected_pub.duration} days")
                st.write(f"Budget: {selected_pub.budget}")
                st.write(f"People: {selected_pub.num_people or 1}")
                st.write(f"Preferences: {selected_pub.preferences}")
                st.write(f"Shared by: {selected_pub.user_name}")

                # ✈️ Flight search
                st.markdown("**Find Best Flights**")
                dep_city_pub = st.text_input("Departure city", key=f"dep_pub_{selected_pub.id}")
                if st.button("Find Flights", key=f"find_flights_pub_{selected_pub.id}"):
                    origin = dep_city_pub.strip() or "Your nearest major airport"
                    flight_template = PromptTemplate(
                        input_variables=["origin", "destination"],
                        template="""You are a travel assistant. Provide top 3 flight options 
                        from {origin} to {destination}. For each: airline, price (INR), duration, stops, and short note."""
                    )
                    flight_chain = flight_template | model
                    with st.spinner("Fetching flight options..."):
                        flight_resp = flight_chain.invoke({
                            "origin": origin,
                            "destination": selected_pub.destination
                        }).content.strip()
                    st.info(flight_resp)

                # Copy itinerary
                st.markdown("**Save to My Itineraries**")
                new_name = st.text_input("New name for your copy", key="copy_name")
                if st.button("Save Copy"):
                    if new_name:
                        new_itin = Itinerary(
                            name=new_name,
                            content=selected_pub.content,
                            destination=selected_pub.destination,
                            duration=selected_pub.duration,
                            budget=selected_pub.budget,
                            preferences=selected_pub.preferences,
                            user_name=st.session_state["username"],
                            is_public=False,
                            num_people=selected_pub.num_people,
                        )
                        save_itinerary(new_itin, user_id)
                        st.success("Saved to your private itineraries!")
                    else:
                        st.error("Enter a name before saving.")

    # -------------------- Admin Storage --------------------
    if tab_storage:
        with tab_storage:
            st.subheader("🗄️ Admin Storage Panel")
            st.info("Admin-only storage management tools (optional).")

st.caption("🚀 Powered by AI | Built with Streamlit + LangChain")
