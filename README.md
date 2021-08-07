# ogcapi_testbed17_dataset_d168
OGC API Testbed 17 Dataset testing (D168)

## Install the ogcapi environment

`pip install -r requirements.txt`

or

`conda env create -f ogcapi_env.yml python=3.8`

### Setup pygeometa in develop mode so changes are accessed
`git clone https://github.com/pixalytics-ltd/pygeometa.git`

`cd pygeometa`

`python setup.py develop`

<b>Note:</b> pygeometa was updated to include a Record to describe a 'dataset', see https://github.com/cholmes/ogc-collection/blob/main/ogc-dataset-record-spec.md 


Notes:
#### Export environment

`conda env export > ogcapi_env.yml`