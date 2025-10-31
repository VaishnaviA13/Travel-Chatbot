from langchain_core.prompts import load_prompt, PromptTemplate
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from dotenv import load_dotenv
import streamlit as st
from models.itinerary import Itinerary
from utils.parsing import display_itinerary
from database.db import init_db, create_user, authenticate_user, save_itinerary, get_itineraries, get_public_itineraries, save_chat_message, get_chat_history
import hashlib
import requests
import requests
import streamlit.components.v1 as components
import uuid
import html


def safe_rerun():
    """Attempt to rerun the Streamlit script. If the runtime doesn't expose experimental_rerun,
    fall back to changing query params (which triggers a rerun) and stopping the script.
    This avoids AttributeError on older/newer Streamlit builds."""
    try:
        # Preferred method when available
        if hasattr(st, 'experimental_rerun'):
            st.experimental_rerun()
            return
    except Exception:
        pass
    try:
        # Changing query params causes a rerun in Streamlit
        st.experimental_set_query_params(_refresh=str(uuid.uuid4()))
    except Exception:
        # Last resort: ask the user to manually refresh
        st.warning("Please refresh the page to see the updated data.")
    # Stop the current run (Streamlit will re-run due to query param change)
    try:
        st.stop()
    except Exception:
        return

st.set_page_config(page_title="AI Travel Itinerary Planner", page_icon="🌍", layout="wide", initial_sidebar_state="expanded")

load_dotenv()
init_db()

def get_city_image(destination):
    try:
        # Try Wikipedia first
        response = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{destination.replace(' ', '_')}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            thumbnail = data.get('thumbnail', {}).get('source')
            if thumbnail:
                return thumbnail
    except:
        pass
    
    try:
        # Use Pexels free image API for city photos
        pexels_api_key = "563492ad6f91700001000001"  # Public demo key
        response = requests.get(f"https://api.pexels.com/v1/search?query={destination}&per_page=1", 
                                headers={"Authorization": pexels_api_key}, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('photos'):
                return data['photos'][0]['src']['medium']
    except:
        pass
    
    # Fallback: Use a consistent image based on destination
    return f"https://picsum.photos/400/200?random={hash(destination) % 1000}"


def get_city_images(destination, n=3):
    """Return up to n distinct image URLs for a destination.
    Strategy: Wikipedia summary thumbnail, Wikimedia page images, Pexels fallback, then picsum placeholders.
    """
    urls = []
    dest = destination.strip() if destination else ''
    if not dest:
        return [f"https://picsum.photos/400/200?random={i}" for i in range(n)]

    # 1) Wikipedia summary thumbnail
    try:
        resp = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{dest.replace(' ', '_')}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            thumb = data.get('thumbnail', {}).get('source')
            if thumb and thumb not in urls:
                urls.append(thumb)
    except Exception:
        pass

    # 2) Wikimedia API: search for page then collect images from page
    try:
        s = requests.get('https://en.wikipedia.org/w/api.php', params={
            'action': 'query', 'list': 'search', 'srsearch': dest, 'format': 'json', 'srlimit': 1
        }, timeout=5).json()
        top = s.get('query', {}).get('search', [])
        if top:
            title = top[0].get('title')
            imgs = requests.get('https://en.wikipedia.org/w/api.php', params={
                'action': 'query', 'titles': title, 'prop': 'images', 'format': 'json', 'imlimit': 'max'
            }, timeout=5).json()
            pages = imgs.get('query', {}).get('pages', {})
            image_titles = []
            for p in pages.values():
                for im in p.get('images', [])[:20]:
                    t = im.get('title', '')
                    if t.lower().endswith(('.jpg', '.jpeg', '.png', '.svg')):
                        image_titles.append(t)
            # fetch imageinfo urls
            for it in image_titles:
                if len(urls) >= n:
                    break
                try:
                    info = requests.get('https://en.wikipedia.org/w/api.php', params={
                        'action': 'query', 'titles': it, 'prop': 'imageinfo', 'iiprop': 'url', 'format': 'json'
                    }, timeout=5).json()
                    pages2 = info.get('query', {}).get('pages', {})
                    for p2 in pages2.values():
                        ii = p2.get('imageinfo', [])
                        if ii:
                            url = ii[0].get('url')
                            if url and url not in urls:
                                urls.append(url)
                                break
                except Exception:
                    continue
    except Exception:
        pass

    # 3) Unsplash Source fallback (no API key) - fetch images related to the place
    try:
        from urllib.parse import quote_plus
        queries = [dest, f"{dest} city", f"{dest} landmark", f"{dest} skyline", f"{dest} aerial"]
        i = 0
        for q in queries:
            if len(urls) >= n:
                break
            qenc = quote_plus(q)
            # Use source.unsplash.com which redirects to a relevant image without API key
            img_url = f"https://source.unsplash.com/800x600/?{qenc}&sig={abs(hash(dest+q))%10000}"
            if img_url not in urls:
                urls.append(img_url)
            i += 1
    except Exception:
        pass

    # Simple caching via streamlit session to avoid repeated lookups (keeps URLs only)
    try:
        key = f"_img_cache_{dest.lower()}_{n}"
        if 'img_cache' not in st.session_state:
            st.session_state['img_cache'] = {}
        st.session_state['img_cache'][key] = urls[:n]
    except Exception:
        pass

    # 4) Fallback to picsum placeholders for remaining slots
    i = 0
    while len(urls) < n:
        urls.append(f"https://picsum.photos/600/400?random={abs(hash(dest + str(i))) % 10000}")
        i += 1

    return urls[:n]


def render_carousel(img_urls, captions=None, uid=None, height=320):
        """Return HTML for a simple carousel. Use a uid to avoid duplicate element IDs."""
        if uid is None:
                uid = str(uuid.uuid4()).replace('-', '')
        if captions is None:
                captions = [''] * len(img_urls)
        # Escape urls and captions
        esc_urls = [html.escape(u) for u in img_urls]
        esc_caps = [html.escape(c) for c in captions]
        slides = "\n".join(f"<div class=\"carousel-slide\" data-index=\"{i}\">\n<img src=\"{esc_urls[i]}\" style=\"width:100%;height:100%;object-fit:cover;border-radius:10px;\">\n<div class=\"carousel-caption\">{esc_caps[i]}</div>\n</div>" for i in range(len(esc_urls)))

        html_content = f"""
        <div id="carousel-{uid}" class="carousel-container" style="width:100%;height:{height}px;position:relative;">
            <style>
                .carousel-slide {{ display:none; width:100%; height:100%; }}
                .carousel-slide img {{ width:100%; height:100%; object-fit:cover; border-radius:10px; }}
                .carousel-prev, .carousel-next {{ position:absolute; top:50%; transform:translateY(-50%); background:rgba(0,0,0,0.45); color:#fff; border:none; padding:8px 12px; cursor:pointer; border-radius:6px; z-index:10; }}
                .carousel-prev {{ left:12px; }}
                .carousel-next {{ right:12px; }}
                .carousel-caption {{ position:absolute; bottom:12px; left:12px; background:rgba(0,0,0,0.45); color:#fff; padding:6px 10px; border-radius:8px; z-index:9; font-size:14px; }}
            </style>
            {slides}
            <button class="carousel-prev" aria-label="prev">❮</button>
            <button class="carousel-next" aria-label="next">❯</button>
        </div>
        <script>
        (function() {{
            const container = document.getElementById('carousel-{uid}');
            const slides = container.querySelectorAll('.carousel-slide');
            const prev = container.querySelector('.carousel-prev');
            const next = container.querySelector('.carousel-next');
            let idx = 0;
            function show(i) {{
                slides.forEach((s, j) => s.style.display = (j===i)?'block':'none');
            }}
            prev.addEventListener('click', ()=>{{ idx = (idx-1+slides.length)%slides.length; show(idx); }});
            next.addEventListener('click', ()=>{{ idx = (idx+1)%slides.length; show(idx); }});
            // auto rotate
            show(idx);
            let t = setInterval(()=>{{ idx=(idx+1)%slides.length; show(idx); }}, 4000);
            container.addEventListener('mouseenter', ()=>clearInterval(t));
            container.addEventListener('mouseleave', ()=>{{ t = setInterval(()=>{{ idx=(idx+1)%slides.length; show(idx); }}, 4000); }});
        }})();
        </script>
        """
        return html_content

llm=HuggingFaceEndpoint(
    repo_id="mistralai/Mistral-7B-Instruct-v0.3",
    task="text-generation"
)

model=ChatHuggingFace(llm=llm)

template= PromptTemplate(
    input_variables=["destination", "duration_days", "budget", "preferences", "user_questions", "user_name", "num_people"],
    template='''You are a highly intelligent, friendly and detail-oriented Travel Planner AI. Your job is to create a tailor-made travel itinerary based on the user’s inputs, and to answer follow-up questions about that itinerary.

User Inputs:
- Name: {user_name}
- Destination: {destination}
- Duration: {duration_days} days
- Budget: {budget}
- Number of people: {num_people}
- Preferences / Interests: {preferences} (if any)
- Additional Questions: {user_questions} (if any)

Your tasks:
1. First, greet the user by name, e.g. "Hello {user_name}!".

2. Generate a day-by-day itinerary for the duration specified. For each day include:
   - Morning activity with estimated cost
   - Afternoon activity with estimated cost
   - Evening activity with estimated cost
   - Recommended restaurant or local cuisine suggestion with estimated cost
   - Accommodation tip (optional) with estimated cost if applicable
   - Travel/transport tip or local insight or cost-saving suggestion

3. Ensure the total estimated cost across all days fits strictly within the provided budget in INR. Distribute the budget logically (e.g., more on activities, less on transport if needed). All costs must be in INR and the total must not exceed the budget.

4. If the user asked any follow-up question(s) in {user_questions}, answer them at the end.

5. After the itinerary, provide a short "Tips" section with practical advice (e.g., local customs, best transport mode, packing, best time of day to visit major spots).

6. At the end, provide a "Total Estimated Cost" section with the grand total in INR, confirming it is within the budget.

7. Format your output clearly with headings for each Day (Day 1, Day 2…), bullet points for activities, and a clear "Tips" section at the end.

Example:

Day 1:
- Morning: Visit the historic city centre (free walking tour) - ₹0
- Afternoon: Lunch at Café de Flore - ₹2000. Then explore the Louvre - ₹1500.
- Evening: Seine river cruise at sunset - ₹1000.
- Restaurant suggestion: Le Comptoir du Relais (moderate budget) - ₹2500.
- Accommodation tip: Stay near Saint-Germain for easy transport - ₹3000 per night.

Day 2:
- Morning: Bike ride through the Bois de Boulogne - ₹500.
- Afternoon: Musée d'Orsay visit - ₹1200.
- Evening: Dinner at local bistro - ₹1800…

Tips:
- Use the métro instead of taxis to save budget.
- Many museums are free on the first Sunday of the month.
- Always carry a refillable water bottle.

Total Estimated Cost: ₹45000 (within budget)

Please give the itinerary in a single response, ready to show in a web app.
''')


if 'user_id' not in st.session_state:
    st.title("🔐 Login to AI Travel Itinerary Planner")
    st.image("https://picsum.photos/800/200", use_container_width=True)
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            user_id = authenticate_user(username, password)
            if user_id:
                st.session_state['user_id'] = user_id
                st.session_state['username'] = username
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
else:
    theme = 'Dark'
    # Global styles
    bg_color = '#121212'
    text_color = '#e0e0e0'
    sidebar_bg = '#1e1e1e'
    input_bg = '#2c2c2c'
    button_bg = 'linear-gradient(135deg, #bb86fc 0%, #6200ea 100%)'
    
    st.markdown(f"""
    <style>
    * {{
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
    }}
    body {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
        transition: all 0.3s ease !important;
    }}
    .stApp {{
        background-color: {bg_color} !important;
    }}
    /* Sidebar removed - using a top-row logout button instead */
    .stTextInput input, .stTextArea textarea, .stSelectbox select {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border: 1px solid #444 !important;
        border-radius: 12px !important;
        padding: 12px !important;
        font-size: 16px !important;
    }}
    .stButton button {{
        background: {button_bg} !important;
        color: white !important;
        border-radius: 12px !important;
        border: none !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
    }}
    .stButton button:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.2) !important;
    }}
    .stSubheader, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
        color: {text_color} !important;
        font-weight: 700 !important;
    }}
    .stSuccess, .stInfo, .stWarning, .stError {{
        border-radius: 12px !important;
        padding: 16px !important;
    }}
    </style>
    """, unsafe_allow_html=True)
    # Top-row welcome + logout (replace previous sidebar logout)
    col_welcome, col_logout = st.columns([9, 1])
    with col_welcome:
        st.markdown(f"**Welcome, {st.session_state['username']}**")
    with col_logout:
        if st.button("Logout", key="logout_main"):
            st.session_state.pop('user_id', None)
            st.session_state.pop('username', None)
            st.rerun()

    user_id = st.session_state['user_id']

    # Top-level tabs for main pages (replaces the old sidebar page selector)
    tab_gen, tab_dash = st.tabs(["Generate Itinerary", "Dashboard"]) 

    with tab_gen:
        st.title("🌍 Generate Your Travel Itinerary")
        st.image("https://picsum.photos/800/150", use_container_width=True)
        with st.form("itinerary_form"):
            col1, col2 = st.columns(2)
            with col1:
                destination = st.text_input("Destination", placeholder="e.g., Paris")
                duration_days = st.number_input("Duration (in days)", min_value=1, max_value=30, value=5)
                budget = st.text_input("Budget", placeholder="e.g., INR50000")
                num_people = st.number_input("Number of People", min_value=1, max_value=20, value=1)
            with col2:
                preferences = st.text_area("Preferences / Interests", placeholder="e.g., adventure, food, culture", height=100)
                user_questions = st.text_area("Additional Questions", placeholder="e.g., I want more adventure on day 2", height=100)
            user_name = st.text_input("Your Name", placeholder="e.g., John")
            submitted = st.form_submit_button("Generate Itinerary")
            if submitted:
                if not destination or not user_name:
                    st.error("Please fill in Destination and Your Name.")
                else:
                    with st.spinner("Generating your itinerary..."):
                        chain = template | model
                        result = chain.invoke({
                            'destination': destination,
                            'duration_days': duration_days,
                            'budget': budget,
                            'preferences': preferences,
                            'user_questions': user_questions,
                            'user_name': user_name,
                            'num_people': num_people
                        })
                        st.session_state['generated_itinerary'] = result.content
                        st.session_state['itinerary_details'] = {
                            'destination': destination,
                            'duration': duration_days,
                            'budget': budget,
                            'preferences': preferences,
                            'user_name': user_name,
                            'num_people': num_people
                        }
                        st.success("Itinerary generated!")
                        st.balloons()
        
        if 'generated_itinerary' in st.session_state:
            st.subheader("📅 Your Generated Itinerary")
            display_itinerary(st.session_state['generated_itinerary'], theme)
            itinerary_name = st.text_input("Name your itinerary", placeholder="e.g., Paris Adventure")
            is_public = st.checkbox("Make this itinerary public (visible to others)", value=False)
            if st.button("Save Itinerary", key="save_itinerary_gen"):
                if itinerary_name:
                    # Ensure num_people is preserved when saving (fixes the None display)
                    itinerary = Itinerary(
                        name=itinerary_name,
                        content=st.session_state['generated_itinerary'],
                        destination=st.session_state['itinerary_details']['destination'],
                        duration=st.session_state['itinerary_details']['duration'],
                        budget=st.session_state['itinerary_details']['budget'],
                        preferences=st.session_state['itinerary_details']['preferences'],
                        user_name=st.session_state['itinerary_details']['user_name'],
                        is_public=is_public,
                        num_people=st.session_state['itinerary_details'].get('num_people', 1)
                    )
                    save_itinerary(itinerary, user_id)
                    del st.session_state['generated_itinerary']
                    del st.session_state['itinerary_details']
                    st.success("Itinerary saved!")
                    st.balloons()
                else:
                    st.error("Please name your itinerary.")

    with tab_dash:
        st.title("📊 Your Dashboard")
        st.image("https://picsum.photos/800/150", use_container_width=True)
        tab1, tab2 = st.tabs(["My Itineraries", "Public Itineraries"])

        with tab1:
            itineraries = get_itineraries(user_id)
            if not itineraries:
                st.info("No itineraries saved yet. Generate one first!")
            else:
                itinerary_names = [it.name for it in itineraries]
                selected_name = st.selectbox("Select an Itinerary", itinerary_names, key="my_it")
                selected_it = next(it for it in itineraries if it.name == selected_name)

                col1, col2 = st.columns([2, 1])
                with col1:
                    st.subheader(f"📍 {selected_it.name}")
                    st.markdown("---")
                    # Animated header
                    card_bg = 'linear-gradient(135deg, #1e1e1e 0%, #2c2c2c 100%)'
                    st.markdown(f"""
                    <style>
                    @keyframes bounceIn {{
                        0% {{ opacity: 0; transform: scale(0.3); }}
                        50% {{ opacity: 1; transform: scale(1.05); }}
                        70% {{ transform: scale(0.9); }}
                        100% {{ opacity: 1; transform: scale(1); }}
                    }}
                    .animated-card {{
                        animation: bounceIn 1s ease-out;
                        background: {card_bg};
                        padding: 24px;
                        border-radius: 16px;
                        color: white;
                        text-align: center;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                        margin: 20px 0;
                        backdrop-filter: blur(10px);
                        border: 1px solid #555;
                        transition: transform 0.3s ease;
                    }}
                    .animated-card:hover {{
                        transform: translateY(-5px);
                    }}
                    </style>
                    <div class="animated-card">
                        <h2 style="margin: 0; font-size: 2em; font-weight: 700;">🌍 {selected_it.destination}</h2>
                        <p style="margin: 10px 0; font-size: 1.2em;">📅 {selected_it.duration} Days | 💰 {selected_it.budget}</p>
                        <p style="margin: 5px 0;">🎯 {selected_it.preferences or 'Custom Trip'}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown("---")
                    display_itinerary(selected_it.content, theme)

                    # Chat animations
                    chat_bg = '#2c2c2c'
                    chat_border = '#555'
                    st.markdown(f"""
                    <style>
                    @keyframes fadeInUp {{
                        from {{ opacity: 0; transform: translateY(20px); }}
                        to {{ opacity: 1; transform: translateY(0); }}
                    }}
                    .stChatMessage {{
                        animation: fadeInUp 0.5s ease-out;
                        background-color: {chat_bg} !important;
                        border-radius: 12px !important;
                        padding: 16px !important;
                        margin: 8px 0 !important;
                        border: 1px solid {chat_border} !important;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
                    }}
                    </style>
                    """, unsafe_allow_html=True)

                with col2:
                    st.markdown("**Details:**")
                    st.write(f"Destination: {selected_it.destination}")
                    st.write(f"Duration: {selected_it.duration} days")
                    st.write(f"Budget: {selected_it.budget}")
                    # Avoid showing 'None' by providing a sensible default display
                    people_display = selected_it.num_people if (selected_it.num_people is not None) else '1'
                    st.write(f"Number of People: {people_display}")
                    st.write(f"Preferences: {selected_it.preferences}")

                    # Image gallery: destination-specific photos (from Wikimedia/Pexels fallbacks)
                    img_urls = get_city_images(selected_it.destination, n=3)
                    st.markdown("**Photos:**")
                    carousel_html = render_carousel(img_urls, captions=[selected_it.destination, f"{selected_it.destination} - view", f"{selected_it.destination} - landmarks"], uid=f"my_{selected_it.id}", height=260)
                    components.html(carousel_html, height=280)

                    # Flight search UI (My Itineraries)
                    st.markdown("**Find best flights to this destination**")
                    dep_city = st.text_input("Your departure city (e.g., Mumbai)", value="", key=f"dep_my_{selected_it.id}")
                    if st.button("Find Best Flights", key=f"find_flights_my_{selected_it.id}"):
                        origin = dep_city.strip() or "Your nearest major airport"
                        flight_template = PromptTemplate(
                            input_variables=["origin", "destination"],
                            template="""You are a helpful travel assistant. Provide the top 3 flight options from {origin} to {destination}. For each option give: airline, approximate price, total duration, number of stops, and a short note about convenience (best times to fly or layovers). Provide prices in INR if possible and include suggested search terms to use on flight booking sites.

Output format:\n1) Airline — Price — Duration — Stops — Note\n2) ...\n3) ...
"""
                        )
                        flight_chain = flight_template | model
                        with st.spinner("Looking up best flight options (using the assistant)..."):
                            flight_resp = flight_chain.invoke({'origin': origin, 'destination': selected_it.destination}).content.strip()
                        st.markdown("**Best Flights (estimated)**")
                        st.info(flight_resp)

                st.divider()
                st.subheader("💬 Chat with Your Itinerary")
                chat_history = get_chat_history(selected_it.id)
                for msg in chat_history:
                    with st.chat_message(msg['role']):
                        st.write(msg['content'])

                if prompt := st.chat_input("Ask about your itinerary..."):
                    with st.chat_message("user"):
                        st.write(prompt)
                    save_chat_message(selected_it.id, "user", prompt)

                    # Get updated history
                    chat_history = get_chat_history(selected_it.id)
                    history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in chat_history[:-1]])  # Exclude the latest user message

                    # AI Response
                    chat_template = PromptTemplate(
                        input_variables=["itinerary", "history", "question"],
                        template="""You are a helpful and accurate travel assistant. Based on the provided itinerary, answer the user's question helpfully, drawing from the itinerary details and conversation history. Provide concise, accurate responses. Format your answers clearly using bullet points, numbered lists, or sections where appropriate for better readability.

Itinerary:

{itinerary}

Conversation History:

{history}

User: {question}

Assistant:"""
                    )
                    chat_chain = chat_template | model
                    response = chat_chain.invoke({
                        'itinerary': selected_it.content,
                        'history': history_text,
                        'question': prompt
                    }).content.strip()

                    with st.chat_message("assistant"):
                        st.write(response)
                    save_chat_message(selected_it.id, "assistant", response)
                    # (Duplicate display block removed to avoid rendering the itinerary twice)

        with tab2:
            st.subheader("🌐 Public Itineraries")
            public_itins = get_public_itineraries()
            if not public_itins:
                st.info("No public itineraries available yet. When users make itineraries public they'll appear here.")
            else:
                public_names = [it.name for it in public_itins]
                selected_pub_name = st.selectbox("Select a Public Itinerary", public_names, key="public_select")
                selected_pub = next(it for it in public_itins if it.name == selected_pub_name)

                col1p, col2p = st.columns([2, 1])
                with col1p:
                    st.subheader(f"📍 {selected_pub.name}")
                    st.markdown("---")
                    card_bg = 'linear-gradient(135deg, #1e1e1e 0%, #2c2c2c 100%)'
                    st.markdown(f"""
                    <div class="animated-card" style="background: {card_bg}; padding: 24px; border-radius: 16px; color: white; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.3); margin: 20px 0; backdrop-filter: blur(10px); border: 1px solid #555;">
                        <h2 style="margin: 0; font-size: 2em; font-weight: 700;">🌍 {selected_pub.destination}</h2>
                        <p style="margin: 10px 0; font-size: 1.2em;">📅 {selected_pub.duration} Days | 💰 {selected_pub.budget}</p>
                        <p style="margin: 5px 0;">🎯 {selected_pub.preferences or 'Custom Trip'}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown("---")
                    display_itinerary(selected_pub.content, theme)

                with col2p:
                    st.markdown("**Details:**")
                    st.write(f"Destination: {selected_pub.destination}")
                    st.write(f"Duration: {selected_pub.duration} days")
                    st.write(f"Budget: {selected_pub.budget}")
                    people_display_pub = selected_pub.num_people if (selected_pub.num_people is not None) else '1'
                    st.write(f"Number of People: {people_display_pub}")
                    st.write(f"Preferences: {selected_pub.preferences}")
                    st.write(f"Shared by: {selected_pub.user_name}")

                    # Destination-specific images
                    img_urls_pub = get_city_images(selected_pub.destination, n=3)
                    st.markdown("**Photos:**")
                    carousel_html_pub = render_carousel(img_urls_pub, captions=[selected_pub.destination, f"{selected_pub.destination} - view", f"{selected_pub.destination} - landmarks"], uid=f"pub_{selected_pub.id}", height=260)
                    components.html(carousel_html_pub, height=280)

                    # Flight search UI (Public Itineraries)
                    st.markdown("**Find best flights to this destination**")
                    dep_city_pub = st.text_input("Your departure city (e.g., Delhi)", value="", key=f"dep_pub_{selected_pub.id}")
                    if st.button("Find Best Flights", key=f"find_flights_pub_{selected_pub.id}"):
                        origin = dep_city_pub.strip() or "Your nearest major airport"
                        flight_template = PromptTemplate(
                            input_variables=["origin", "destination"],
                            template="""You are a helpful travel assistant. Provide the top 3 flight options from {origin} to {destination}. For each option give: airline, approximate price, total duration, number of stops, and a short note about convenience (best times to fly or layovers). Provide prices in INR if possible and include suggested search terms to use on flight booking sites.

Output format:\n1) Airline — Price — Duration — Stops — Note\n2) ...\n3) ...
"""
                        )
                        flight_chain = flight_template | model
                        with st.spinner("Looking up best flight options (using the assistant)..."):
                            flight_resp = flight_chain.invoke({'origin': origin, 'destination': selected_pub.destination}).content.strip()
                        st.markdown("**Best Flights (estimated)**")
                        st.info(flight_resp)

                    # Save a public itinerary copy to the current user's account
                    st.markdown("**Save a copy to your account:**")
                    new_name_public = st.text_input("New Name for Your Copy", placeholder="e.g., My Paris Trip", key="save_pub_name_public")
                    if st.button("Save to My Itineraries", key="save_to_my_from_public"):
                        if new_name_public:
                            private_itinerary = Itinerary(
                                name=new_name_public,
                                content=selected_pub.content,
                                destination=selected_pub.destination,
                                duration=selected_pub.duration,
                                budget=selected_pub.budget,
                                preferences=selected_pub.preferences,
                                user_name=st.session_state.get('username', 'Anonymous'),
                                is_public=False,
                                num_people=selected_pub.num_people
                            )
                            save_itinerary(private_itinerary, user_id)
                            st.success("Itinerary saved to your private collection! You can now chat with it in 'My Itineraries'.")
                            # Refresh the app so the 'My Itineraries' tab shows the newly saved itinerary
                            safe_rerun()
                        else:
                            st.error("Please enter a name for your copy.")

st.caption("🚀 Powered by AI | Built with Streamlit and LangChain")

