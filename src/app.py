"""
Date Night AI - Streamlit App
"""
import streamlit as st

# Page config
st.set_page_config(
    page_title="Date Night AI 🎬🍕",
    page_icon="🎬",
    layout="wide"
)

# Title
st.title("🎬🍕 Date Night AI")
st.markdown("*Your AI assistant for the perfect movie night!*")

# Sidebar
st.sidebar.header("Options")
cook_at_home = st.sidebar.checkbox("I want to cook at home", value=False)
show_prices = st.sidebar.checkbox("Compare delivery prices", value=True)

# Main input
st.markdown("---")
movie_name = st.text_input(
    "🎥 What movie are you watching tonight?",
    placeholder="e.g., The Godfather, Spirited Away, Pulp Fiction..."
)

# Process button
if st.button("🔮 Get Suggestions!", type="primary"):
    if movie_name:
        st.markdown("---")
        
        # Placeholder for now - we'll add real AI later!
        with st.spinner("🤔 Thinking about the perfect pairing..."):
            import time
            time.sleep(1)  # Simulate thinking
        
        # Movie info (placeholder)
        st.subheader(f"🎬 Movie: {movie_name}")
        st.info("Movie details will appear here once we connect the IMDB database!")
        
        # Food suggestion (placeholder)
        st.subheader("🍽️ Food Pairing Suggestion")
        st.success("Food pairing suggestions will appear here once we build the RAG system!")
        
        if cook_at_home:
            # Recipe (placeholder)
            st.subheader("👨‍🍳 Recipe")
            st.warning("Recipes will appear here once we add the recipe database!")
        
        if show_prices:
            # Price comparison (placeholder)
            st.subheader("💰 Price Comparison")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Uber Eats", "$--")
            with col2:
                st.metric("Wolt", "$--")
            with col3:
                st.metric("JustEat", "$--")
            st.info("Price comparison will work once we add the delivery APIs!")
    else:
        st.warning("Please enter a movie name!")

# Footer
st.markdown("---")
st.markdown("*Built with ❤️ using LangChain, ChromaDB, and Streamlit*")