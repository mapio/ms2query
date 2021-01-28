import os
import pandas as pd
from matchms import Spectrum
from ms2query.app_helpers import load_pickled_file
from ms2query.create_sqlite_database import make_sqlfile_wrapper
from ms2query.query_from_sqlite_database import \
    get_tanimoto_score_for_inchikeys, get_spectra_from_sqlite


def test_sqlite_functions(tmp_path):
    """Tests create_sqlite_database.py and query_from_sqlite_database.py
    """

    sqlite_file_name = os.path.join(tmp_path, "test_spectra_database.sqlite")

    # Create path so it also works for automatic testing
    path_to_test_files_sqlite_dir = os.path.join(
        os.path.split(os.path.dirname(__file__))[0],
        'tests/test_files_sqlite')
    # Create sqlite file, with 3 tables
    make_sqlfile_wrapper(sqlite_file_name,
                         os.path.join(path_to_test_files_sqlite_dir,
                                      "test_tanimoto_scores.npy"),
                         os.path.join(path_to_test_files_sqlite_dir,
                                      "first_10_spectra.pickle"),
                         os.path.join(path_to_test_files_sqlite_dir,
                                      "test_metadata_for_inchikey_order.csv"))

    # Test if file is made
    assert os.path.isfile(sqlite_file_name), "Expected a file to be created"

    tanimoto_score_dataframe = get_tanimoto_score_for_inchikeys(
        ['MYHSVHWQEVDFQT',
         'BKAWJIRCKVUVED',
         'CXVGEDCSTKKODG'],
        sqlite_file_name)

    # The matrix in the testfile: [[1.0, 0.068, 0.106],
    #                              [0.068, 1.0, 0.045],
    #                              [0.106, 0.045, 1.0]])

    assert isinstance(tanimoto_score_dataframe, pd.DataFrame)
    assert tanimoto_score_dataframe['MYHSVHWQEVDFQT']['MYHSVHWQEVDFQT'] == \
           1.0, "Expected different value in dataframe"
    assert tanimoto_score_dataframe['BKAWJIRCKVUVED']['MYHSVHWQEVDFQT'] == \
           0.068, "Expected different value in dataframe"
    assert tanimoto_score_dataframe['CXVGEDCSTKKODG']['MYHSVHWQEVDFQT'] == \
           0.106, "Expected different value in dataframe"
    assert tanimoto_score_dataframe['BKAWJIRCKVUVED']['BKAWJIRCKVUVED'] == \
           1.0, "Expected different value in dataframe"
    assert tanimoto_score_dataframe['CXVGEDCSTKKODG']['BKAWJIRCKVUVED'] == \
           0.045, "Expected different value in dataframe"
    assert tanimoto_score_dataframe['CXVGEDCSTKKODG']['CXVGEDCSTKKODG'] == \
           1.0, "Expected different value in dataframe"

    spectra_id_list = ['CCMSLIB00000001547', 'CCMSLIB00000001549']
    spectra_list = get_spectra_from_sqlite(sqlite_file_name, spectra_id_list)

    # Test if the output is of the right type
    assert isinstance(spectra_list, list), "Expected a list"
    assert isinstance(spectra_list[0], Spectrum), \
        "Expected a list with matchms.Spectrum.Spectrum objects"

    # Test if the right number of spectra are returned
    assert len(spectra_list) == 2, "Expected only 2 spectra"

    # Test if the correct spectra are loaded
    pickled_file_name = os.path.join(path_to_test_files_sqlite_dir,
                                     "first_10_spectra.pickle")
    original_spectra = load_pickled_file(pickled_file_name)
    assert original_spectra[0].__eq__(spectra_list[0]), \
        "expected different spectrum"
    assert original_spectra[2].__eq__(spectra_list[1]), \
        "expected different spectrum"

    print(tanimoto_score_dataframe)
    print(spectra_list)


if __name__ == "__main__":
    # # To manually run the test
    # test_sqlite_functions("")
    #
    # # To test large file:
    #
    # # Create new sql file with all the large datasets
    # new_sqlite_file_name = \
    #     "../downloads/data_all_inchikeys_and_all_tanimoto_scores.sqlite"
    # make_sqlfile_wrapper(
    #     new_sqlite_file_name,
    #     "../downloads/similarities_AllInchikeys14_daylight2048_jaccard.npy",
    #     "../downloads/" +
    #     "gnps_positive_ionmode_cleaned_by_matchms_and_lookups.pickle",
    #     "../downloads/metadata_AllInchikeys14.csv")
    #
    # # Loading tanimoto scores took 770 s (12800 inchikeys)
    # # Loading spectrum data took less than a minute
    #
    # spectra = get_spectra_from_sqlite(new_sqlite_file_name,
    #                                   ["CCMSLIB00000001547",
    #                                    "CCMSLIB00000001548"])
    # # Takes 0.0025 s
    #
    # print(spectra[0].metadata)
    # print(spectra)
    #
    # print(get_tanimoto_score_for_inchikeys(['MYHSVHWQEVDFQT',
    #                                         'HYTGGNIMZXFORS',
    #                                         'JAMSDVDUWQNQFZ',
    #                                         'QASOACWKTAXFSE',
    #                                         'MZWQZYDNVSKPPF',
    #                                         'abc'],
    #                                        new_sqlite_file_name))
    # # Takes 0.025 seconds
    pass
