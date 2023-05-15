import math
import os
import numpy as np
import pandas as pd
import pytest
from matchms import Spectrum
from pandas.testing import assert_series_equal
from ms2query.ms2library import (MS2Library,
                                 create_library_object_from_one_dir,
                                 get_ms2query_model_prediction_single_spectrum)
from ms2query.results_table import ResultsTable
from ms2query.utils import load_ms2query_model, load_pickled_file, SettingsRunMS2Query
from ms2query.query_from_sqlite_database import SqliteLibrary
from tests.fixtures import sqlite_library
from tests.test_utils import check_correct_results_csv_file


@pytest.fixture
def ms2library() -> MS2Library:
    """Returns file names of the files needed to create MS2Library object"""
    path_to_tests_dir = os.path.join(
        os.path.split(os.path.dirname(__file__))[0],
        'tests/test_files/')
    sqlite_file_loc = os.path.join(
        path_to_tests_dir,
        "general_test_files/100_test_spectra.sqlite")
    spec2vec_model_file_loc = os.path.join(
        path_to_tests_dir,
        "general_test_files/100_test_spectra_s2v_model.model")
    s2v_pickled_embeddings_file = os.path.join(
        path_to_tests_dir,
        "general_test_files/100_test_spectra_s2v_embeddings.pickle")
    ms2ds_model_file_name = os.path.join(
        path_to_tests_dir,
        "general_test_files/ms2ds_siamese_210301_5000_500_400.hdf5")
    ms2ds_embeddings_file_name = os.path.join(
        path_to_tests_dir,
        "general_test_files/100_test_spectra_ms2ds_embeddings.pickle")
    spectrum_id_column_name = "spectrumid"
    ms2q_model_file_name = os.path.join(path_to_tests_dir,
        "general_test_files", "test_ms2q_rf_model.onnx")
    ms2library = MS2Library(sqlite_file_loc, spec2vec_model_file_loc, ms2ds_model_file_name,
                            s2v_pickled_embeddings_file, ms2ds_embeddings_file_name, ms2q_model_file_name,
                            spectrum_id_column_name=spectrum_id_column_name)
    return ms2library


@pytest.fixture
def test_spectra():
    """Returns a list with two spectra

    The spectra are created by using peaks from the first two spectra in
    100_test_spectra.pickle, to make sure that the peaks occur in the s2v
    model. The other values are random.
    """
    spectrum1 = Spectrum(mz=np.array([808.27356, 872.289917, 890.246277,
                                      891.272888, 894.326416, 904.195679,
                                      905.224548, 908.183472, 922.178101,
                                      923.155762], dtype="float"),
                         intensities=np.array([0.11106008, 0.12347332,
                                               0.16352988, 0.17101522,
                                               0.17312992, 0.19262333,
                                               0.21442898, 0.42173288,
                                               0.51071955, 1.],
                                              dtype="float"),
                         metadata={'pepmass': (907.0, None),
                                   'spectrumid': 'CCMSLIB00000001760',
                                   'precursor_mz': 907.0,
                                   # 'precursor_mz': 905.9927235480093,
                                   'inchikey': 'SCYRNRIZFGMUSB-STOGWRBBSA-N',
                                   'charge': 1})
    spectrum2 = Spectrum(mz=np.array([538.003174, 539.217773, 556.030396,
                                      599.352783, 851.380859, 852.370605,
                                      909.424438, 953.396606, 963.686768,
                                      964.524658
                                      ],
                                     dtype="float"),
                         intensities=np.array([0.28046377, 0.28900242,
                                               0.31933114, 0.32199162,
                                               0.34214536, 0.35616456,
                                               0.36216307, 0.41616014,
                                               0.71323034, 1.],
                                              dtype="float"),
                         metadata={'pepmass': (928.0, None),
                                   'spectrumid': 'CCMSLIB00000001761',
                                   'precursor_mz': 928.0,
                                   # 'precursor_mz': 905.010782,
                                   'inchikey': 'SCYRNRIZFGMUSB-STOGWRBBSA-N',
                                   # 'charge': 1
                                   })
    return [spectrum1, spectrum2]


@pytest.fixture
def expected_ms2deespcore_scores():
    ms2dscores:pd.DataFrame = load_pickled_file(os.path.join(
        os.path.split(os.path.dirname(__file__))[0],
        'tests/test_files/test_files_ms2library/expected_ms2ds_scores.pickle'))
    return ms2dscores


def test_ms2library_set_settings(ms2library):
    """Tests creating a ms2library object"""

    assert ms2library.settings["spectrum_id_column_name"] == "spectrumid", \
        "Different value for attribute was expected"
    assert ms2library.settings["progress_bars"] == True, \
        "Different value for attribute was expected"


def test_analog_search_no_ms2ds(ms2library, test_spectra):
    """Check if no ms2deepscores are stored."""
    cutoff = 20
    results_without_ms2deepscores = ms2library.analog_search_return_results_tables(
        test_spectra, cutoff, store_ms2deepscore_scores=False)
    for i in range(len(results_without_ms2deepscores)):
        assert results_without_ms2deepscores[i].ms2deepscores.empty, \
            "No ms2deepscores should be stored in the result table"


def test_get_all_ms2ds_scores(ms2library, test_spectra, expected_ms2deespcore_scores):
    """Test get_all_ms2ds_scores method of ms2library"""
    result = ms2library._get_all_ms2ds_scores(test_spectra[0])
    assert_series_equal(result, expected_ms2deespcore_scores)


def test_get_s2v_scores(ms2library, test_spectra):
    """Test _get_s2v_scores method of MS2Library"""
    result = ms2library._get_s2v_scores(
        test_spectra[0], [18, 68])
    assert np.allclose(result, np.array([0.97565603, 0.97848464])), \
        "Expected different Spec2Vec scores"


def test_get_average_ms2ds_for_inchikey14(ms2library):
    inchickey14s = {"BKUKTJSDOUXYFL", "BTVYFIMKUHNOBZ"}
    ms2ds_scores = pd.Series(
        [0.1, 0.8, 0.3],
        index=[87, 71, 73])
    results = ms2library._get_average_ms2ds_for_inchikey14(
        ms2ds_scores, inchickey14s)
    assert results == \
           {'BKUKTJSDOUXYFL': 0.1, 'BTVYFIMKUHNOBZ': 0.55}, \
           "Expected different results"


def test_get_chemical_neighbourhood_scores(ms2library):
    average_inchickey_scores = \
        {'BKUKTJSDOUXYFL': 0.8,
         'UZMVEOVJASEKLP': 0.8,
         'QWSYKJZSJYRUSS': 0.8,
         'GRVRRAOIXXYICO': 0.8,
         'WXDBUBIFYCCNLE': 0.8,
         'ORRFIXSGNXBETO': 0.7,
         'LLWMPGSQZXZZAE': 0.7,
         'CTBBEXWJRAPJIZ': 0.6,
         'YQLQWGVOWKPLFR': 0.6,
         'BTVYFIMKUHNOBZ': 0.6}

    results = ms2library._calculate_average_multiple_library_structures({"BKUKTJSDOUXYFL"}, average_inchickey_scores)
    assert isinstance(results, dict), "expected a dictionary"
    assert len(results) == 1, "Expected different number of results in " \
                              "dictionary"
    assert 'BKUKTJSDOUXYFL' in results
    scores = results['BKUKTJSDOUXYFL']
    assert isinstance(scores, tuple)
    assert len(scores) == 2, "Expected two scores for each InChiKey"
    assert math.isclose(scores[0], 0.72)
    assert math.isclose(scores[1], 0.4607757103045708)


def test_analog_search_store_in_csv(ms2library, test_spectra, tmp_path):
    results_csv_file = os.path.join(tmp_path, "test_csv_analog_search")
    settings = SettingsRunMS2Query(additional_metadata_columns=(("spectrumid", )))
    ms2library.analog_search_store_in_csv(test_spectra, results_csv_file, settings)
    assert os.path.exists(results_csv_file)
    expected_headers = \
        ['query_spectrum_nr', "ms2query_model_prediction", "precursor_mz_difference", "precursor_mz_query_spectrum",
         "precursor_mz_analog", "inchikey", "analog_compound_name", "smiles", "spectrumid"]
    check_correct_results_csv_file(
        pd.read_csv(results_csv_file),
        expected_headers)


def test_create_library_object_from_one_dir():
    """Test creating a MS2Library object with create_library_object_from_one_dir"""
    path_to_tests_dir = os.path.join(
        os.path.split(os.path.dirname(__file__))[0],
        'tests/test_files/general_test_files')
    library = create_library_object_from_one_dir(path_to_tests_dir)
    assert isinstance(library, MS2Library)


if __name__ == "__main__":
    pass
