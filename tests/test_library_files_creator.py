import os
import pytest
import pandas as pd
from .test_sqlite import check_sqlite_files_are_equal
from ms2query.library_files_creator import LibraryFilesCreator
from ms2query.app_helpers import load_pickled_file


@pytest.fixture
def path_to_general_test_files() -> str:
    return os.path.join(
        os.path.split(os.path.dirname(__file__))[0],
        'tests/test_files/general_test_files')


def test_set_settings_correct(path_to_general_test_files):
    """Tests if settings are set correctly"""
    test_create_files = LibraryFilesCreator(os.path.join(
        path_to_general_test_files, '100_test_spectra.pickle'),
        output_file_sqlite="test_output_name.sqlite",
        progress_bars=False)

    assert test_create_files.settings["output_file_sqlite"] == \
           "test_output_name.sqlite", "Expected different output_file_sqlite"
    assert test_create_files.settings["progress_bars"] is False, \
        "Expected different setting for progress_bar"
    assert test_create_files.settings["spectrum_id_column_name"] == \
           "spectrumid", "Expected different spectrum_id_column_name"
    assert test_create_files.settings["ms2ds_embeddings_file_name"] == \
           "test_output_name_ms2ds_embeddings.pickle", \
           "Expected different ms2ds_embeddings_file_name"
    assert test_create_files.settings["s2v_embeddings_file_name"] == \
           "test_output_name_s2v_embeddings.pickle", \
           "Expected different s2v_embeddings_file_name"


def test_set_settings_wrong():
    """Tests if an error is raised if a wrong attribute is passed"""
    pickled_spectra_file_name = os.path.join(
        os.path.split(os.path.dirname(__file__))[0],
        'tests/test_files/test_files_ms2library/100_test_spectra.pickle')
    pytest.raises(AssertionError, LibraryFilesCreator,
                  pickled_spectra_file_name, "output_filename.sqlite",
                  not_recognized_attribute="test_value")


def test_create_all_library_files(tmp_path, path_to_general_test_files):
    """Tests create_all_library_files"""
    ms2ds_embeddings_file = os.path.join(tmp_path, "ms2ds_embeddings")
    s2v_embeddings_file = os.path.join(tmp_path, "s2v_embeddings")
    sqlite_file = os.path.join(tmp_path, '100_test_spectra.sqlite')
    test_create_files = LibraryFilesCreator(os.path.join(
        path_to_general_test_files, '100_test_spectra.pickle'),
        sqlite_file,
        ms2ds_embeddings_file_name=ms2ds_embeddings_file,
        s2v_embeddings_file_name=s2v_embeddings_file)
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


def test_store_ms2ds_embeddings(tmp_path, path_to_general_test_files):
    """Tests store_ms2ds_embeddings"""
    new_embeddings_file_name = os.path.join(tmp_path,
                                            "new_test_ms2ds_embeddings.pickle")
    test_create_files = LibraryFilesCreator(os.path.join(
        path_to_general_test_files, '100_test_spectra.pickle'),
        os.path.join(path_to_general_test_files, '100_test_spectra.sqlite'),
        ms2ds_embeddings_file_name=new_embeddings_file_name)
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


def test_store_s2v_embeddings(tmp_path, path_to_general_test_files):
    """Tests store_ms2ds_embeddings"""
    new_embeddings_file_name = os.path.join(tmp_path,
                                            "new_test_s2v_embeddings.pickle")
    test_create_files = LibraryFilesCreator(os.path.join(
        path_to_general_test_files, '100_test_spectra.pickle'),
        os.path.join(path_to_general_test_files, '100_test_spectra.sqlite'),
        s2v_embeddings_file_name=new_embeddings_file_name)
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
