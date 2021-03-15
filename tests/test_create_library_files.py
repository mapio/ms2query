import os
import pytest
import pandas as pd
from ms2query.create_library_files import CreateFilesForLibrary
from ms2query.app_helpers import load_pickled_file
from ms2query.tests.sqlite_file import check_sqlite_files_are_equal


def test_set_settings_correct():
    """Tests if settings are set correctly"""
    path_to_general_test_files = os.path.join(
        os.path.split(os.path.dirname(__file__))[0],
        'tests/test_files/general_test_files')
    test_create_files = CreateFilesForLibrary(os.path.join(
        path_to_general_test_files, '100_test_spectra.pickle'),
        new_sqlite_file_name="test_sqlite_name", progress_bars=False)

    assert test_create_files.sqlite_file_name == "test_sqlite_name", \
        "Expected different sqlite_file_name"
    assert test_create_files.progress_bars is False, \
        "Expected different setting for progress_bar"
    assert test_create_files.spectrum_id_column_name == "spectrumid", \
        "Expected different spectrum_id_column_name"
    assert test_create_files.ms2ds_embeddings_file_name == os.path.join(
        path_to_general_test_files,
        "100_test_spectra_ms2ds_embeddings.pickle"), \
        "Expected different ms2ds_embeddings_file_name"
    assert test_create_files.s2v_embeddings_file_name == os.path.join(
        path_to_general_test_files,
        "100_test_spectra_s2v_embeddings.pickle"), \
        "Expected different s2v_embeddings_file_name"


def test_set_settings_wrong():
    """Tests if an error is raised if a wrong attribute is passed"""
    pickled_spectra_file_name = os.path.join(
        os.path.split(os.path.dirname(__file__))[0],
        'tests/test_files/test_files_ms2library/100_test_spectra.pickle')
    pytest.raises(AssertionError, CreateFilesForLibrary,
                  pickled_spectra_file_name,
                  not_recognized_attribute="test_value")


def test_create_all_library_files(tmp_path):
    """Tests create_all_library_files"""
    path_to_general_test_files = os.path.join(
        os.path.split(os.path.dirname(__file__))[0],
        'tests/test_files/general_test_files')
    ms2ds_embeddings_file = os.path.join(tmp_path, "ms2ds_embeddings")
    s2v_embeddings_file = os.path.join(tmp_path, "s2v_embeddings")
    sqlite_file = os.path.join(tmp_path, "sqlite")
    test_create_files = CreateFilesForLibrary(os.path.join(
        path_to_general_test_files, '100_test_spectra.pickle'),
        new_ms2ds_embeddings_file_name=ms2ds_embeddings_file,
        new_s2v_embeddings_file_name=s2v_embeddings_file,
        new_sqlite_file_name=sqlite_file)
    test_create_files.create_all_library_files(
        os.path.join(path_to_general_test_files,
                     '100_test_spectra_tanimoto_scores.pickle'),
        os.path.join(path_to_general_test_files,
                     'ms2ds_siamese_210301_5000_500_400.hdf5'),
        os.path.join(path_to_general_test_files,
                     '100_test_spectra_s2v_model.model'))
    assert os.path.isfile(ms2ds_embeddings_file), \
        "Expected ms2ds embeddings file to be created"
    assert os.path.isfile(s2v_embeddings_file), \
        "Expected s2v file to be created"
    assert os.path.isfile(sqlite_file), \
        "Expected sqlite file to be created"
    # Test if correct embeddings are stored
    ms2ds_embeddings = load_pickled_file(ms2ds_embeddings_file)
    s2v_embeddings = load_pickled_file(s2v_embeddings_file)
    expected_s2v_embeddings = load_pickled_file(os.path.join(
        path_to_general_test_files,
        "100_test_spectra_s2v_embeddings.pickle"))
    expected_ms2ds_embeddings = load_pickled_file(os.path.join(
        path_to_general_test_files,
        "100_test_spectra_ms2ds_embeddings.pickle"))
    pd.testing.assert_frame_equal(ms2ds_embeddings,
                                  expected_ms2ds_embeddings)
    pd.testing.assert_frame_equal(s2v_embeddings,
                                  expected_s2v_embeddings)
    # Check if sqlite file is stored correctly
    check_sqlite_files_are_equal(sqlite_file, os.path.join(
        path_to_general_test_files, "100_test_spectra.sqlite"))


def test_store_ms2ds_embeddings(tmp_path):
    """Tests store_ms2ds_embeddings"""
    path_to_general_test_files = os.path.join(
        os.path.split(os.path.dirname(__file__))[0],
        'tests/test_files/general_test_files')
    new_embeddings_file_name = os.path.join(tmp_path,
                                            "new_test_ms2ds_embeddings.pickle")
    test_create_files = CreateFilesForLibrary(os.path.join(
        path_to_general_test_files, '100_test_spectra.pickle'),
        new_ms2ds_embeddings_file_name=new_embeddings_file_name)
    test_create_files.store_ms2ds_embeddings(os.path.join(
        path_to_general_test_files,
        'ms2ds_siamese_210301_5000_500_400.hdf5'))
    assert os.path.isfile(new_embeddings_file_name), \
        "Expected file to be created"
    # Test if correct embeddings are stored
    embeddings = load_pickled_file(new_embeddings_file_name)
    expected_embeddings = load_pickled_file(os.path.join(
        path_to_general_test_files,
        "100_test_spectra_ms2ds_embeddings.pickle"))
    pd.testing.assert_frame_equal(embeddings, expected_embeddings)


def test_store_s2v_embeddings(tmp_path):
    """Tests store_ms2ds_embeddings"""
    path_to_general_test_files = os.path.join(
        os.path.split(os.path.dirname(__file__))[0],
        'tests/test_files/general_test_files')
    new_embeddings_file_name = os.path.join(tmp_path,
                                            "new_test_s2v_embeddings.pickle")
    test_create_files = CreateFilesForLibrary(os.path.join(
        path_to_general_test_files, '100_test_spectra.pickle'),
        new_s2v_embeddings_file_name=new_embeddings_file_name)
    test_create_files.store_s2v_embeddings(os.path.join(
        path_to_general_test_files,
        "100_test_spectra_s2v_model.model"))
    assert os.path.isfile(new_embeddings_file_name), \
        "Expected file to be created"
    embeddings = load_pickled_file(new_embeddings_file_name)
    expected_embeddings = load_pickled_file(os.path.join(
        path_to_general_test_files,
        "100_test_spectra_s2v_embeddings.pickle"))
    pd.testing.assert_frame_equal(embeddings, expected_embeddings)
