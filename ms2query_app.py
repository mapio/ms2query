import os
import pandas as pd
import streamlit as st
from ms2query.networking import do_networking
from ms2query.app_helpers import get_query
from ms2query.app_helpers import get_library
from ms2query.app_helpers import get_model
from ms2query.app_helpers import do_spectrum_processing
from ms2query.app_helpers import get_example_library_matches
from ms2query.app_helpers import get_library_matches


st.title("Ms2query")
st.write("""
Upload your query and library spectra files in json format in the sidebar.
Query the library using a Spec2Vec model and inspect the results! 
""")
st.write("## Input information")
input_warning_placeholder = st.empty()  # input warning for later

# load query spectrum
query_spectrums = get_query()
# load library file in sidebar
library_spectrums = get_library()

# load a s2v model in sidebar
# todo: make more user friendly, currently there is no standard func to do this
# for quick testing C:\Users\joris\Documents\eScience_data\data\trained_models\spec2vec_library_testing_4000removed_2dec.model
model, model_num = get_model()

# write an input warning
if not query_spectrums or not library_spectrums or not model:
    input_warning_placeholder.markdown("""<p><span style="color:red">Please
    upload a query, library and model file in the sidebar.</span></p>""",
                                       unsafe_allow_html=True)

# processing of query and library spectra into SpectrumDocuments
documents_query, documents_library = do_spectrum_processing(query_spectrums,
                                                            library_spectrums)

# do library matching
st.write("## Library matching")
# load example library matching (test query on test library)
get_example_library_matches()

# library matching function
do_library_matching = st.checkbox("Do library matching")
if do_library_matching:
    if all([documents_query, documents_library, model]):
        found_match = get_library_matches(documents_query, documents_library,
                                          model, model_num)
    else:
        do_library_matching = False
        st.write("""<p><span style="color:red">Please specify input files.
        </span></p>""", unsafe_allow_html=True)

# do networking
# for now load example similarity matrix
path_dir = os.path.dirname(__file__)
test_sim_matrix_file = os.path.join(path_dir, "tests", "test_found_matches_" +
                                    "similarity_matrix.csv")
test_sim_matrix = pd.read_csv(test_sim_matrix_file, index_col=0)
st.write("## Networking")
plot_true = st.checkbox("Plot network of found matches")
if plot_true and do_library_matching:
    plot_placeholder = st.empty()  # add a place for the plot
    # add sliders to adjust network plot
    col1, col2 = st.beta_columns(2)
    with col1:
        st.write("Restrict library matches")
        attr_key = st.selectbox("Choose parameter", found_match.columns,
                                index=0)
        attr_data = found_match[attr_key]
        if isinstance(attr_data.iloc[0], float):
            # true for s2v, cosine etc
            min_v, max_v, step, val = (0., 1., 0.05, 0.4)
        elif max(attr_data) >= 1:
            # true for parentmass, cosine matches etc
            min_v, max_v, step, val = (0, max(attr_data), 1, 1)
        attr_cutoff = st.slider(attr_key + " cutoff", min_value=min_v,
                                max_value=max_v, step=step, value=val)
    with col2:
        st.write("Restrict library connections")
        tanimoto_cutoff = st.slider("Tanimoto cutoff", min_value=0.,
                                    max_value=1., step=0.05, value=0.6)

    network_plot = do_networking("query", found_match, test_sim_matrix,
                                 documents_library, attribute_key=attr_key,
                                 cutoff=attr_cutoff,
                                 tan_cutoff=tanimoto_cutoff)
    if network_plot:
        plot_placeholder.plotly_chart(network_plot)
elif plot_true:  # library matching is not done yet, but plot button is clicked
    st.write("""<p><span style="color:red">Please specify input files and do
            library matching.</span></p>""", unsafe_allow_html=True)
