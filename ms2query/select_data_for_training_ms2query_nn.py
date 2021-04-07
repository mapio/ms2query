import pickle
from typing import List, Tuple, Union
import pandas as pd
from tqdm import tqdm
from matchms.typing import SpectrumType
from ms2query.app_helpers import load_pickled_file
from ms2query.ms2library import MS2Library
from ms2query.query_from_sqlite_database import \
    get_tanimoto_score_for_inchikey14s, get_metadata_from_sqlite
from ms2query.spectrum_processing import minimal_processing_multiple_spectra


class SelectDataForTraining(MS2Library):
    """Class to collect data needed to train a ms2query neural network"""
    def __init__(self,
                 sqlite_file_location: str,
                 s2v_model_file_name: str,
                 ms2ds_model_file_name: str,
                 pickled_s2v_embeddings_file_name: str,
                 pickled_ms2ds_embeddings_file_name: str,
                 training_spectra_file: str,
                 validation_spectra_file: str,
                 **settings):
        """Parameters
        ----------
        sqlite_file_location:
            The location at which the sqlite_file_is_stored. The file is
            expected to have 3 tables: tanimoto_scores, inchikeys and
            spectra_data.
        s2v_model_file_name:
            File location of a spec2vec model. In addition two more files in
            the same folder are expected with the same name but with extensions
            .trainables.syn1neg.npy and .wv.vectors.npy.
        ms2ds_model_file_name:
            File location of a trained ms2ds model.
        pickled_s2v_embeddings_file_name:
            File location of a pickled file with Spec2Vec embeddings in a
            pd.Dataframe with as index the spectrum id.
        pickled_ms2ds_embeddings_file_name:
            File location of a pickled file with ms2ds embeddings in a
            pd.Dataframe with as index the spectrum id.
        training_spectra_file:
            Pickled file with training spectra.
        validation_spectra_file:
            Pickled file with validation spectra.


        **settings:
            As additional parameters predefined settings can be changed.
        spectrum_id_column_name:
            The name of the column or key in dictionaries under which the
            spectrum id is stored. Default = "spectrumid"
        cosine_score_tolerance:
            Setting for calculating the cosine score. If two peaks fall within
            the cosine_score tolerance the peaks are considered a match.
            Default = 0.1
        base_nr_mass_similarity:
            The base nr used for normalizing the mass similarity. Default = 0.8
        max_parent_mass:
            The value used to normalize the parent mass by dividing it by the
            max_parent_mass. Default = 13428.370894192036
        progress_bars:
            If True progress bars will be shown. Default = True"""
        # pylint: disable=too-many-arguments
        super().__init__(sqlite_file_location,
                         s2v_model_file_name,
                         ms2ds_model_file_name,
                         pickled_s2v_embeddings_file_name,
                         pickled_ms2ds_embeddings_file_name,
                         **settings)
        self.training_spectra = minimal_processing_multiple_spectra(
            load_pickled_file(training_spectra_file))
        self.validation_spectra = minimal_processing_multiple_spectra(
            load_pickled_file(validation_spectra_file))

    def create_train_and_val_data(self,
                                  save_file_name: Union[None, str] = None
                                  ) -> Tuple[pd.DataFrame, pd.DataFrame,
                                             pd.DataFrame, pd.DataFrame]:
        """Creates the training and validation sets and labels

        The sets contain the top 20 ms2ds matches of each spectrum and a
        collection of different scores and data of these matches in a
        pd.DataFrame. The labels contain a dataframe with the tanimoto scores.
        Args
        ----
        save_file_name:
            File name to which the result will be stored. The result is stored
            as a pickled file of a tuple containing the training_set, the
            training_labels, the validation_set and the validation_labels in
            that order.
            """
        training_set, training_labels = \
            self.get_matches_info_and_tanimoto(self.training_spectra)
        validation_set, validation_labels = \
            self.get_matches_info_and_tanimoto(self.validation_spectra)

        if save_file_name:
            with open(save_file_name, "wb") \
                    as new_file:
                pickle.dump((training_set,
                             training_labels,
                             validation_set,
                             validation_labels), new_file)
        return training_set, training_labels, validation_set, validation_labels

    def get_matches_info_and_tanimoto(self,
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
            self.collect_matches_data_multiple_spectra(
                query_spectra)
        all_tanimoto_scores = pd.DataFrame()
        info_of_matches_with_tanimoto = pd.DataFrame()
        for query_spectrum in tqdm(query_spectra,
                                   desc="Get tanimoto scores",
                                   disable=not self.settings["progress_bars"]):
            query_spectrum_id = query_spectrum.get(
                self.settings["spectrum_id_column_name"])
            match_info_df = query_spectra_matches_info[query_spectrum_id]
            match_spectrum_ids = list(match_info_df.index)
            # Get tanimoto scores, spectra that do not have an inchikey are not
            # returned.
            tanimoto_scores_for_query_spectrum = \
                self.get_tanimoto_for_spectrum_ids(query_spectrum,
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
        # Converted to float32 since keras model cannot read float64
        return info_of_matches_with_tanimoto.astype("float32"), \
            all_tanimoto_scores.astype("float32")

    def get_tanimoto_for_spectrum_ids(self,
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
        query_inchikey14 = query_spectrum.get("inchikey")[:14]
        assert len(query_inchikey14) == 14, \
            f"Expected inchikey of length 14, " \
            f"got inchikey = {query_inchikey14}"

        # Get inchikeys belonging to spectra ids
        metadata_dict = get_metadata_from_sqlite(
            self.sqlite_file_location,
            spectra_ids_list,
            self.settings["spectrum_id_column_name"])
        unfiltered_inchikeys = [metadata_dict[spectrum_id]["inchikey"]
                                for spectrum_id in spectra_ids_list]

        inchikey14s_dict = {}
        for i, inchikey in enumerate(unfiltered_inchikeys):
            # Only get the first 14 characters of the inchikeys
            inchikey14 = inchikey[:14]
            spectrum_id = spectra_ids_list[i]
            # Don't save spectra that do not have an inchikey. If a spectra has
            # no inchikey it is stored as "", so it will not be stored.
            if len(inchikey14) == 14:
                inchikey14s_dict[spectrum_id] = inchikey14
        inchikey14s_list = list(inchikey14s_dict.values())
        # Returns tanimoto score for each unique inchikey14.
        tanimoto_scores_inchikey14s = get_tanimoto_score_for_inchikey14s(
            inchikey14s_list, [query_inchikey14], self.sqlite_file_location)
        # Add tanimoto scores to dataframe.
        tanimoto_scores_spectra_ids = pd.DataFrame(
            columns=["Tanimoto_score"],
            index=list(inchikey14s_dict.keys()))
        for spectrum_id in inchikey14s_dict:
            inchikey14 = inchikey14s_dict[spectrum_id]
            tanimoto_score = tanimoto_scores_inchikey14s.loc[inchikey14,
                                                             query_inchikey14]
            tanimoto_scores_spectra_ids.at[spectrum_id, "Tanimoto_score"] = \
                tanimoto_score
        return tanimoto_scores_spectra_ids
