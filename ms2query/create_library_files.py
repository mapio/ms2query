from typing import List, Dict, Union
import pandas as pd
import os
from tqdm import tqdm
from matchms.Spectrum import Spectrum
from gensim.models import Word2Vec
from ms2deepscore import MS2DeepScore
from ms2deepscore.models import load_model as load_ms2ds_model
from spec2vec.vector_operations import calc_vector
from ms2query.create_sqlite_database import make_sqlfile_wrapper
from ms2query.spectrum_processing import minimal_processing_multiple_spectra, \
    create_spectrum_documents
from ms2query.app_helpers import load_pickled_file


class CreateFilesForLibrary:
    def __init__(self,
                 pickled_spectra_file_name: str,
                 **settings):
        """Creates files needed to run queries on a library

        Parameters
        ----------
        pickled_spectra_file_name:
            File name of a pickled file containing spectrum objects.

        **settings:
            The following optional parameters can be defined.
        new_sqlite_file_name:
            The file name of the new sqlite file that is created. As default
            the pickled_spectra_file_name is used and ".pickle" is removed and
            replaced with ".sqlite".
        new_ms2ds_embeddings_file_name:
            The file name of the file with ms2ds embeddings that is created.
            As default the pickled_spectra_file_name is used and ".pickle" is
            removed and replaced with "_ms2ds_embeddings.pickle".
        new_s2v_embeddings_file_name:
            The file name of the file with s2v embeddings. As default the
            pickled_spectra_file_name is used and ".pickle" is removed and
            replaced with "_s2v_embeddings.pickle".
        progress_bars:
            If True, a progress bar of the different processes is shown.
            Default = True.
        spectrum_id_column_name:
            The name of the column or key under which the spectrum id is
            stored. Default = "spectrumid"
        """
        self.settings = self._set_settings(settings, pickled_spectra_file_name)

        # Load in the spectra
        self.list_of_spectra = \
            self.load_spectra_and_minimal_processing(pickled_spectra_file_name)

    @staticmethod
    def _set_settings(new_settings: Dict[str, Union[str, bool]],
                      pickled_spectra_file_name: str
                      ) -> Dict[str, Union[str, bool]]:
        """Changes default settings to new_settings and creates file names

        Args:
        ------
        new_settings:
            Dictionary with settings that should be changed. Only the
            keys given in default_settings can be used and the type has to be
            the same as the type of the values in default settings.
        pickled_spectra_file_name:
            The name of a pickled spectra file name. Expected to end on
            '.pickle'. It is used to create 3 new file names, with different
            extensions.
        """
        default_settings = {"new_sqlite_file_name": "",
                            "new_ms2ds_embeddings_file_name": "",
                            "new_s2v_embeddings_file_name": "",
                            "progress_bars": True,
                            "spectrum_id_column_name": "spectrumid"}

        for attribute in new_settings:
            assert attribute in default_settings, \
                f"Invalid argument in constructor:{attribute}"
            assert isinstance(new_settings[attribute],
                              type(default_settings[attribute])), \
                f"Different type is expected for argument: {attribute}"
            default_settings[attribute] = new_settings[attribute]

        # Empty new file names are replaced with default file names.
        assert pickled_spectra_file_name[-7:] == ".pickle", \
            "Pickled_spectra_file_name is expected end on '.pickle'"
        base_file_name = pickled_spectra_file_name[:-7]
        if default_settings["new_sqlite_file_name"] == "":
            default_settings["new_sqlite_file_name"] = \
                pickled_spectra_file_name[:-7] + ".sqlite"
        if default_settings["new_ms2ds_embeddings_file_name"] == "":
            default_settings["new_ms2ds_embeddings_file_name"] = \
                base_file_name + "_ms2ds_embeddings.pickle"
        if default_settings["new_s2v_embeddings_file_name"] == "":
            default_settings["new_s2v_embeddings_file_name"] = \
                base_file_name + "_s2v_embeddings.pickle"

        return default_settings

    def load_spectra_and_minimal_processing(self,
                                            pickled_spectra_file_name: str
                                            ) -> List[Spectrum]:
        """Loads spectra from pickled file and does minimal processing

        Args
        ______
        pickled_spectra_file_name:
            The file name of a pickled file containing a list of spectra.
        """
        # Loads the spectra from a pickled file
        list_of_spectra = load_pickled_file(pickled_spectra_file_name)
        assert list_of_spectra[0].get(self.settings[
                                          "spectrum_id_column_name"]), \
            f"Expected spectra to have '" \
            f"{self.settings['spectrum_id_column_name']}' in " \
            f"metadata, to solve specify the correct spectrum_solumn_name"
        # Does normalization and filtering of spectra
        list_of_spectra = \
            minimal_processing_multiple_spectra(
                list_of_spectra,
                progress_bar=self.settings["progress_bars"])
        return list_of_spectra

    def create_all_library_files(self,
                                 tanimoto_scores_file_name: str,
                                 ms2ds_model_file_name: str,
                                 s2v_model_file_name: str,
                                 calculate_new_tanimoto_scores: bool = False):
        """Creates files with embeddings and a sqlite file with spectra data

        Args
        ------
        tanimoto_scores_file_name:
            File name of a pickled file containing a dataframe with tanimoto
            scores. If self.calculate_new_tanimoto_scores = True, this will
            be the file name of a new file in which the tanimoto scores will
            be stored.
        ms2ds_model_file_name:
            File name of a ms2ds model
        s2v_model_file_name:
            file name of a s2v model
        calculate_new_tanimoto_scores:
            If True new tanimoto scores will be calculated and stored in
            tanimoto_scores_file_name.
        """
        assert not os.path.exists(self.settings["new_sqlite_file_name"]), \
            "Given new_sqlite_file_name already exists"
        assert not os.path.exists(self.settings[
                                      'new_ms2ds_embeddings_file_name']), \
            "Given ms2ds_embeddings_file_name already exists"
        assert not os.path.exists(self.settings[
            "new_s2v_embeddings_file_name"]), \
            "Given s2v_embeddings_file_name already exists"

        if calculate_new_tanimoto_scores:
            assert not os.path.exists(tanimoto_scores_file_name),\
                "Tanimoto scores file already exists, " \
                "to use a file with already calculated tanimoto scores, " \
                "set calculate_new_tanimoto_scores to False"
            # Todo automatically create tanimoto scores

        make_sqlfile_wrapper(
            self.settings["new_sqlite_file_name"],
            tanimoto_scores_file_name,
            self.list_of_spectra,
            columns_dict={"parent_mass": "REAL"},
            progress_bars=self.settings["progress_bars"],
            spectrum_id_column_name=self.settings["spectrum_id_column_name"])

        self.store_s2v_embeddings(s2v_model_file_name)
        self.store_ms2ds_embeddings(ms2ds_model_file_name)

    def store_ms2ds_embeddings(self,
                               ms2ds_model_file_name):
        """Creates a pickled file with embeddings scores for spectra

        A dataframe with as index the spectrum_ids and as columns the indexes
        of the vector is converted to pickle.

        Args:
        ------
        spectrum_list:
            Spectra for which embeddings should be calculated.
        ms2ds_model_file_name:
            File name for a SiameseModel that is used to calculate the
            embeddings.
        new_pickled_embeddings_file_name:
            The file name in which the pickled dataframe is stored.
        """
        assert not os.path.exists(self.settings[
                                      'new_ms2ds_embeddings_file_name']), \
            "Given ms2ds_embeddings_file_name already exists"
        temporary_csv_file_name = "temporary_embeddings_file.csv"
        assert not os.path.exists(temporary_csv_file_name), \
            f"{temporary_csv_file_name} already exists"
        model = load_ms2ds_model(ms2ds_model_file_name)
        ms2ds = MS2DeepScore(model)

        for spectrum in tqdm(self.list_of_spectra,
                             desc="Calculating ms2ds embeddings",
                             disable=not self.settings["progress_bars"]):
            binned_spec = model.spectrum_binner.transform(
                [spectrum],
                progress_bar=False)[0]
            # pylint: disable=protected-access
            embedding = model.base.predict(
                ms2ds._create_input_vector(binned_spec))[0]
            spectrum_id = spectrum.get(self.settings[
                                           "spectrum_id_column_name"])
            embedding_df = pd.DataFrame([embedding], index=[spectrum_id])
            embedding_df.to_csv(temporary_csv_file_name,
                                index=True,
                                mode="a",
                                header=False)
        all_embeddings_df = pd.read_csv(temporary_csv_file_name,
                                        index_col=0,
                                        header=None,
                                        names=list(range(400)))
        all_embeddings_df.to_pickle(self.settings[
                                        'new_ms2ds_embeddings_file_name'])
        os.remove(temporary_csv_file_name)

    def store_s2v_embeddings(self, s2v_model_file_name):
        """Creates and stored a dataframe with embeddings as pickled file

        A dataframe with as index the spectrum_ids and as columns the indexes
        of the vector is converted to pickle.

        Args
        ------
        s2v_model_file_name:
            File name to load spec2vec model, 3 files are expected, with the
             extension .model, .model.trainables.syn1neg.npy and
             .model.wv.vectors.npy, together containing a Spec2Vec model,
        """
        assert not os.path.exists(self.settings[
            "new_s2v_embeddings_file_name"]), \
            "Given s2v_embeddings_file_name already exists"
        model = Word2Vec.load(s2v_model_file_name)
        # Convert Spectrum objects to SpectrumDocument
        spectrum_documents = create_spectrum_documents(
            self.list_of_spectra,
            progress_bar=self.settings["progress_bars"])
        embeddings_dict = {}
        for spectrum_document in tqdm(spectrum_documents,
                                      desc="Calculating embeddings",
                                      disable=not self.settings[
                                          "progress_bars"]):
            embedding = calc_vector(model,
                                    spectrum_document,
                                    allowed_missing_percentage=100)
            spectrum_id = spectrum_document.get(self.settings[
                                                    "spectrum_id_column_name"])
            embeddings_dict[spectrum_id] = embedding

        # Convert to pandas Dataframe
        embeddings_dataframe = pd.DataFrame.from_dict(embeddings_dict,
                                                      orient="index")
        embeddings_dataframe.to_pickle(self.settings[
            "new_s2v_embeddings_file_name"])
