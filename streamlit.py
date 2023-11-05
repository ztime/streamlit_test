import streamlit as st
import pandas as pd
from scipy import stats
import plotly.express as px
import os

file_source_prefix = os.environ.get("FILE_SOURCE_PREFIX")
if file_source_prefix is None:
    file_source_prefix = ""

@st.cache_data
def load_dropdown_data():
    ids_and_albums = pd.read_csv(f'{file_source_prefix}artist_to_id.csv')
    artist_name_list = ids_and_albums['artist_name'].tolist()
    mapping_album_id = ids_and_albums.set_index('artist_name').to_dict()['album_id']
    return artist_name_list, mapping_album_id

@st.cache_data
def load_all_ratings():
    all_ratings = pd.read_csv(f'{file_source_prefix}rating_events.csv')
    return all_ratings

@st.cache_data
def load_all_albums():
    all_albums = pd.read_csv(f'{file_source_prefix}top_500_albums.csv')
    return all_albums

def load_albums_ratings(album_1_id, album_2_id):
    all_ratings = load_all_ratings()
    album_1_data = all_ratings[all_ratings['album_id'] == album_1_id]
    album_2_data = all_ratings[all_ratings['album_id'] == album_2_id]
    return album_1_data, album_2_data

def load_albums_metadata(album_1_id, album_2_id):
    all_albums = load_all_albums()
    album_1_metadata = all_albums[all_albums['album_id'] == album_1_id].to_dict('records')[0]
    album_2_metadata = all_albums[all_albums['album_id'] == album_2_id].to_dict('records')[0]
    return album_1_metadata, album_2_metadata

artist_name_list, mapping_album_id = load_dropdown_data()

st.title("Battle of the albums - Corona edition")
st.subheader("Pick two albums from 2020 and see which one is better!")

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        st.header("First album:")
        album_1_name = st.selectbox(
            'Search using "Artist - Album"',
            artist_name_list,
            key='album_1_name'
        )
    with col2:
        st.header("Second album:")
        album_2_name = st.selectbox(
            'Search using "Artist - Album"',
            artist_name_list,
            key='album_2_name'
        )
st.divider()

try:
    album_1_id = mapping_album_id[album_1_name]
    album_2_id = mapping_album_id[album_2_name]
except KeyError as e:
    st.write("Something went wrong, couldn't find those albums, try again")

album_1_data, album_2_data = load_albums_ratings(album_1_id, album_2_id)
album_1_metadata, album_2_metadata = load_albums_metadata(album_1_id, album_2_id)

with st.container():
    col1,col2 = st.columns(2)
    def display_album_data(m):
        st.header(m['name'])
        st.subheader(m['artist'])
        st.text(f"Release year: {m['date']}")
        st.metric(label="Rating", value=m['rating'])
        st.text(f"Genres: {m['genres']}")
    with col1:
        display_album_data(album_1_metadata)
    with col2:
        display_album_data(album_2_metadata)
st.divider()
# Perform t-test, previous investigation between Yessuz and deltron 
# had that levene test failed, indicating that the samples does not have 
# the same variance, so we well go with welch test instead
t_stat, p_value = stats.ttest_ind(album_1_data['rating'], album_2_data['rating'], equal_var=False) 
# H0 is that they have equal mean, so if p_value less < 0.01 we can say with 99% certienty
# that the means is significantly different
h0_holds = p_value > 0.05
if h0_holds:
    st.markdown("## We _:red[can not say]_ with more than :violet[95%] certainty that one album is better than the other!")
else:
    if album_1_metadata['rating'] == album_2_metadata['rating']:
        st.markdown("## We _:red[can not say]_ with more than :violet[95%] certainty that one album is better than the other!")
    elif album_1_metadata['rating'] > album_2_metadata['rating']:
        st.markdown(f"## We can be :green[95%] sure that :orange[{album_1_metadata['name']}] is better than :blue[{album_2_metadata['name']}]!")
    else:
        st.markdown(f"## We can be :green[95%] sure that :orange[{album_2_metadata['name']}] is better than :blue[{album_1_metadata['name']}]!")
with st.expander("Stats for nerds"):
    st.markdown("""
        During exploration I noticed that I could not assume that variance was equal between two groups of ratings, so I choose to go with the
        [Welch's t-test](https://en.wikipedia.org/wiki/Welch%27s_t-test) to determine if there was a statistically significant difference in the 
        mean ratings between the two albums.

        I choose a significance level of 95% simply on a hunch, it felt good enough.
    """)
    st.metric(label="P-value from Welch", value=p_value)
    st.metric(label="T-stat from Welch", value=t_stat)
st.divider()
combined_data_for_graphs = pd.concat([album_1_data, album_2_data])

histograms_fig = px.histogram(
    combined_data_for_graphs,
    x='rating',
    color='album_id',
    title="Number of votes for each rating",
    labels={
        'count': 'Number of votes',
        'rating': "Rating",
        'album_id': "Album"
    }
)
name_mapping = { album_1_metadata['album_id']: album_1_metadata['name'], album_2_metadata['album_id']: album_2_metadata['name']}
histograms_fig.for_each_trace(
    lambda t: t.update(name = name_mapping[t.name],
       legendgroup = name_mapping[t.name],
       hovertemplate = t.hovertemplate.replace(t.name, name_mapping[t.name])
   )
)
st.plotly_chart(histograms_fig, use_container_width=True)
st.divider()

mean_over_time = combined_data_for_graphs
mean_over_time['event_time'] = pd.to_datetime(mean_over_time['event_time'])
mean_over_time['date'] = mean_over_time['event_time'].dt.date
mean_over_time = mean_over_time.groupby(['date','album_id']).agg(rating_mean=('rating','mean')).reset_index()
mean_over_time_fig = px.line(
    mean_over_time,
    x='date',
    y='rating_mean',
    color='album_id',
    title="Mean rating over the course of the year",
    labels={
        'rating_mean': 'Rating (mean)',
        'date': "Date",
        'album_id': "Album"
    }
)
mean_over_time_fig.for_each_trace(
    lambda t: t.update(name = name_mapping[t.name],
       legendgroup = name_mapping[t.name],
       hovertemplate = t.hovertemplate.replace(t.name, name_mapping[t.name])
   )
)
st.plotly_chart(mean_over_time_fig, use_container_width=True)


