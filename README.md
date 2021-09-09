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

### Build catalog

Use `create_catalog.py` to create STAC or Records catalogs with the configuration stored in `test-configuration.yaml` alongside `eo4sas-record.yml` for a Record's catalog. The data referenced in these YAML files is stored in a publicly accessible AWS S3 bucket.

To create a STAC collection you would run:

`~/anaconda3/envs/ogcapi/bin/python create_catalog.py --collection`

If an output dierctory to store the catalog is not specified by --outdir then a folder specified in  will be created in `test-configuration.yaml` will be used. 

### Deploy catalog

Then, to upload to Elasticsearch run the following script with `es_upload_conf.yaml` defining what is uploaded:

`python upload_esearch.py --verbose --upload`

If you have problems connecting to Elasticsearch then use the diagnose option

`/home/seadas/anaconda3/envs/ogcapi/bin/python /upload_esearch.py --verbose --diagnose`

An example configuration files is provide as
`deploy_catalog/[example]es_upload_conf.yaml` that needs to be renamed to `deploy_catalog/es_upload_conf.yaml` and edited with the details of your Elasticsearch instance

### utils

Utilities used to support file conversion from GeoTiFF to COG or NetCDF.

