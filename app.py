from langchain_core.prompts import load_prompt, PromptTemplate
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from dotenv import load_dotenv
import streamlit as st
from models.itinerary import Itinerary
from utils.parsing import display_itinerary
from database.db import init_db, create_user, authenticate_user, save_itinerary, get_itineraries, save_chat_message, get_chat_history
import hashlib

load_dotenv()
init_db()

llm=HuggingFaceEndpoint(
    repo_id="mistralai/Mistral-7B-Instruct-v0.3",
    task="text-generation"
)

model=ChatHuggingFace(llm=llm)

template= PromptTemplate(
    input_variables=["destination", "duration_days", "budget", "preferences", "user_questions", "user_name"],
    template='''You are a highly intelligent, friendly and detail-oriented Travel Planner AI. Your job is to create a tailor-made travel itinerary based on the user’s inputs, and to answer follow-up questions about that itinerary.

User Inputs:
- Name: {user_name}
- Destination: {destination}
- Duration: {duration_days} days
- Budget: {budget}
- Preferences / Interests: {preferences} (if any)
- Additional Questions: {user_questions} (if any)

Your tasks:
1. First, greet the user by name, e.g. “Hello {user_name}!”.

2. Generate a day-by-day itinerary for the duration specified. For each day include:
   - Morning activity  
   - Afternoon activity  
   - Evening activity  
   - Recommended restaurant or local cuisine suggestion  
   - Accommodation tip (optional)  
   - Travel/transport–tip or local insight or cost-saving suggestion  

3. Ensure the plan fits within the budget if provided. Suggest cheaper alternatives if needed.

4. If the user asked any follow-up question(s) in {user_questions}, integrate that request into the itinerary (for example: “I want more adventure on day 2” → adjust Day 2 accordingly).

5. After the itinerary, provide a short “Tips” section with practical advice (e.g., local customs, best transport mode, packing, best time of day to visit major spots).

6. Format your output clearly with headings for each Day (Day 1, Day 2…), bullet points for activities, and a clear “Tips” section at the end.

Example:

Hello John! Here is your 5-day itinerary for Paris with a budget of $1000:

Day 1:
- Morning: Visit the historic city centre (free walking tour)
- Afternoon: Lunch at Café de Flore. Then explore the Louvre.
- Evening: Seine river cruise at sunset.
- Restaurant suggestion: Le Comptoir du Relais (moderate budget).
- Accommodation tip: Stay near Saint-Germain for easy transport.

Day 2:
- Morning: Bike ride through the Bois de Boulogne.
- Afternoon: Musée d’Orsay visit.
- Evening: Dinner at local bistro…  
…  
Tips:
- Use the métro instead of taxis to save budget.
- Many museums are free on the first Sunday of the month.
- Always carry a refillable water bottle.

Please give the itinerary in a single response, ready to show in a web app.
'''
)

if 'user_id' not in st.session_state:
    st.title("🔐 Login to AI Travel Itinerary Planner")
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
    # Sidebar for navigation and logout
    st.sidebar.title(f"Welcome, {st.session_state['username']}!")
    if st.sidebar.button("Logout"):
        del st.session_state['user_id']
        del st.session_state['username']
        st.rerun()
    
    page = st.sidebar.selectbox("Choose Page", ["Generate Itinerary", "Dashboard"])
    
    user_id = st.session_state['user_id']
    
    if page == "Generate Itinerary":
        st.title("🌍 Generate Your Travel Itinerary")
        with st.form("itinerary_form"):
            col1, col2 = st.columns(2)
            with col1:
                destination = st.text_input("Destination", placeholder="e.g., Paris")
                duration_days = st.number_input("Duration (in days)", min_value=1, max_value=30, value=5)
                budget = st.text_input("Budget", placeholder="e.g., $1000")
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
                            'user_name': user_name
                        })
                        st.session_state['generated_itinerary'] = result.content
                        st.session_state['itinerary_details'] = {
                            'destination': destination,
                            'duration': duration_days,
                            'budget': budget,
                            'preferences': preferences,
                            'user_name': user_name
                        }
                        st.success("Itinerary generated!")
        
        if 'generated_itinerary' in st.session_state:
            st.subheader("📅 Your Generated Itinerary")
            display_itinerary(st.session_state['generated_itinerary'])
            itinerary_name = st.text_input("Name your itinerary", placeholder="e.g., Paris Adventure")
            if st.button("Save Itinerary"):
                if itinerary_name:
                    itinerary = Itinerary(
                        name=itinerary_name,
                        content=st.session_state['generated_itinerary'],
                        destination=st.session_state['itinerary_details']['destination'],
                        duration=st.session_state['itinerary_details']['duration'],
                        budget=st.session_state['itinerary_details']['budget'],
                        preferences=st.session_state['itinerary_details']['preferences'],
                        user_name=st.session_state['itinerary_details']['user_name']
                    )
                    save_itinerary(itinerary, user_id)
                    del st.session_state['generated_itinerary']
                    del st.session_state['itinerary_details']
                    st.success("Itinerary saved!")
                else:
                    st.error("Please name your itinerary.")
    
    elif page == "Dashboard":
        st.title("📊 Your Dashboard")
        itineraries = get_itineraries(user_id)
        if not itineraries:
            st.info("No itineraries saved yet. Generate one first!")
        else:
            itinerary_names = [it.name for it in itineraries]
            selected_name = st.selectbox("Select an Itinerary", itinerary_names)
            selected_it = next(it for it in itineraries if it.name == selected_name)
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader(f"📍 {selected_it.name}")
                display_itinerary(selected_it.content)
            with col2:
                st.markdown("**Details:**")
                st.write(f"Destination: {selected_it.destination}")
                st.write(f"Duration: {selected_it.duration} days")
                st.write(f"Budget: {selected_it.budget}")
                st.write(f"Preferences: {selected_it.preferences}")
                st.write(f"User: {selected_it.user_name}")
            
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

