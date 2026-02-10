import streamlit as st
import os

st.title("🎬 Test App")
st.write("If you see this, Streamlit works! ✅")

# Check vectorstore
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(project_root, "vectorstore")

if os.path.exists(db_path):
    files = os.listdir(db_path)
    st.success(f"✅ vectorstore found with {len(files)} files")
    st.write(files)
else:
    st.error(f"❌ vectorstore NOT found at: {db_path}")