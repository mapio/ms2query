from typing import List, Dict, Union, Tuple
import pandas as pd
import numpy as np
from tqdm import tqdm
from heapq import nlargest
from tensorflow.keras.models import load_model as load_nn_model
from gensim.models import Word2Vec
from matchms.Spectrum import Spectrum
from ms2deepscore.models import load_model as load_ms2ds_model
from ms2deepscore import MS2DeepScore
from spec2vec.vector_operations import cosine_similarity_matrix, calc_vector
from ms2query.query_from_sqlite_database import get_parent_mass_within_range, \
    get_parent_mass, get_inchikey_information
from ms2query.app_helpers import load_pickled_file
from ms2query.spectrum_processing import create_spectrum_documents


class MS2Library:
    """Calculates scores of spectra in library and selects best matches"""
    def __init__(self,
                 sqlite_file_location: str,
                 s2v_model_file_name: str,
                 ms2ds_model_file_name: str,
                 pickled_s2v_embeddings_file_name: str,
                 pickled_ms2ds_embeddings_file_name: str,
                 **settings):
        """
        Parameters
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
            If True progress bars will be shown of all methods. Default = True
        """
        # pylint: disable=too-many-arguments
        # todo create a ms2query model class that stores the model but also the
        #  settings used, since the settings used should always be the same as
        #  when the model was trained

        # Change default settings to values given in **settings
        self.settings = self._set_settings(settings)

        # Load models and set sqlite_file_location
        self.sqlite_file_location = sqlite_file_location
        self.s2v_model = Word2Vec.load(s2v_model_file_name)
        self.ms2ds_model = load_ms2ds_model(ms2ds_model_file_name)

        # loads the library embeddings into memory
        self.s2v_embeddings: pd.DataFrame = load_pickled_file(
            pickled_s2v_embeddings_file_name)
        self.ms2ds_embeddings: pd.DataFrame = load_pickled_file(
            pickled_ms2ds_embeddings_file_name)

    @staticmethod
    def _set_settings(new_settings: Dict[str, Union[str, bool]],
                      ) -> Dict[str, Union[str, float]]:
        """Changes default settings to new_settings

        Args:
        ------
        new_settings:
            Dictionary with settings that should be changed. Only the
            keys given in default_settings can be used and the type has to be
            the same as the type of the values in default settings.
        """
        # Set default settings
        default_settings = {"spectrum_id_column_name": "spectrumid",
                            "cosine_score_tolerance": 0.1,
                            "base_nr_mass_similarity": 0.8,
                            "progress_bars": True}
        # todo make new model that has a fixed basic mass
        for attribute in new_settings:
            assert attribute in default_settings, \
                f"Invalid argument in constructor:{attribute}"
            assert isinstance(new_settings[attribute],
                              type(default_settings[attribute])), \
                f"Different type is expected for argument: {attribute}"
            default_settings[attribute] = new_settings[attribute]
        return default_settings

    def select_best_matches(self,
                            query_spectra: List[Spectrum],
                            ms2query_model_file_name: str,
                            preselection_cut_off: int = 2000
                            ) -> Dict[str, pd.DataFrame]:
        """Returns ordered best matches with info for all query spectra

        Args
        ----
        query_spectra:
            List of query spectra for which the best matches should be found
        ms2query_model_file_name:
            File name of a hdf5 file containing the ms2query model.
        preselection_cut_off:
            The number of spectra with the highest ms2ds that should be
            selected. Default = 2000
        """
        # Selects top 20 best matches based on ms2ds and calculates all scores
        preselected_matches_info = \
            self.collect_matches_data_multiple_spectra(query_spectra,
                                                       preselection_cut_off)
        # Adds the ms2query model prediction to the dataframes
        preselected_matches_with_prediction = \
            get_ms2query_model_prediction(preselected_matches_info,
                                               ms2query_model_file_name)
        # todo decide for a good filtering method e.g. below certain threshold
        return preselected_matches_with_prediction

    def collect_matches_data_multiple_spectra(self,
                                              query_spectra: List[Spectrum],
                                              preselection_cut_off: int
                                              ) -> Dict[str, pd.DataFrame]:
        """Returns a dataframe with info for all matches to all query spectra

        This is stored in a dictionary with as keys the spectrum_ids and as
        values a pd.Dataframe with on each row the information for one spectrum
        that was found in the preselection. The column names tell the info that
        is stored. Which column names/info is stored can be found in
        collect_data_for_tanimoto_prediction_model.

        Args:
        ------
        query_spectra:
            The spectra for which info about matches should be collected
        preselection_cut_off:
            The number of spectra with the highest ms2ds that should be
            selected
        """
        ms2ds_scores = self._get_all_ms2ds_scores(query_spectra)

        spectra_belonging_to_inchikey14s, closely_related_inchikey14s = \
            get_inchikey_information(self.sqlite_file_location)

        inchikeys_belonging_to_spectra = {}
        for inchikey, list_of_spectrum_ids in spectra_belonging_to_inchikey14s.items():
            for spectrum_id in list_of_spectrum_ids:
                inchikeys_belonging_to_spectra[spectrum_id] = inchikey

        all_parent_masses = get_parent_mass(
            self.sqlite_file_location,
            self.settings["spectrum_id_column_name"])

        # Run neural network model over all found spectra and add the predicted
        # scores to a dict with the spectra in dataframes
        dict_with_preselected_spectra_info = {}
        for query_spectrum in tqdm(query_spectra,
                                   desc="collecting matches info",
                                   disable=not self.settings["progress_bars"]):
            spectrum_id = query_spectrum.get(
                self.settings["spectrum_id_column_name"])
            query_spectrum_parent_mass = query_spectrum.get("parent_mass")

            selected_spectrum_ids, average_ms2ds_scores, \
                related_inchikey_scores = \
                self.calculate_averages_and_preselection(
                    ms2ds_scores[spectrum_id],
                    preselection_cut_off,
                    spectra_belonging_to_inchikey14s,
                    closely_related_inchikey14s)

            s2v_scores = self.get_s2v_scores(query_spectrum,
                                             selected_spectrum_ids)

            dict_with_preselected_spectra_info[spectrum_id] = \
                self.select_and_normalize_scores_for_selected_spectra(
                    selected_spectrum_ids,
                    ms2ds_scores[spectrum_id],
                    s2v_scores,
                    inchikeys_belonging_to_spectra,
                    related_inchikey_scores,
                    average_ms2ds_scores,
                    all_parent_masses,
                    query_spectrum_parent_mass)

        return dict_with_preselected_spectra_info

    def select_potential_true_matches(self,
                                      query_spectra: List[Spectrum],
                                      mass_tolerance: Union[float, int] = 0.1,
                                      s2v_score_threshold: float = 0.6
                                      ) -> Dict[str, List[str]]:
        found_matches_dict = {}
        for query_spectrum in tqdm(query_spectra,
                                   desc="Selecting potential perfect matches",
                                   disable=not self.settings["progress_bars"]):
            query_parent_mass = query_spectrum.get("parent_mass")
            query_spectrum_id = query_spectrum.get(
                self.settings["spectrum_id_column_name"])
            parent_masses_within_mass_tolerance = get_parent_mass_within_range(
                self.sqlite_file_location,
                query_parent_mass-mass_tolerance,
                query_parent_mass+mass_tolerance,
                self.settings["spectrum_id_column_name"])
            selected_library_spectra = [result[0] for result in
                                        parent_masses_within_mass_tolerance]
            s2v_scores = self.get_s2v_scores(query_spectrum,
                                             selected_library_spectra)
            found_matches = []
            for i in range(len(selected_library_spectra)):
                if s2v_scores[i] > s2v_score_threshold:
                    found_matches.append(selected_library_spectra[i])
            found_matches_dict[query_spectrum_id] = found_matches
        return found_matches_dict

    def _get_all_ms2ds_scores(self, query_spectra: List[Spectrum]
                              ) -> pd.DataFrame:
        """Returns a dataframe with the ms2deepscore similarity scores

        The similarity scores are calculated between the query_spectra and all
        library spectra.

        query_spectra
            Spectra for which similarity scores should be calculated for all
            spectra in the ms2ds embeddings file.
        """
        ms2ds = MS2DeepScore(self.ms2ds_model, progress_bar=False)
        query_embeddings = ms2ds.calculate_vectors(query_spectra)
        library_ms2ds_embeddings_numpy = self.ms2ds_embeddings.to_numpy()
        ms2ds_scores = cosine_similarity_matrix(library_ms2ds_embeddings_numpy,
                                                query_embeddings)
        similarity_matrix_dataframe = pd.DataFrame(
            ms2ds_scores,
            index=self.ms2ds_embeddings.index,
            columns=[query_spectrum.get(
                self.settings["spectrum_id_column_name"])
                for query_spectrum in query_spectra])
        return similarity_matrix_dataframe

    def calculate_averages_and_preselection(
            self,
            ms2ds_scores: pd.DataFrame,
            preselection_cut_off: int,
            spectra_belonging_to_inchikey14s,
            closely_related_inchikey14s,
            sort_on_average_ms2ds: bool = False
            ):
        """Returns dataframe with relevant info for ms2query nn model

        query_spectrum:
            Spectrum for which all relevant data is collected
        preselected_spectrum_ids:
            List of spectrum ids that have the highest ms2ds scores with the
            query_spectrum
        """
        # pylint: disable=too-many-locals
        average_ms2ds_scores = \
            get_average_ms2ds_for_inchikey14(ms2ds_scores,
                                             spectra_belonging_to_inchikey14s)

        if sort_on_average_ms2ds:
            # select on highest ms2ds score
            selected_inchikeys, selected_spectrum_ids = \
                preselect_best_matching_inchikeys(
                    average_ms2ds_scores,
                    spectra_belonging_to_inchikey14s,
                    preselection_cut_off)
        else:
            # Select inchikeys and spectrums based on the highest average
            # ms2ds scores
            selected_spectrum_ids = list(ms2ds_scores.nlargest(
                preselection_cut_off).index)

            selected_inchikeys = average_ms2ds_scores

        related_inchikey_scores = get_closely_related_scores(
            selected_inchikeys,
            closely_related_inchikey14s,
            average_ms2ds_scores)
        return selected_spectrum_ids, average_ms2ds_scores, \
            related_inchikey_scores

    def select_and_normalize_scores_for_selected_spectra(self,
            selected_spectra: List[Spectrum],
            ms2ds_scores,
            s2v_scores,
            inchikey14s_corresponding_to_spectrum_ids,
            related_inchikey_score_dict,
            average_ms2ds_scores,
            all_parent_masses,
            query_spectrum_parent_mass) -> pd.DataFrame:
        """Returns list of scores for the selected spectra


        Args:
        -----
        selected_spectra:
        inchikey14s_corresponding_to_spectrum_ids:
        related_inchikey_score_dict:
        average_ms2ds_scores:
        """
        selected_and_normalized_scores = \
            {"parent_mass_divided_by_1000": [],
             "mass_similarity": [],
             "s2v_score": s2v_scores,
             "ms2ds_score": [],
             "average_ms2ds_score_for_inchikey14": [],
             "nr_of_spectra_with_same_inchikey14_divided_by_100": [],
             "average_ms2ds_score_for_closely_related_inchikey14s": [],
             "average_tanimoto_score_used_for_closely_related_score": [],
             "nr_of_spectra_for_closely_related_score_divided_by_100": []}
        for spectrum_id in selected_spectra:
            selected_and_normalized_scores["ms2ds_score"].append(
                ms2ds_scores.loc[spectrum_id])

            matching_inchikey14 = \
                inchikey14s_corresponding_to_spectrum_ids[spectrum_id]
            selected_and_normalized_scores[
                "average_ms2ds_score_for_closely_related_inchikey14s"].append(
                related_inchikey_score_dict[matching_inchikey14][0])
            # Devide by 100 for normalization
            selected_and_normalized_scores[
                "nr_of_spectra_for_closely_related_score_divided_by_100"].append(
                related_inchikey_score_dict[matching_inchikey14][1] / 100)
            selected_and_normalized_scores[
                "average_tanimoto_score_used_for_closely_related_score"].append(
                related_inchikey_score_dict[matching_inchikey14][2])

            matching_inchikey14 = \
                inchikey14s_corresponding_to_spectrum_ids[spectrum_id]
            selected_and_normalized_scores[
                "average_ms2ds_score_for_inchikey14"].append(
                average_ms2ds_scores[matching_inchikey14][0])
            selected_and_normalized_scores[
                "nr_of_spectra_with_same_inchikey14_divided_by_100"].append(
                average_ms2ds_scores[matching_inchikey14][1] / 100)

            selected_and_normalized_scores[
                "parent_mass_divided_by_1000"].append(
                all_parent_masses[spectrum_id] / 1000)
            selected_and_normalized_scores["mass_similarity"].append(
                self.settings["base_nr_mass_similarity"] **
                abs(all_parent_masses[spectrum_id] -
                    query_spectrum_parent_mass))
        return pd.DataFrame(selected_and_normalized_scores,
                            index=selected_spectra)

    def get_s2v_scores(self,
                       query_spectrum: Spectrum,
                       preselection_of_library_ids: List[str]
                       ) -> np.ndarray:
        """Returns the s2v scores

        query_spectrum:
            Spectrum object
        preselection_of_library_ids:
            list of spectrum ids for which the s2v scores should be calcualated
            """
        query_spectrum_document = \
            create_spectrum_documents([query_spectrum])[0]
        query_s2v_embedding = calc_vector(self.s2v_model,
                                          query_spectrum_document,
                                          allowed_missing_percentage=100)
        preselected_s2v_embeddings = \
            self.s2v_embeddings.loc[preselection_of_library_ids].to_numpy()
        s2v_scores = cosine_similarity_matrix(np.array([query_s2v_embedding]),
                                              preselected_s2v_embeddings)[0]
        return s2v_scores


def get_average_ms2ds_for_inchikey14(ms2ds_scores: pd.DataFrame,
                                     spectra_belonging_to_inchikey14s):

    inchikey14_scores = {}
    for inchikey14 in spectra_belonging_to_inchikey14s:
        sum_of_ms2ds_scores = 0
        for spectrum_id in spectra_belonging_to_inchikey14s[inchikey14]:
            sum_of_ms2ds_scores += ms2ds_scores.loc[spectrum_id]
        nr_of_spectra = len(spectra_belonging_to_inchikey14s[inchikey14])
        if nr_of_spectra > 0:
            avg_ms2ds_score = sum_of_ms2ds_scores / nr_of_spectra
            inchikey14_scores[inchikey14] = (avg_ms2ds_score, nr_of_spectra)
    return inchikey14_scores


def preselect_best_matching_inchikeys(average_ms2ds_scores_per_inchikey14,
                                      spectra_belonging_to_inchikey,
                                      top_nr_of_inchikeys):
    top_inchikeys = nlargest(top_nr_of_inchikeys,
                             average_ms2ds_scores_per_inchikey14,
                             key=average_ms2ds_scores_per_inchikey14.get)
    top_spectrum_ids = []
    top_inchikeys_with_scores = {}
    for inchikey in top_inchikeys:
        top_spectrum_ids += spectra_belonging_to_inchikey[inchikey]
        top_inchikeys_with_scores[inchikey] = average_ms2ds_scores_per_inchikey14[inchikey]
    return top_inchikeys_with_scores, top_spectrum_ids


def get_closely_related_scores(
        selected_inchikey14s,
        closest_related_inchikey14s: Dict[str, List[Tuple[str, float]]],
        average_inchikey_scores: Dict[str, Tuple[float, int]]
        ) -> Dict[str, Tuple[float, int, float]]:
    """Returns the related inchikey scores for the selected inchikeys

    Args:
    ------
    selected_inchikey14s:


    average_inchikey_score:
        Dictionary containing the average MS2Deepscore scores for each inchikey
        and the number of spectra belonging to this inchikey.
    """

    related_inchikey_score_dict = {}
    for inchikey in selected_inchikey14s:
        # For each inchikey a list with the top 10 closest related inchikeys
        #  and the corresponding tanimoto score is stored
        best_matches_and_tanimoto_scores = \
            closest_related_inchikey14s[inchikey]

        # Count the weight, nr and sum of tanimoto scores to calculate the
        #  average tanimoto score.
        sum_related_inchikey_tanimoto_scores = 0
        total_weight_of_spectra_used = 0
        total_nr_of_spectra_used = 0
        for closely_related_inchikey14, tanimoto_score in \
                best_matches_and_tanimoto_scores:
            # Get the ms2ds score for this closely related inchikey14 and the
            # nr of spectra for this related inchikey.
            closely_related_ms2ds, nr_of_spectra_related_inchikey14 = \
                average_inchikey_scores[closely_related_inchikey14]
            # todo think of different weighting based on tanimoto score,
            #  e.g. nr_of_spectra^tanimoto_score or return all individual
            #  scores, nr and tanimoto score for each closely related inchikey
            #  (so 30 in total) to MS2Query
            # The weight of closely related spectra is based on the tanimoto
            # score and the nr of spectra this inchikey has.
            weight_of_closely_related_inchikey_score = \
                nr_of_spectra_related_inchikey14 * tanimoto_score

            sum_related_inchikey_tanimoto_scores += \
                closely_related_ms2ds * \
                weight_of_closely_related_inchikey_score
            total_weight_of_spectra_used += \
                weight_of_closely_related_inchikey_score
            total_nr_of_spectra_used += nr_of_spectra_related_inchikey14

        average_tanimoto_score_used = \
            total_weight_of_spectra_used/total_nr_of_spectra_used

        related_inchikey_score_dict[
            inchikey] = \
            (sum_related_inchikey_tanimoto_scores/total_weight_of_spectra_used,
             total_nr_of_spectra_used,
             average_tanimoto_score_used)
    return related_inchikey_score_dict


def get_ms2query_model_prediction(
        matches_info: Dict[str, Union[pd.DataFrame, None]],
        ms2query_model_file_name: str
        ) -> Dict[str, pd.DataFrame]:
    """Adds ms2query predictions to dataframes

    matches_info:
        A dictionary with as keys the query spectrum ids and as values
        pd.DataFrames containing the top 20 preselected matches and all
        info needed about these matches to run the ms2query model.
    ms2query_model_file_name:
        File name of a hdf5 name containing the ms2query model.
    """
    ms2query_nn_model = load_nn_model(ms2query_model_file_name)

    for query_spectrum_id in matches_info:
        current_query_matches_info = matches_info[query_spectrum_id]
        if current_query_matches_info is None:
            continue
        predictions = ms2query_nn_model.predict(current_query_matches_info)

        # Add prediction to dataframe
        current_query_matches_info[
            "ms2query_model_prediction"] = predictions
        matches_info[query_spectrum_id] = \
            current_query_matches_info.sort_values(
                by=["ms2query_model_prediction"], ascending=False)
    return matches_info
