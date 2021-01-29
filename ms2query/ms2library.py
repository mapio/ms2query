from ms2query.query_from_sqlite_database import get_spectra_from_sqlite, \
    get_tanimoto_score_for_inchikeys
from typing import Optional, List, Dict, Union
from matchms.Spectrum import Spectrum
import pandas as pd
from ms2query.create_sqlite_database import make_sqlfile_wrapper


class Ms2Library:
    def __init__(self,
                 sqlite_file_location: Union[str, None],
                 file_name_dict: Optional[Dict[str, str]] = None):
        """

        Args:
        -------
        sqlite_file_location:
            The location at which the sqlite_file_is_stored. The file is
            expected to have 3 tables: tanimoto_scores, inchikeys and
            spectra_data. If no sqlite file is available paramater is expected
            to be None.
        file_name_dict:
            A dictionary containing the files needed to create a sql database.
            The dictionary is expected to contain the keys:
            "npy_file_location", "pickled_file_name" and "csv_file_name". With
            as value the location of these files.
            Default = None
        """
        if sqlite_file_location is not None:
            self.sqlite_file_location = sqlite_file_location
        elif file_name_dict is not None:
            self.sqlite_file_location = file_name_dict["new_sqlite_file_name"]
            self.make_sqlite_file(file_name_dict)
        else:
            print("sqlite_file_location and file_name_dict can't both be None")

    def make_sqlite_file(self, file_name_dict):
        """Creates a sqlite file with three tables"""
        npy_file_location = file_name_dict["npy_file_location"]
        pickled_file_name = file_name_dict["pickled_file_name"]
        csv_file_with_inchikey_order = file_name_dict["csv_file_name"]

        make_sqlfile_wrapper(self.sqlite_file_location,
                             npy_file_location,
                             pickled_file_name,
                             csv_file_with_inchikey_order)

    def get_spectra(self, spectrum_id_list: List[str]) -> List[Spectrum]:
        """Returns the spectra corresponding to the spectrum ids"""
        spectra_list = get_spectra_from_sqlite(self.sqlite_file_location,
                                               spectrum_id_list)
        return spectra_list

    def get_tanimoto_scores(self,
                            list_of_inchikeys: List[str]
                            ) -> pd.DataFrame:
        """Returns a panda dataframe with the tanimoto scores"""
        tanimoto_score_matrix = get_tanimoto_score_for_inchikeys(
            list_of_inchikeys,
            self.sqlite_file_location)
        return tanimoto_score_matrix

if __name__ == "__main__":
    my_library = Ms2Library(
        "../downloads/data_all_inchikeys_and_all_tanimoto_scores.sqlite")
    print(my_library.get_tanimoto_scores(["ARZWATDYIYAUTA", "QASOACWKTAXFSE"]))

    my_small_library = Ms2Library(
        None,
        {"new_sqlite_file_name": "small_sqlite_test_file.sqlite",
         "npy_file_location":
             "../tests/test_files_sqlite/test_tanimoto_scores.npy",
         "pickled_file_name":
             "../tests/test_files_sqlite/first_10_spectra.pickle",
         "csv_file_name":
             "../tests/test_files_sqlite/test_metadata_for_inchikey_order.csv"})

    print(my_small_library.get_tanimoto_scores(["MYHSVHWQEVDFQT",
                                                "BKAWJIRCKVUVED",
                                                "CXVGEDCSTKKODG"]))
    print(my_small_library.get_spectra(["CCMSLIB00000001547",
                                        "CCMSLIB00000001549"])[1].peaks.mz)
