# ogcapi_testbed17_dataset_d168
OGC API Testbed 17 Dataset testing (D168)

## Install the ogcapi environment

`conda env create -f environment.yml python=3.9`

The environment will not be activated, so to activate run:

`conda activate ogcapi`

<b>Note:</b> Must install elasticsearch version 7.13.4 as release 7.14.0 no longer supports an AWS hosted instance

### Install pystac schemas

Install pystac with the validation optional requirements (e.g. pip install pystac[validation]) as these schemas are used

### Install pygeometa from the Pixalytics repository, so the updates implemented for this activity are accessed

`python -m pip install git+https://github.com/pixalytics-ltd/pygeometa.git@t17-rcatalog`

OR if you want to further edit the code, setup pygeometa in develop mode 

`git clone https://github.com/pixalytics-ltd/pygeometa.git`

`cd pygeometa`

`python setup.py develop`

<b>Note:</b> pygeometa was updated to include a Record to describe a 'dataset', see https://github.com/cholmes/ogc-collection/blob/main/ogc-dataset-record-spec.md 

### Clone this repository

`git clone https://github.com/opengeospatial/T17-API-D168.git`

`cd T17-API-D168`

There will be a soft link to pygeometa under build catalog, so adjust that link if the location of that repository is different 

## Code folders

### build catalog

Use `create_catalog.py` to create STAC or Records catalogs, e.g. to create a STAC collection with the configuration stored in :

`~/anaconda3/envs/ogcapi/bin/python create_catalog.py --collection`

### deploy catalog

Then, to upload to Elasticsearch run the following script with es_upload_conf.yaml defining what is uploaded:

`python upload_esearch.py --verbose --upload`

If you have problems connecting to Elasticsearch then use the diagnose option

`/home/seadas/anaconda3/envs/ogcapi/bin/python /upload_esearch.py --verbose --diagnose`

An example configuration files is provide as
deploy_catalog/[example]es_upload_conf.yaml that needs to be renamed to deploy_catalog/es_upload_conf.yaml and edited with the details of your Elasticsearch instance

### utils

Utilities used to support file conversion.

