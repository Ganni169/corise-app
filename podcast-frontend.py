import streamlit as st
import json
import os
# import yagmail


# Load all episode data files
episode_files = [file for file in os.listdir() if file.endswith(".json")]
podcast_data = []


# Load episode data from each file
for episode_file in episode_files:
    with open(episode_file, 'r') as json_file:
        episode = json.load(json_file)
        podcast_data.append(episode)

# Title and Header
st.title("Podcast Summary App")
st.sidebar.header("Select Podcast Episode")

# Sidebar Dropdown
selected_episode_title = st.sidebar.selectbox("Choose an episode", [episode['episode_title'] for episode in podcast_data])

# Find selected episode data
selected_episode_data = next((episode for episode in podcast_data if episode['episode_title'] == selected_episode_title), None)

# Display selected episode details in a layout with two column rows
if selected_episode_data:
    col1, col2 = st.columns(2)

    # First row: Image on the left, Episode name and date on the right
    with col1:
        st.image(selected_episode_data['podcast_image'], caption=selected_episode_data['podcast_title'], use_column_width=True, width=150)
    with col2:
        st.write(f"Episode Title: {selected_episode_data['episode_title']}")
        st.write(f"Episode Date: {selected_episode_data['episode_date']}")
        # Episode Characters
        st.write("Episode Characters:")
        for character in selected_episode_data['episode_characters']:
            st.write(f"- Character Name: {character['character_name']}")
            st.write(f"  Description: {character['character_description']}")
            if character['wikipedia'] != "":
                st.write(f"  Wikipedia: {character['wikipedia']}")

    # Second row: Podcast player
    st.audio(selected_episode_data['episode_audio_url'], format='audio/mp3')

    # Episode summary
    st.write(f"Summary: {selected_episode_data['episode_summary']}")

    # Episode Highlights
    st.write(f"{selected_episode_data['episode_highlights']}")
