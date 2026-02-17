import streamlit as st
import chromadb
import os
import requests
import urllib.parse
from dotenv import load_dotenv
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate

# Load .env from project root (not cwd)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))

# ─────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Hangry 🍕",
    page_icon="🍕",
    layout="wide"
)

# ─────────────────────────────────────────────
# Load ChromaDB & LLM (cached)
# ─────────────────────────────────────────────
@st.cache_resource
def load_db():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, "vectorstore")
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_collection("movies")
    return collection

@st.cache_resource
def load_llm():
    return OllamaLLM(model="llama3")

collection = load_db()
llm = load_llm()

# ─────────────────────────────────────────────
# TMDB API (Free, no signup needed!)
# ─────────────────────────────────────────────
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/w500"
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")



def search_tmdb(query: str, n_results: int = 5, year_min: int = 1900, year_max: int = 2025, filter_year: bool = False):
    """Search TMDB API for movies"""
    try:
        url = f"{TMDB_BASE_URL}/search/movie"

        # Extract year from query like "The Housemaid (2025)"
        import re
        year_match = re.search(r'\((\d{4})\)', query)
        clean_query = re.sub(r'\(\d{4}\)', '', query).strip()  # Remove (2025) from query

        params = {
            "api_key": TMDB_API_KEY,
            "query": clean_query if clean_query else query,
            "language": "en-US",
            "page": 1,
            "include_adult": False
        }

        # If user typed year in query like "The Housemaid (2025)", use it
        if year_match:
            params["year"] = int(year_match.group(1))

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        movies = []
        for item in data.get("results", []):
            year_str = item.get("release_date", "")[:4] if item.get("release_date") else "Unknown"

            # Year range filter (from sidebar)
            if filter_year and year_str != "Unknown":
                try:
                    year_int = int(year_str)
                    if year_int < year_min or year_int > year_max:
                        continue
                except ValueError:
                    pass

            # Resolve genre IDs to names
            genre_names = ", ".join([genre_map.get(gid, "Unknown") for gid in item.get("genre_ids", [])])

            poster = f"{TMDB_IMAGE_URL}{item['poster_path']}" if item.get("poster_path") else None

            movies.append({
                "title": item.get("title", "Unknown"),
                "year": year_str,
                "genre": genre_names,
                "overview": item.get("overview", "No description available"),
                "rating": item.get("vote_average", "N/A"),
                "poster": poster,
                "source": "TMDB 🌐"
            })

            if len(movies) >= n_results:
                break

        return movies
    except Exception as e:
        st.warning(f"⚠️ TMDB search failed: {e}")
        return []



def get_tmdb_genres():
    """Fetch genre mapping from TMDB"""
    try:
        url = f"{TMDB_BASE_URL}/genre/movie/list"
        params = {"api_key": TMDB_API_KEY, "language": "en-US"}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        return {str(g["id"]): g["name"] for g in data.get("genres", [])}
    except:
        return {}

def get_trending_movies():
    """Fetch trending movies from TMDB"""
    try:
        url = f"{TMDB_BASE_URL}/trending/movie/week"
        params = {"api_key": TMDB_API_KEY, "language": "en-US"}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        return data.get("results", [])[:5]
    except:
        return []

# Load genre mapping once
genre_map = get_tmdb_genres()



def resolve_genres(genre_id_string: str) -> str:
    """Convert genre IDs to names"""
    if not genre_id_string or genre_id_string == "Unknown":
        return "Unknown"
    ids = [gid.strip() for gid in genre_id_string.split(",")]
    names = [genre_map.get(gid, gid) for gid in ids]
    return ", ".join(names)

# ─────────────────────────────────────────────
# Local ChromaDB Search
# ─────────────────────────────────────────────
def search_local(query, n_results=5, year_min=1900, year_max=2025, filter_year=True):
    """Search local ChromaDB and optionally filter by year"""
    fetch_count = n_results * 10
    results = collection.query(query_texts=[query], n_results=fetch_count)

    if not results['documents'][0]:
        return []

    movies = []
    for i, meta in enumerate(results['metadatas'][0]):
        if filter_year:
            try:
                year_str = str(meta.get('year', '')).strip()
                year = int(float(year_str))
                if year < year_min or year > year_max:
                    continue
            except (ValueError, TypeError):
                pass

        movies.append({
            "title": meta.get("title", "Unknown"),
            "year": str(meta.get("year", "Unknown")),
            "genre": meta.get("genre", "Unknown"),
            "overview": results['documents'][0][i],
            "rating": "N/A",
            "poster": None,
            "source": "Local DB 💾"
        })

        if len(movies) >= n_results:
            break

    return movies

# ─────────────────────────────────────────────
# Hybrid Search (TMDB + Local)
# ─────────────────────────────────────────────
def hybrid_search(query, n_results=5, source="Both", year_min=1900, year_max=2025, filter_year=False):
    """Search both TMDB API and local ChromaDB"""
    movies = []

    if source in ["TMDB API 🌐", "Both"]:
        tmdb_results = search_tmdb(query, n_results, year_min, year_max, filter_year)
        for m in tmdb_results:
            m['genre'] = resolve_genres(m['genre'])
        movies.extend(tmdb_results)

    if source in ["Local DB 💾", "Both"]:
        local_results = search_local(query, n_results, year_min, year_max, filter_year)
        movies.extend(local_results)

    # Remove duplicates by title
    seen = set()
    unique = []
    for m in movies:
        title_lower = m['title'].lower()
        if title_lower not in seen:
            seen.add(title_lower)
            unique.append(m)

    return unique[:n_results]



# ─────────────────────────────────────────────
# Free Recipe API (No key needed!)
# ─────────────────────────────────────────────

def clean_dish_name(dish_name: str) -> str:
    """Clean LLM-generated dish names for better recipe search"""
    import re

    # Remove emojis
    dish_name = re.sub(r'[^\w\s\'-]', '', dish_name)

    # Remove common LLM flair words
    flair_words = [
        "seduction", "romantic", "passionate", "cozy", "spooky",
        "dreamy", "magical", "enchanted", "ultimate", "perfect",
        "date night", "love", "special", "delicious", "homemade",
        "gourmet", "classic", "authentic", "traditional", "famous",
        "epic", "heavenly", "divine", "sinful", "decadent",
        "lusty", "fiery", "sizzling", "steamy", "midnight",
        "moonlit", "candlelit", "sultry", "sensual", "forbidden",
        "irresistible", "tempting", "indulgent", "luxurious",
    ]

    words = dish_name.split()
    cleaned_words = [w for w in words if w.lower().strip() not in flair_words]
    dish_name = " ".join(cleaned_words).strip()

    # Remove extra whitespace
    dish_name = re.sub(r'\s+', ' ', dish_name).strip()

    return dish_name

def search_recipe_smart(dish_name: str):
    """Search recipe with fallback: full name → cleaned → individual words"""

    # Step 1: Try original name (cleaned of emojis/flair)
    cleaned = clean_dish_name(dish_name)

    recipe = search_recipe(cleaned)
    if recipe:
        return recipe

    # Step 2: Try progressively shorter names
    # "Seduction Fettuccine Alfredo" → "Fettuccine Alfredo" → "Fettuccine"
    words = cleaned.split()
    while len(words) > 1:
        words.pop(0)  # Remove first word
        attempt = " ".join(words)
        recipe = search_recipe(attempt)
        if recipe:
            return recipe

    # Step 3: Try each word individually (longest first)
    words = cleaned.split()
    words.sort(key=len, reverse=True)  # Try longest words first
    for word in words:
        if len(word) > 3:  # Skip short words like "the", "and"
            recipe = search_recipe(word)
            if recipe:
                return recipe

    return None



def search_recipe(dish_name: str):
    """Search for recipes using TheMealDB (free, no key)"""
    try:
        url = "https://www.themealdb.com/api/json/v1/1/search.php"
        params = {"s": dish_name}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        meals = data.get("meals")
        if not meals:
            return None

        meal = meals[0]

        ingredients = []
        for i in range(1, 21):
            ingredient = meal.get(f"strIngredient{i}", "")
            measure = meal.get(f"strMeasure{i}", "")
            if ingredient and ingredient.strip():
                ingredients.append(f"{measure.strip()} {ingredient.strip()}")

        return {
            "name": meal.get("strMeal", "Unknown"),
            "category": meal.get("strCategory", ""),
            "cuisine": meal.get("strArea", ""),
            "instructions": meal.get("strInstructions", ""),
            "image": meal.get("strMealThumb", ""),
            "video": meal.get("strYoutube", ""),
            "ingredients": ingredients,
            "source": meal.get("strSource", "")
        }
    except Exception:
        return None

def get_order_links(dish_name: str):
    """Generate deep-link order URLs that search for the dish directly"""
    cleaned_dish_name = clean_dish_name(dish_name)
    encoded = urllib.parse.quote(cleaned_dish_name)

    return {
        "🟢 Uber Eats": f"https://www.ubereats.com/search?q={encoded}",
        "🟠 Lieferando": f"https://www.lieferando.de/en/delivery/food/{encoded}",
        "🟧 Just Eat": f"https://www.just-eat.co.uk/search?q={encoded}"
    }

def get_youtube_link(dish_name: str):
    """Generate YouTube search link for recipe video"""
    encoded = urllib.parse.quote(f"{dish_name} recipe")
    return f"https://www.youtube.com/results?search_query={encoded}"

# ─────────────────────────────────────────────
# Local ChromaDB Search
# ─────────────────────────────────────────────
def search_local(query, n_results=5, year_min=1900, year_max=2025, filter_year=True):
    """Search local ChromaDB and optionally filter by year"""
    fetch_count = n_results * 10
    results = collection.query(query_texts=[query], n_results=fetch_count)

    if not results['documents'][0]:
        return []

    movies = []
    for i, meta in enumerate(results['metadatas'][0]):
        # Year filter
        if filter_year:
            try:
                year_str = str(meta.get('year', '')).strip()
                year = int(float(year_str))
                if year < year_min or year > year_max:
                    continue
            except (ValueError, TypeError):
                pass  # Include movies with unknown years

        movies.append({
            "title": meta.get("title", "Unknown"),
            "year": str(meta.get("year", "Unknown")),
            "genre": meta.get("genre", "Unknown"),
            "overview": results['documents'][0][i],
            "rating": "N/A",
            "poster": None,
            "source": "Local DB 💾"
        })

        if len(movies) >= n_results:
            break

    return movies

# ─────────────────────────────────────────────
# Hybrid Search (TMDB + Local)
# ─────────────────────────────────────────────
def hybrid_search(query, n_results=5, source="Both", year_min=1900, year_max=2025, filter_year=False):
    """Search both TMDB API and local ChromaDB"""
    movies = []

    if source in ["TMDB API 🌐", "Both"]:
        tmdb_results = search_tmdb(query, n_results, year_min, year_max, filter_year)
        # Resolve genre IDs to names
        for m in tmdb_results:
            m['genre'] = resolve_genres(m['genre'])
        movies.extend(tmdb_results)

    if source in ["Local DB 💾", "Both"]:
        local_results = search_local(query, n_results, year_min, year_max, filter_year)
        movies.extend(local_results)

    # Remove duplicates by title
    seen = set()
    unique = []
    for m in movies:
        title_lower = m['title'].lower()
        if title_lower not in seen:
            seen.add(title_lower)
            unique.append(m)

    return unique[:n_results]

# ─────────────────────────────────────────────
# Prompt Template
# ─────────────────────────────────────────────


PROMPT = PromptTemplate(
    input_variables=["movie_info", "title", "mood", "cuisine_pref"],
    template="""You are Hangry — a fun movie + food pairing expert! 🍕

Movie Information:
{movie_info}

User's Mood: {mood}
Cuisine Preference: {cuisine_pref}

Based on this movie's theme, genre, and the user's preferences,
suggest the perfect food pairing for watching "{title}".

IMPORTANT: You MUST start your response with these THREE lines EXACTLY (no emojis, no extra text on these lines):

MAIN DISH: [just the dish name, nothing else]
DRINK: [just the drink name, nothing else]
SNACK: [just the snack name, nothing else]

Then on new lines describe each:

🍽️ **Main Dish**: [dish with fun description]
🥤 **Drink**: [drink with fun description]
🍿 **Snack**: [snack with fun description]
💡 **Why This Works**: [one sentence]
🎯 **Mood Setting Tip**: [one tip]

Example of CORRECT response:
MAIN DISH: Kung Pao Chicken
DRINK: Lychee Tea
SNACK: Edamame

🍽️ **Main Dish**: Kung Pao Chicken - A spicy and savory delight...

Keep it fun, brief, and use emojis in descriptions only!"""
)



def extract_dish_name(response: str) -> dict:
    """Extract dish names from LLM response - handles multiple formats"""
    import re
    dishes = {"main": "", "drink": "", "snack": ""}

    # ── Normalize: "MAIN_DISH:" → "MAIN DISH:" so one regex handles both ──
    normalized = response.replace("MAIN_DISH:", "MAIN DISH:")

    # ── Strategy 1: Regex-based (works even if all on one line) ──
    main_match = re.search(r'MAIN DISH:\s*(.+?)(?:\s*DRINK:|\s*SNACK:|\n|$)', normalized)
    drink_match = re.search(r'DRINK:\s*(.+?)(?:\s*SNACK:|\s*MAIN DISH:|\n|$)', normalized)
    snack_match = re.search(r'SNACK:\s*(.+?)(?:\s*MAIN DISH:|\s*DRINK:|\n|$)', normalized)

    if main_match:
        dishes["main"] = main_match.group(1).strip()
    if drink_match:
        dishes["drink"] = drink_match.group(1).strip()
    if snack_match:
        dishes["snack"] = snack_match.group(1).strip()

    # ── Strategy 2: Fallback to markdown format ──
    if not dishes["main"]:
        for line in response.split("\n"):
            line = line.strip()
            if "Main Dish" in line and ":" in line:
                raw = line.split(":")[-1].strip().strip("*").strip()
                for sep in [" - ", " – ", ". ", ", a ", ", this ", ", an "]:
                    if sep in raw:
                        raw = raw.split(sep)[0].strip()
                        break
                dishes["main"] = raw
            elif "Drink" in line and ":" in line and not dishes["drink"]:
                raw = line.split(":")[-1].strip().strip("*").strip()
                for sep in [" - ", " – ", ". ", ", a ", ", this ", ", an "]:
                    if sep in raw:
                        raw = raw.split(sep)[0].strip()
                        break
                dishes["drink"] = raw
            elif "Snack" in line and ":" in line and not dishes["snack"]:
                raw = line.split(":")[-1].strip().strip("*").strip()
                for sep in [" - ", " – ", ". ", ", a ", ", this ", ", an "]:
                    if sep in raw:
                        raw = raw.split(sep)[0].strip()
                        break
                dishes["snack"] = raw

    # ── Clean all dish names ──
    for key in dishes:
        if dishes[key]:
            dishes[key] = re.sub(r'[^\w\s\'-]', '', dishes[key]).strip()
            dishes[key] = re.sub(r'\s+', ' ', dishes[key]).strip()

    return dishes





# ─────────────────────────────────────────────
# Sidebar (minimal - stats only)
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("📊 Stats & Info")

    tmdb_status = "✅ Connected" if genre_map else "❌ Failed"
    st.metric("TMDB API", tmdb_status)
    st.metric("Movies Available", "Millions 🌐")

    st.markdown("---")
    st.markdown(
        """
        ### ℹ️ How it works
        1. Search for a movie
        2. AI suggests food pairings
        3. Get recipes or order online!
        """
    )

# ─────────────────────────────────────────────
# Main Content
# ─────────────────────────────────────────────
st.title("� Hangry")
st.subheader("Pick a Movie. We'll Fix Your Hangry.")
st.markdown("---")

# ─────────────────────────────────────────────
# Search Bar
# ─────────────────────────────────────────────
col1, col2 = st.columns([3, 1])

with col1:
    movie_query = st.text_input(
        "🔍 Search for a movie or describe what you want to watch:",
        placeholder="e.g., 'Godfather', 'romantic comedy', 'Snow White'"
    )

with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    search_button = st.button("🎬 Find Pairings!", type="primary", use_container_width=True)



# ─────────────────────────────────────────────
# Preferences (in body, not sidebar)
# ─────────────────────────────────────────────
st.markdown("### 🎛️ Your Preferences")

pref_col1, pref_col2, pref_col3, pref_col4, pref_col5 = st.columns(5)

with pref_col1:
    mood = st.selectbox(
        "😊 Mood",
        ["Romantic", "Adventurous", "Cozy & Comfort", "Fun & Energetic",
         "Chill & Relaxed", "Spooky", "Nostalgic"]
    )

with pref_col2:
    cuisine_pref = st.selectbox(
        "🍴 Cuisine",
        ["No Preference", "Italian", "Japanese", "Mexican", "Indian",
         "French", "American", "Korean", "Thai", "Mediterranean"]
    )

with pref_col3:
    n_suggestions = st.slider(
        "📊 Results",
        min_value=1, max_value=5, value=3
    )

with pref_col4:
    enable_year_filter = st.checkbox("📅 Year filter", value=False)
    if enable_year_filter:
        year_range = st.slider(
            "Year range",
            min_value=1900,
            max_value=2025,
            value=(1970, 2025),
            step=1
        )
    else:
        year_range = (1900, 2025)

with pref_col5:
    search_source = st.selectbox(
        "🔍 Source",
        ["Both", "TMDB API 🌐", "Local DB 💾"]
    )

st.markdown("---")
# ─────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────
if search_button and movie_query:
    with st.spinner("🔍 Searching movies..."):
        movies = hybrid_search(
            movie_query,
            n_results=n_suggestions,
            source=search_source,
            year_min=year_range[0],
            year_max=year_range[1],
            filter_year=enable_year_filter
        )

    if not movies:

        st.error(f"❌ No movies found for '{movie_query}'"
                 + (f" between {year_range[0]}-{year_range[1]}. Try disabling year filter!" if enable_year_filter else "! Try a different search."))
    else:
        st.markdown("---")
        if enable_year_filter:
            st.header(f"🎬 Movie Matches ({year_range[0]} - {year_range[1]})")
        else:
            st.header("🎬 Movie Matches")

        tab_names = [f"🎬 {m['title']}" for m in movies]
        tabs = st.tabs(tab_names)

        for i, tab in enumerate(tabs):
            with tab:
                movie = movies[i]

                # ── Row 1: Movie Info + Food Pairing ──
                col_poster, col_info, col_pairing = st.columns([1, 1, 2])

                # Poster (TMDB only)
                with col_poster:
                    if movie.get('poster'):
                        st.image(movie['poster'], use_container_width=True)
                    else:
                        st.markdown("### 🎬")
                        st.caption("No poster available")

                # Movie Info
                with col_info:
                    st.markdown(f"### {movie['title']}")
                    st.markdown(f"📅 **Year:** {movie['year']}")
                    st.markdown(f"🎭 **Genre:** {movie['genre']}")
                    if movie.get('rating') and movie['rating'] != "N/A":
                        st.markdown(f"⭐ **Rating:** {movie['rating']}")
                    st.caption(f"Source: {movie['source']}")

                    if movie.get('overview'):
                        with st.expander("📖 Overview"):
                            st.write(movie['overview'])

                # Food Pairing
                with col_pairing:
                    movie_info = f"Title: {movie['title']}. Year: {movie['year']}. Genre: {movie['genre']}. Overview: {movie.get('overview', 'N/A')}"

                    with st.spinner(f"🤖 Generating pairing for {movie['title']}..."):
                        response = llm.invoke(
                            PROMPT.format(
                                movie_info=movie_info,
                                title=movie['title'],
                                mood=mood,
                                cuisine_pref=cuisine_pref
                            )
                        )
                    st.markdown("### 🍕 Food Pairing")
                    st.markdown(response)

                    # Extract dish names
                    dishes = extract_dish_name(response)

                st.markdown("---")

                # ── Row 2: Recipe + Order Online ──
                st.markdown("### 🍳 Recipe & 🛒 Order Online")

                recipe_tab, order_tab = st.tabs(["🍳 Cook It Yourself", "🛒 Order Online"])

                # ── Recipe Tab ──
                with recipe_tab:
                    dish_to_search = dishes.get("main") or movie_query

                    if dish_to_search:
                        with st.spinner(f"🔍 Finding recipe for {dish_to_search}..."):
                            recipe = search_recipe_smart(dish_to_search)

                        if recipe:
                            col_recipe_img, col_recipe_details = st.columns([1, 2])

                            with col_recipe_img:
                                if recipe['image']:
                                    st.image(recipe['image'], use_container_width=True)
                                st.caption(f"🌍 {recipe['cuisine']} | 📂 {recipe['category']}")

                            with col_recipe_details:
                                st.markdown(f"### 🍳 {recipe['name']}")

                                with st.expander("📝 Ingredients", expanded=True):
                                    for ing in recipe['ingredients']:
                                        st.markdown(f"- {ing}")

                                with st.expander("👨‍🍳 Cooking Instructions"):
                                    st.write(recipe['instructions'])

                                if recipe['video']:
                                    st.markdown(f"[🎥 Watch Video Tutorial]({recipe['video']})")

                        else:
                            st.info(f"📖 No exact recipe found for '{dish_to_search}'")
                            st.markdown("**Try searching manually:**")
                            yt_link = get_youtube_link(dish_to_search)
                            st.markdown(f"- [🎥 YouTube: {dish_to_search} recipe]({yt_link})")
                            google_link = f"https://www.google.com/search?q={urllib.parse.quote(dish_to_search + ' recipe')}"
                            st.markdown(f"- [🔍 Google: {dish_to_search} recipe]({google_link})")
                    else:
                        st.warning("Could not extract dish name. Try searching manually!")

                # ── Order Online Tab ──
                with order_tab:
                    dish_to_order = dishes.get("main") or movie_query

                    st.markdown(f"### 🛒 Order **{dish_to_order}** Online")
                    st.markdown("Click any platform to order:")

                    order_links = get_order_links(dish_to_order)

                    order_cols = st.columns(4)
                    for j, (platform, link) in enumerate(order_links.items()):
                        with order_cols[j % 4]:
                            st.markdown(f"[{platform}]({link})")

                    st.markdown("---")

                    if dishes.get("drink"):
                        st.markdown(f"**🥤 Order {dishes['drink']}:**")
                        drink_links = get_order_links(dishes['drink'])
                        drink_cols = st.columns(4)
                        for j, (platform, link) in enumerate(drink_links.items()):
                            with drink_cols[j % 4]:
                                st.markdown(f"[{platform}]({link})")

                    if dishes.get("snack"):
                        st.markdown(f"**🍿 Order {dishes['snack']}:**")
                        snack_links = get_order_links(dishes['snack'])
                        snack_cols = st.columns(4)
                        for j, (platform, link) in enumerate(snack_links.items()):
                            with snack_cols[j % 4]:
                                st.markdown(f"[{platform}]({link})")

# ─────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        Made with ❤️ using Streamlit + Ollama + ChromaDB + TMDB + TheMealDB<br>
        � Hangry — Pick a Movie. We'll Fix Your Hangry.
    </div>
    """,
    unsafe_allow_html=True
)