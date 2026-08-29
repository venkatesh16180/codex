# streamlit_app.py
import os
os.environ['HF_HUB_OFFLINE'] = '1'
import streamlit as st
from sentence_transformers import SentenceTransformer
from db import get_connection
from chat import chat_with_specialist, HISTORY_TURNS
from history import (create_session, save_message, list_sessions, load_session_messages,
                      rename_session, export_session_as_markdown, delete_session, get_recent_history)

conn = get_connection()
embed_model = SentenceTransformer('all-MiniLM-L6-v2')

specialists = conn.execute("SELECT slug, display_name, specialist_id FROM specialists WHERE status='active'").fetchall()
labels = {s['display_name']: s for s in specialists}

choice = st.selectbox('Talk to:', list(labels.keys()))
specialist = labels[choice]

# Reset session state when switching specialists, so history doesn't bleed across them
if st.session_state.get('active_specialist_id') != specialist['specialist_id']:
    st.session_state.active_specialist_id = specialist['specialist_id']
    st.session_state.session_id = None
    st.session_state.history = []

with st.sidebar:
    # Moved here from the top of the main page -- the sidebar stays fully visible
    # regardless of how long the chat transcript grows, so the toggle no longer
    # requires scrolling back to the top of a long conversation to reach.
    use_web = st.toggle('Search the web if the local corpus is thin', value=False)

    st.subheader('Past conversations')
    if st.button('+ New chat'):
        st.session_state.session_id = None
        st.session_state.history = []

    for s in list_sessions(conn, specialist['specialist_id']):
        label = s['title'] or f"Session {s['session_id']}"
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(label, key=f"session_{s['session_id']}"):
                st.session_state.session_id = s['session_id']
                st.session_state.history = [
                    (m['content'], None) if m['role'] == 'user' else (None, m['content'])
                    for m in load_session_messages(conn, s['session_id'])
                ]
        with col2:
            with st.popover('⋮'):
                new_title = st.text_input('Rename', value=label, key=f"rename_{s['session_id']}")
                if st.button('Save', key=f"save_{s['session_id']}"):
                    rename_session(conn, s['session_id'], new_title)
                    st.rerun()
                md = export_session_as_markdown(conn, s['session_id'])
                st.download_button('Export as .md', md, file_name=f"session_{s['session_id']}.md",
                                    key=f"export_{s['session_id']}")

                st.divider()
                confirm_key = f"confirm_delete_{s['session_id']}"
                if not st.session_state.get(confirm_key):
                    if st.button('Delete', key=f"delete_{s['session_id']}"):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    st.warning('Delete this conversation permanently?')
                    if st.button('Yes, delete', key=f"confirm_{s['session_id']}"):
                        delete_session(conn, s['session_id'])
                        st.session_state.pop(confirm_key)
                        if st.session_state.session_id == s['session_id']:
                            st.session_state.session_id = None
                            st.session_state.history = []
                        st.rerun()

query = st.chat_input('Ask a question')

if query:
    recent_history = get_recent_history(conn, st.session_state.session_id, turns=HISTORY_TURNS)
    answer = chat_with_specialist(conn, embed_model, specialist['slug'], query,
                                   use_web=use_web, history=recent_history)

    if st.session_state.session_id is None:
        st.session_state.session_id = create_session(conn, specialist['specialist_id'], query)

    save_message(conn, st.session_state.session_id, 'user', query)  # used_web defaults to 0 -- a question doesn't "use the web"
    save_message(conn, st.session_state.session_id, 'assistant', answer, used_web=use_web)

    st.session_state.history.append((query, answer))

for q, a in st.session_state.history:
    if q:
        st.chat_message('user').write(q)
    if a:
        st.chat_message('assistant').write(a)