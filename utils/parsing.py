import streamlit as st
import re
import html


def _activity_icon(text: str) -> str:
    t = text.lower()
    if 'morning' in t or 'breakfast' in t or 'sunrise' in t:
        return '☀️'
    if 'afternoon' in t or 'lunch' in t:
        return '🌤️'
    if 'evening' in t or 'dinner' in t or 'night' in t:
        return '🌙'
    if 'restaurant' in t or 'cuisine' in t or 'food' in t or 'dining' in t:
        return '🍽️'
    if 'hotel' in t or 'accommodation' in t or 'stay' in t:
        return '🏨'
    if 'train' in t or 'bus' in t or 'taxi' in t or 'transport' in t:
        return '🚗'
    if 'flight' in t or 'airport' in t or 'airline' in t:
        return '✈️'
    if 'museum' in t or 'gallery' in t:
        return '🖼️'
    if 'shopping' in t or 'market' in t or 'bazaar' in t:
        return '🛍️'
    # default icon
    return '📌'


def _extract_price(text: str) -> str:
    # Look for rupee symbol or INR or 'rupees'
    m = re.search(r'(₹\s?[0-9,]+|INR\s?[0-9,]+|[0-9,]+\s?(rupees|Rs\.?))', text, re.IGNORECASE)
    return m.group(0) if m else ''


def _clean_markdown(text: str) -> str:
    """Remove common Markdown formatting and convert links to plain text."""
    if not text:
        return text
    # Convert links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Remove bold/italic/backticks markers
    text = re.sub(r"(\*\*|__|\*|`)", "", text)
    # Remove heading markers (###, ##, #)
    text = re.sub(r"^\s*#+\s*", "", text)
    # Remove common list markers at line start
    text = re.sub(r"^\s*[-\*\+]\s*", "", text)
    return text.strip()

def display_itinerary(content, theme='Dark'):
    # Define colors for dark theme
    bg_color = '#121212'
    text_color = '#e0e0e0'
    card_bg = 'linear-gradient(135deg, #1e1e1e 0%, #2c2c2c 100%)'
    tips_bg = 'linear-gradient(135deg, #333 0%, #444 100%)'
    activity_bg = '#2c2c2c'
    border_color = '#555'
    
    # Add custom CSS for animations and modern design
    st.markdown(f"""
    <style>
    body {{
        background-color: {bg_color} !important;
        color: {text_color} !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
    }}
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(20px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes slideInLeft {{
        from {{ opacity: 0; transform: translateX(-30px); }}
        to {{ opacity: 1; transform: translateX(0); }}
    }}
    .day-card {{
        background: {card_bg};
        color: white;
        padding: 24px;
        border-radius: 16px;
        margin: 20px 0;
        animation: fadeIn 0.8s ease-out;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        backdrop-filter: blur(10px);
        border: 1px solid {border_color};
        transition: transform 0.3s ease;
    }}
    .day-card:hover {{
        transform: translateY(-5px);
    }}
    .tips-card {{
        background: {tips_bg};
        color: white;
        padding: 24px;
        border-radius: 16px;
        margin: 20px 0;
        animation: fadeIn 1s ease-out;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        backdrop-filter: blur(10px);
        border: 1px solid {border_color};
        transition: transform 0.3s ease;
    }}
    .tips-card:hover {{
        transform: translateY(-5px);
    }}
    .activity-list {{
        background: {activity_bg};
        padding: 20px;
        border-radius: 12px;
        margin: 15px 0;
        animation: fadeIn 1.2s ease-out;
        border-left: 4px solid #bb86fc;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
    }}
    .day-card ul li {{
        animation: slideInLeft 0.6s ease-out;
        animation-fill-mode: both;
        margin: 10px 0;
        padding: 8px 0;
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }}
    .day-card ul li:nth-child(1) {{ animation-delay: 0.1s; }}
    .day-card ul li:nth-child(2) {{ animation-delay: 0.2s; }}
    .day-card ul li:nth-child(3) {{ animation-delay: 0.3s; }}
    .day-card ul li:nth-child(4) {{ animation-delay: 0.4s; }}
    .day-card ul li:nth-child(5) {{ animation-delay: 0.5s; }}
    .day-card ul li:nth-child(6) {{ animation-delay: 0.6s; }}
    .day-card ul li:nth-child(7) {{ animation-delay: 0.7s; }}
    .day-card ul li:nth-child(8) {{ animation-delay: 0.8s; }}
    .modern-list {{
        list-style: none;
        padding: 0;
    }}
    .modern-list li:before {{
        content: "✨ ";
        font-size: 1.2em;
        margin-right: 8px;
    }}
    .act-icon {{ margin-right: 8px; font-size: 1.1em; }}
    .price-badge {{ background: #bb86fc; color: #121212; padding: 4px 8px; border-radius: 12px; font-weight: 700; margin-left: 8px; font-size: 0.9em; }}
    .act-text {{ vertical-align: middle; }}
    .day-card h3, .tips-card h4 {{
        margin: 0 0 16px 0;
        font-weight: 700;
        font-size: 1.5em;
    }}
    </style>
    """, unsafe_allow_html=True)
    
    # Extract greeting
    greeting_match = re.search(r'^(Hello .*?!)', content, re.MULTILINE | re.IGNORECASE)
    if greeting_match:
        st.markdown(f"### {greeting_match.group(1)}")
        content = content.replace(greeting_match.group(0), '').strip()
    
    # Improved parsing: Find all Day sections, Tips, and Total Cost
    day_pattern = r'(Day \d+:.*?)(?=Day \d+:|Tips:|$)'
    tips_pattern = r'(Tips:.*?)(?=Total Estimated Cost:|$)'
    cost_pattern = r'(Total Estimated Cost:.*?)$'
    
    days = re.findall(day_pattern, content, re.DOTALL | re.IGNORECASE)
    tips_match = re.search(tips_pattern, content, re.DOTALL | re.IGNORECASE)
    tips = tips_match.group(1) if tips_match else ""
    cost_match = re.search(cost_pattern, content, re.DOTALL | re.IGNORECASE)
    cost = cost_match.group(1) if cost_match else ""
    
    # Remove tips and cost from content for days
    content_without_extras = re.sub(tips_pattern, '', content, flags=re.DOTALL | re.IGNORECASE).strip()
    content_without_extras = re.sub(cost_pattern, '', content_without_extras, flags=re.DOTALL | re.IGNORECASE).strip()
    
    # Display days
    for day in days:
        day = day.strip()
        if day:
            day_title_match = re.match(r'(Day \d+:)', day, re.IGNORECASE)
            if day_title_match:
                title = day_title_match.group(1)
                activities = day.replace(title, '').strip()
                raw_lines = [line for line in activities.split('\n') if line.strip()]
                activity_lines = [_clean_markdown(line).strip() for line in raw_lines if _clean_markdown(line).strip()]
                if activity_lines:
                    items_html = []
                    for line in activity_lines:
                        icon = _activity_icon(line)
                        price = _extract_price(line)
                        display_text = line
                        if price:
                            # remove the price snippet from the display text
                            display_text = re.sub(re.escape(price), '', display_text, flags=re.IGNORECASE).strip(' -:')
                        display_text = html.escape(display_text)
                        price_html = f"<span class=\"price-badge\">{html.escape(price)}</span>" if price else ''
                        items_html.append(f"<li><span class=\"act-icon\">{icon}</span><span class=\"act-text\">{display_text}</span>{price_html}</li>")

                    st.markdown(f"""
                    <div class="day-card">
                        <h3 style="margin: 0; font-weight: bold;">📅 {title}</h3>
                        <ul class="modern-list">
                            {''.join(items_html)}
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Display tips
    if tips:
        tips_content = tips.replace('Tips:', '').strip()
        raw_tips = [line for line in tips_content.split('\n') if line.strip()]
        tip_lines = [_clean_markdown(line) for line in raw_tips if _clean_markdown(line)]
        if tip_lines:
            st.markdown(f"""
            <div class="tips-card">
                <h4 style="margin: 0; font-weight: bold;">💡 Tips</h4>
                <div class="activity-list">
                    {"<br>".join(f"• {line}" for line in tip_lines)}
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Display total cost
    if cost:
        cost_content = cost.replace('Total Estimated Cost:', '').strip()
        st.markdown(f"""
        <div class="tips-card">
            <h4 style="margin: 0; font-weight: bold;">💰 Total Estimated Cost</h4>
            <div class="activity-list">
                {cost_content}
            </div>
        </div>
        """, unsafe_allow_html=True)