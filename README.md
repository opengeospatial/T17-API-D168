# ogcapi_testbed17_dataset_d168
OGC API Testbed 17 Dataset testing (D168)

## Install the ogcapi environment

`pip install -r requirements.txt`

or

`conda env create -f ogcapi_env.yml python=3.8`

## Clone this repository
`git clone https://github.com/opengeospatial/T17-API-D168.git`

## Clone and setup pygeometa - use forked version with updated for OGC API Records catalog creation
`git clone https://github.com/pixalytics-ltd/pygeometa/tree/t17-rcatalog`

`cd pygeometa`

`python setup.py build`

`python setup.py install`

## Final Steps
Create link in the main folder of theis repository to pygeometa/pygeometa 
