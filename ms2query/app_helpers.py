import os
from typing import Tuple
import streamlit as st
from ms2query.utils import json_loader
from ms2query.s2v_functions import process_spectrums
from ms2query.s2v_functions import set_spec2vec_defaults


def gather_test_json(test_file_name: str) -> Tuple[dict, list]:
    """Return tuple of {test_file_name: full_path}, ['', test_file_name]

    test_file_name has to be in 'tests' folder

    Args:
    -------
    test_file_name:
        Name of the test file.
    """
    test_path = os.path.join(os.path.split(os.path.dirname(__file__))[0],
                             'tests', test_file_name)
    test_dict = {test_file_name: test_path}
    test_list = [''] + list(test_dict.keys())
    return test_dict, test_list


def get_query():
    """Gather all relevant query information and print info for query spectrum
    """
    # load query file in sidebar
    query_spectrums = []  # default so later code doesn't crash
    query_file = st.sidebar.file_uploader("Choose a query spectrum file...",
                                          type=['json', 'txt'])

    # gather default queries
    example_queries_dict, example_queries_list = gather_test_json(
        'testspectrum_query.json')
    query_example = st.sidebar.selectbox("Load a query spectrum example",
                                         example_queries_list)

    st.write("#### Query spectrum")
    if query_example and not query_file:
        st.write('You have selected an example query:', query_example)
        query_spectrums = json_loader(open(example_queries_dict[query_example]))
    elif query_file is not None:
        if query_file.name.endswith("json"):
            query_file.seek(0)  # fix for streamlit issue #2235
            query_spectrums = json_loader(query_file)

    # write query info
    if query_example or query_file:
        st.write("Your query spectrum id: {}".format(
            query_spectrums[0].metadata.get("spectrum_id")))
        with st.beta_expander("View additional query information"):
            fig = query_spectrums[0].plot()
            st.pyplot(fig)

    return query_spectrums


def get_library():
    library_spectrums = []  # default so later code doesn't crash
    library_file = st.sidebar.file_uploader("Choose a spectra library file...",
                                            type=['json', 'txt'])
    # gather default libraries
    example_libs_dict, example_libs_list = gather_test_json(
        'testspectrum_library.json')
    library_example = st.sidebar.selectbox("Load a library spectrum example",
                                           example_libs_list)
    st.write("#### Library spectra")
    if library_example and not library_file:
        st.write('You have selected an example library:', library_example)
        library_spectrums = json_loader(
            open(example_libs_dict[library_example]))
    elif library_file is not None:
        if library_file.name.endswith("json"):
            library_file.seek(0)  # fix for streamlit issue #2235
            library_spectrums = json_loader(library_file)

    # write library info
    if library_spectrums:
        st.write(f"Your library contains {len(library_spectrums)} spectra.")

    return library_spectrums


def do_spectrum_processing(query_spectrums, library_spectrums):
    st.write("""## Post-process spectra
    Spec2Vec similarity scores rely on creating a document vector for each
    spectrum. For the underlying word2vec model we want the documents
    (=spectra) to be more homogeneous in their number of unique words. Assuming
    that larger compounds will on average break down into a higher number of
    meaningful fragment peaks we reduce the document size of each spectrum
    according to its parent mass.
    """)
    # todo: we could add some buttons later to make this adjustable
    settings = set_spec2vec_defaults()
    with st.beta_expander("View processing defaults"):
        st.markdown(f"""* normalize peaks (maximum intensity to 1)\n* remove peaks 
        outside [{settings["mz_from"]}, {settings["mz_to"]}] m/z window\n* remove
        spectra with < {settings["n_required"]} peaks\n* reduce number of peaks to
        maximum of {settings["ratio_desired"]} * parent mass\n* remove peaks with
        intensities < {settings["intensity_from"]} of maximum intensity (unless
        this brings number of peaks to less than 10)\n* add losses between m/z
        value of [{settings["loss_mz_from"]}, {settings["loss_mz_to"]}]""")

    documents_query = process_spectrums(query_spectrums, **settings)
    documents_library = process_spectrums(library_spectrums, **settings)

    return documents_query, documents_library
