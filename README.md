# ogcapi_testbed17_dataset_d168
OGC API Testbed 17 Dataset testing (D168)

## Install the ogcapi environment

`pip install -r requirements.txt`

or

`conda env create -f ogcapi_env.yml python=3.8`

### Setup pygeometa
`git clone https://github.com/geopython/pygeometa.git`

`cd pygeometa`

`python setup.py build`

`python setup.py install`


Notes:
#### Export environment

`conda env export > ogcapi_env.yml`