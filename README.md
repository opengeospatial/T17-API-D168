# OGC API Testbed 17 Dataset testing (D168)

## Installing the ogcapi conda environment

`conda env create -f environment.yml python=3.9`

The environment will not be activated, so to activate run:

`conda activate ogcapi`

<b>Note:</b> If using AWS for Elasticsearch, then you will need to install elasticsearch version 7.13.4 as release 7.14.0 no longer supports an AWS hosted Elasticsearch instance (now called Amazon OpenSearch)

### Install pystac schemas

Install pystac with the validation optional requirement (e.g. pip install pystac[validation]) as these schemas are used

### Install pygeometa from the Pixalytics repository, so the updates implemented for this activity are accessible

`python -m pip install git+https://github.com/pixalytics-ltd/pygeometa.git@t17-rcatalog`

OR if you want to further edit the code, setup pygeometa in develop mode: 

`git clone https://github.com/pixalytics-ltd/pygeometa.git`

`cd pygeometa`

`python setup.py develop`

<b>Note:</b> pygeometa was updated to include a Record to describe a 'dataset', see https://github.com/cholmes/ogc-collection/blob/main/ogc-dataset-record-spec.md 

## Clone this repository

`git clone https://github.com/opengeospatial/T17-API-D168.git`

`cd T17-API-D168`

There will be a soft link to pygeometa under build catalog, so adjust that link if the location of that repository is different 

## Code folders

### Build catalog

Use `create_catalog.py` to create STAC or Records catalogs with the configuration stored in `test-configuration.yaml` alongside `eo4sas-record.yml` for a Record's catalog. The data referenced in these YAML files is stored in a publicly accessible AWS S3 bucket.

For example, to create a STAC collection run:

`~/anaconda3/envs/ogcapi/bin/python create_catalog.py --collection`

If an output directory to store the catalog is not specified by --outdir then the folder specified in `test-configuration.yaml` will be used. 

### Deploy catalog

Then, tupload the catlog to an Elasticsearch instance and run the following script with `es_upload_conf.yaml` to define what is uploaded:

`python upload_esearch.py --verbose --upload`

If you have problems connecting to Elasticsearch then use the diagnose option:

`~/anaconda3/envs/ogcapi/bin/python /upload_esearch.py --verbose --diagnose`

<b>Note:</b> An example configuration files is provide as
`deploy_catalog/[example]es_upload_conf.yaml` that needs to be renamed to `deploy_catalog/es_upload_conf.yaml` and edited with the details of your Elasticsearch instance.

### utils

Utilities used to support file conversion from GeoTiFF to COG or NetCDF.

## Example outputs

### Static deployment via AWS S3 bucket

These are version 0-8 catalogs with multiple objects. A public access S3 bucket has been set up, and contains both the catalogs and imagery:

* STAC collection catalog v0-8 created using pystac for GeoTiFFs:
  * main JSON: https://pixalytics-ogc-api.s3.eu-west-2.amazonaws.com/eo4sas-catalog-stac-v0-8/collection.json
  * image JSONs, e.g. https://pixalytics-ogc-api.s3.eu-west-2.amazonaws.com/eo4sas-catalog-stac-v0-8/20200831T101156_rgb_classification/20200831T101156_rgb_classification.json

* STAC collection catalog v0-8 created using pystac for NetCDFs:
  * main JSON: https://pixalytics-ogc-api.s3.eu-west-2.amazonaws.com/eo4sas-catalog-stac-nc-v0-8/collection.json

* OGC API Records catalog v0-8 created using pygeometa for GeoTiFFs:
  * main JSON: https://pixalytics-ogc-api.s3.eu-west-2.amazonaws.com/eo4sas-catalog-records-v0-8/catalog.json
  * image JSONs e.g.: https://pixalytics-ogc-api.s3.eu-west-2.amazonaws.com/eo4sas-catalog-records-v0-8/eo4sas-record1.json

* OGC API Records catalog v0-8 created using pygeometa for NetCDFs:
  * main JSON: https://pixalytics-ogc-api.s3.eu-west-2.amazonaws.com/eo4sas-catalog-records-nc-v0-8/catalog.json

### Dynamic catalogs deployed using the D165 server

D165 server has its own GitHub repository at https://github.com/opengeospatial/T17-API-D165

OGC API - Features server with three catalogs (Cubewerx alongside Elasticsearch versions of Records and STAC GeoTiFF catalogs):
* http://ogcapi.pixalytics.com:8080/

OGI API - EDR implementation with a single multi time-step NetCDF:
* http://ogcapiedr.pixalytics.com:8080/
