import streamlit as st
import re

def display_itinerary(content):
    # Extract greeting
    greeting_match = re.search(r'^(Hello .*?!)', content, re.MULTILINE)
    if greeting_match:
        st.markdown(f"### {greeting_match.group(1)}")
        content = content.replace(greeting_match.group(0), '').strip()
    
    # Split into sections: Days and Tips
    sections = re.split(r'(Day \d+:|Tips:)', content)
    
    current_section = None
    for part in sections:
        part = part.strip()
        if re.match(r'Day \d+:', part):
            current_section = part
            st.header(current_section)
        elif part == 'Tips:':
            current_section = part
            st.subheader(current_section)
        elif current_section and part:
            # Display bullet points as markdown
            st.markdown(part)