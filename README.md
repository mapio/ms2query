![GitHub Workflow Status](https://img.shields.io/github/workflow/status/iomega/ms2query/CI%20Build)
![GitHub](https://img.shields.io/github/license/iomega/ms2query)
[![PyPI](https://img.shields.io/pypi/v/ms2query)](https://pypi.org/project/ms2query/)
[![fair-software.eu](https://img.shields.io/badge/fair--software.eu-%E2%97%8F%20%20%E2%97%8F%20%20%E2%97%8F%20%20%E2%97%8F%20%20%E2%97%8B-yellow)](https://fair-software.eu)

<img src="https://github.com/iomega/ms2query/blob/main/images/ms2query_logo.svg" width="280">

### MS2Query - machine learning assisted library querying of MS/MS spectra.
MS2Query is a tool for fast library searching for both analogs and true matches.

## Documentation for users
### Prepare environmnent
We recommend to create an Anaconda environment with

```
conda create --name ms2query python=3.8
conda activate ms2query
```
### Pip install MS2Query
MS2Query can simply be installed by running:
```
pip install ms2query
```

### Run MS2Query
Below an example script is given.
This script will first download files for a default MS2Query library.
This default library is trained on the GNPS library of 2021-04-09.

After downloading it runs a search on 
```python
import os
from ms2query.run_ms2query import automatically_download_models
from ms2query.run_ms2query import default_library_file_names
from ms2query.run_ms2query import run_complete_folder
from ms2query.run_ms2query import create_default_library_object

# Set the location where all your downloaded model files are stored
ms2query_library_files_directory = "./ms2query_library_files"

# Downloads pretrained models and files for MS2Query (>10GB download)
automatically_download_models(ms2query_library_files_directory, default_library_file_names())

# Create a MS2Library object 
ms2library = create_default_library_object(
    ms2query_library_files_directory, default_library_file_names())


# define the folder in which your spectra are stored.
# Accepted formats are: "mzML", "json", "mgf", "msp", "mzxml", "usi" or a pickled matchms object. 
ms2_spectra_directory = "specify_directory"
folder_to_store_results = os.path.join(ms2_spectra_directory, "results")

# Run library search and analog search on your files. 
# The results are stored in the specified folder_to_store_results.
run_complete_folder(ms2library, ms2_spectra_directory, folder_to_store_results)

```
## Documentation for developers
### Prepare environmnent
We recommend to create an Anaconda environment with

```
conda create --name ms2query python=3.7
conda activate ms2query
```
### Clone repository
Clone the present repository, e.g. by running
```
git clone https://github.com/iomega/ms2query.git
```
And then install the required dependencies, e.g. by running the following from within the cloned directory
```
pip install -e .
```
To run all unit tests, to check if everything was installed successfully run: 
```
pytest
```

## Contributing

If you want to contribute to the development of ms2query,
have a look at the [contribution guidelines](CONTRIBUTING.md).

## License

Copyright (c) 2021, Netherlands eScience Center

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
