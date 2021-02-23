"""
Choices made, different than joris method:
The test data set used bij Joris named nn_prep_training_found_matches_s2v_2dec.pickle
contains 2 sets of 2000 spectra the second set is testing data. This set
consists of 1000 spectra that have more than 4 inchikeys and 1000 spectra that
have only 1 inchikey. From this set a validation set is selected of 500 spectra.
To make sure this set is similar, 250 were taken from the first 1000 and 250
were taken from the second 1000. In the functions here this is not, the case,
since later sets will probably just have random spectra.

"""
import pickle
import os
from typing import List, Dict, Tuple
import numpy as np
import pandas as pd
from matchms.typing import SpectrumType
from tensorflow.keras.models import Sequential, load_model, Model
from tensorflow.keras.layers import Dense
from ms2query.app_helpers import load_pickled_file
from ms2query.ms2library import Ms2Library, get_spectra_from_sqlite
from ms2query.query_from_sqlite_database import \
    get_tanimoto_score_for_inchikeys, get_part_of_metadata_from_sqlite


class TrainImproveLibraryMatchingNN(Ms2Library):
    def __init__(self,
                 sqlite_file_location: str,
                 s2v_model_file_name: str,
                 ms2ds_model_file_name: str,
                 pickled_s2v_embeddings_file_name: str,
                 pickled_ms2ds_embeddings_file_name: str,
                 training_spectra_file_name: str,
                 **settings):

        self.training_spectra, test_and_val_spectra = \
            load_pickled_file(training_spectra_file_name)

        # Select random spectra for validation set.
        random_val_spectra_indexes = list(
            np.random.choice(range(0, len(test_and_val_spectra)),
                             500,
                             replace=False))
        self.test_spectra = [spectrum
                             for i, spectrum in enumerate(test_and_val_spectra)
                             if i not in random_val_spectra_indexes]
        self.validation_spectra = [spectrum for i, spectrum
                                   in enumerate(test_and_val_spectra)
                                   if i in random_val_spectra_indexes]

        self.training_spectra = self.training_spectra[:20]
        self.test_spectra = self.test_spectra[:15]
        self.validation_spectra = self.validation_spectra[:5]
        print("ingeladen")

        super().__init__(sqlite_file_location,
                         s2v_model_file_name,
                         ms2ds_model_file_name,
                         pickled_s2v_embeddings_file_name,
                         pickled_ms2ds_embeddings_file_name,
                         **settings)

    def train_network(self):
        self.get_matches_info_for_training(self.test_spectra[:2])

    def get_matches_info_for_training(self,
                                      query_spectra: List[SpectrumType]):
        """Returns tanimoto scores and info about matches of all query spectra

        A selection of matches is made for each query_spectrum. Based on the
        spectra multiple scores are calculated (info_of_matches_with_tanimoto)
        and the tanimoto scores based on the smiles is returned. All matches of
        all query_spectra are added together and the order of the tanimoto
        scores corresponds to the order of the info, so they can be used for
        training.

        Args:
        ------
        query_spectra:
            List of Spectrum objects
        """
        query_spectra_matches_info = \
            self.collect_matches_data_multiple_spectra(query_spectra)
        all_tanimoto_scores = pd.DataFrame()
        info_of_matches_with_tanimoto = pd.DataFrame()
        for query_spectrum in query_spectra:
            query_spectrum_id = query_spectrum.get("spectrum_id")
            match_info_df = query_spectra_matches_info[query_spectrum_id]
            match_spectrum_ids = list(match_info_df.index)
            # Get tanimoto scores, spectra that do not have an inchikey are not
            # returned.
            tanimoto_scores_for_query_spectrum = \
                get_tanimoto_for_spectrum_ids(self.sqlite_file_location,
                                              query_spectrum,
                                              match_spectrum_ids)
            all_tanimoto_scores = \
                all_tanimoto_scores.append(tanimoto_scores_for_query_spectrum,
                                           ignore_index=True)

            # Add matches for which a tanimoto score could be calculated
            matches_with_tanimoto = \
                match_info_df.loc[tanimoto_scores_for_query_spectrum.index]
            info_of_matches_with_tanimoto = \
                info_of_matches_with_tanimoto.append(matches_with_tanimoto,
                                                     ignore_index=True)
        return info_of_matches_with_tanimoto, all_tanimoto_scores


def get_tanimoto_for_spectrum_ids(sqlite_file_location: str,
                                  query_spectrum: SpectrumType,
                                  spectra_ids_list: List[str]
                                  ) -> pd.DataFrame:
    """Returns a dataframe with tanimoto scores

    Spectra in spectra_ids_list without inchikey are removed.
    Args:
    ------
    sqlite_file_location:
        location of sqlite file with spectrum info
    query_spectrum:
        Single Spectrum, the tanimoto scores are calculated between this
        spectrum and the spectra in match_spectrum_ids.
    match_spectrum_ids:
        list of spectrum_ids, which are preselected matches of the
        query_spectrum
    """
    query_inchikey = query_spectrum.get("inchikey")[:14]

    # Get inchikeys belonging to spectra ids
    unfiltered_inchikeys = get_part_of_metadata_from_sqlite(
        sqlite_file_location,
        spectra_ids_list,
        "inchikey")

    inchikeys_dict = {}
    for i, inchikey in enumerate(unfiltered_inchikeys):
        # Only get the first 14 characters of the inchikeys
        inchikey_14 = inchikey[:14]
        # Don't save spectra that do not have an inchikey. If a spectra has no
        # inchikey it is stored as "", so it will not be stored.
        spectrum_id = spectra_ids_list[i]
        if len(inchikey_14) == 14:
            inchikeys_dict[spectrum_id] = inchikey_14
    inchikeys_list = list(inchikeys_dict.values())
    # Returns tanimoto score for each unique inchikey.
    tanimoto_scores_inchikeys = get_tanimoto_score_for_inchikeys(
        inchikeys_list,
        [query_inchikey],
        sqlite_file_location)
    # Add tanimoto scores to dataframe.
    tanimoto_scores_spectra_ids = pd.DataFrame(columns=["Tanimoto_score"],
                                               index=list(inchikeys_dict.keys()))
    for spectrum_id in inchikeys_dict:
        inchikey = inchikeys_dict[spectrum_id]
        tanimoto_score = tanimoto_scores_inchikeys.loc[inchikey,
                                                       query_inchikey]
        tanimoto_scores_spectra_ids.at[spectrum_id,
                                       "Tanimoto_score"] = tanimoto_score
    return tanimoto_scores_spectra_ids


if __name__ == "__main__":
    sqlite_file_name = \
        "../downloads/data_all_inchikeys_with_tanimoto_and_parent_mass.sqlite"
    s2v_model_file_name = \
        "../downloads/" \
        "spec2vec_AllPositive_ratio05_filtered_201101_iter_15.model"
    s2v_pickled_embeddings_file = \
        "../downloads/embeddings_all_spectra.pickle"
    ms2ds_model_file_name = \
        "../../ms2deepscore/data/" \
        "ms2ds_siamese_210207_ALL_GNPS_positive_L1L2.hdf5"
    ms2ds_embeddings_file_name = \
        "../../ms2deepscore/data/ms2ds_embeddings_2_spectra.pickle"
    neural_network_model_file_location = \
        "../model/nn_2000_queries_trimming_simple_10.hdf5"
    training_spectra_file_name = \
        "../downloads/models/spec2vec_models/train_nn_model_data/test_and_validation_spectra_nn_model.pickle"
    # Create library object
    my_library = TrainImproveLibraryMatchingNN(
        sqlite_file_name,
        s2v_model_file_name,
        ms2ds_model_file_name,
        s2v_pickled_embeddings_file,
        ms2ds_embeddings_file_name,
        training_spectra_file_name)
    query_spectrum = get_spectra_from_sqlite(sqlite_file_name,
                                             ["CCMSLIB00000001552",
                                              "CCMSLIB00000001547"])
    print(my_library.get_matches_info_for_training(query_spectrum))

    # training_spectra_file_name = "../downloads/models/spec2vec_models/train_nn_model_data/test_and_validation_spectrum_docs_nn_model.pickle"
    # training_spectrum_docs, test_and_val_spectrum_docs = \
    #     load_pickled_file(training_spectra_file_name)
    #
    # training_spectra = [spectrum._obj for spectrum in
    #                          training_spectrum_docs]
    # test_and_val_spectra = [spectrum._obj for spectrum in
    #                         test_and_val_spectrum_docs]
    # with open("../downloads/models/spec2vec_models/train_nn_model_data/test_and_validation_spectra_nn_model.pickle", "wb") as new_file:
    #     pickle.dump((training_spectra, test_and_val_spectra), new_file)



    # sqlite_file_name = \
    #     "../downloads/data_all_inchikeys_with_tanimoto_and_parent_mass.sqlite"
    #
    # query_spectrum = get_spectra_from_sqlite(sqlite_file_name,
    #                                          ["CCMSLIB00000001552"])[0]
    # spectra_ids = ["CCMSLIB00000001547", "CCMSLIB00000001548",
    #                  "CCMSLIB00000001549","CCMSLIB00000001551"]
    # print(get_tanimoto_for_spectrum_ids(sqlite_file_name,
    #                                     query_spectrum,
    #                                     spectra_ids))
    pass