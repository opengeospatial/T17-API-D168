import shutil
import sys

import pystac
import os
from argparse import Namespace, ArgumentParser
import urllib.request
from tempfile import TemporaryDirectory
import rasterio
from shapely.geometry import Polygon, mapping
from datetime import datetime
import json
import re
# Local repository, from https://github.com/geopython/pygeometa
from pygeometa.core import read_mcf, render_j2_template

import yaml
import logging


def get_bbox_and_footprint(raster_uri):
    with rasterio.open(raster_uri) as ds:
        bounds = ds.bounds
        bbox = [bounds.left, bounds.bottom, bounds.right, bounds.top]
        footprint = Polygon([
            [bounds.left, bounds.bottom],
            [bounds.left, bounds.top],
            [bounds.right, bounds.top],
            [bounds.right, bounds.bottom]
        ])

        return (bbox, mapping(footprint))


def pull_s3bucket(logger, tmp_dir, url, catalog_id, catalog_desc):
    img_path = os.path.join(tmp_dir.name, 'image.tif')

    urllib.request.urlretrieve(url, img_path)
    logger.debug(pystac.Catalog.__doc__)

    catalog = pystac.Catalog(id=catalog_id, description=catalog_desc)
    logger.debug(list(catalog.get_children()))
    logger.debug(list(catalog.get_items()))
    logger.debug(pystac.Item.__doc__)

    return img_path


def add_item(footprint, bbox, dateval, img_path, image_id):
    # Add item to catalog and apply timestamp
    item = pystac.Item(id=image_id,
                       geometry=footprint,
                       bbox=bbox,
                       datetime=dateval,
                       properties={})

    # Add image
    item.add_asset(
        key='image',
        asset=pystac.Asset(
            href=img_path,
            media_type=pystac.MediaType.GEOTIFF
        )
    )
    return item


def main(args: Namespace = None) -> int:
    if args is None:
        parser = ArgumentParser(
            description="Creates STAC Catalog",
            epilog="Should be run in the 'ogcapi' environment",
        )
        parser.add_argument(
            "-u",
            "--url",
            type=str,
            dest="url",
            help="Input url",
        )
        parser.add_argument(
            "-o",
            "--outdir",
            type=str,
            dest="outdir",
            help="Output data folder",
        )
        parser.add_argument(
            "-t",
            "--test",
            help="Run in test mode",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "-s",
            "--stac",
            help="Create STAC catalog",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "-v",
            "--verbose",
            help="Add extra information to logs.",
            action="store_true",
            default=False,
        )

    # define arguments
    args = parser.parse_args()

    # Start logging
    codedir, program = os.path.split(__file__)
    logger = logging.getLogger(program)
    logger.setLevel(logging.DEBUG if "verbose" in args and args.verbose else logging.INFO)

    # Configuration to be loaded from main directory
    if args.test:
        CONFIGURATION_FILE_PATH = os.path.join(codedir, "test-configuration.yaml")
    else:
        CONFIGURATION_FILE_PATH = os.path.join(codedir, "configuration.yaml")

    if not os.path.exists(CONFIGURATION_FILE_PATH):
        logger.info("Configuration file is missing")

    try:
        with open(CONFIGURATION_FILE_PATH, "r") as config_file:
            config = yaml.safe_load(config_file)
            url = config["url"]
            out_default = config["output_dir"]
            catalog_id = config["catalog_id"]
            catalog_desc = config["catalog_desc"]
            image_id = config["image_id"]
            yaml_file = config["yaml_file"]

            logging.debug("Configuration was loaded from '{}'.".format(CONFIGURATION_FILE_PATH))
    except Exception:
        logging.warning("Unable to load default configuration from '{}', relying on input variables.".format(CONFIGURATION_FILE_PATH))
        sys.exit(1)

    # Setup S3 bucket url
    if args.url:
        urlpath = (args.url)
    else:
        urlpath = (url)

    # Temp directory
    tmp_dir = TemporaryDirectory()

    # Setup output folder
    ofolder = "Folder-Not-Set"
    if args.outdir:
        ofolder = args.outdir
    #elif args.test:
    #    ofolder = tmp_dir
    #    print("Using temporary directory: {}".format(ofolder))
    else:
        ofolder = out_default

    if not os.path.exists(ofolder):
        if not os.path.islink(ofolder):
            print("Output folder {} does not exists".format(ofolder))
            sys.exit(1)

    # Version
    f = open('__init__.py', "r")
    version_file = f.read()
    version_line = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",version_file, re.M)
    logger.info("Running {}".format(version_line.group()))
    version = version_line.group().split("'")[1]

    # Create catalog sub_folder - delete if exists
    if args.stac:
        cat_folder = os.path.join(ofolder,catalog_id + "-stac-v" + version)
    else:
        cat_folder = os.path.join(ofolder,catalog_id + "-records-v" + version)

    if os.path.exists(cat_folder):
        shutil.rmtree(cat_folder)
    os.mkdir(cat_folder)

    if args.stac:
        logger.info("Creating STAC Catalog")
        # Create catalog
        catalog = pystac.Catalog(id=catalog_id, description=catalog_desc)

        # Get image and then extract information
        img_path = pull_s3bucket(logger, tmp_dir, urlpath, catalog_id, catalog_desc)
        bbox, footprint = get_bbox_and_footprint(img_path)
        logger.debug("Bounding box: {}".format(bbox))
        logger.debug("Footprint: {}".format(footprint))

        # Add item to catalog
        if args.test:
            dateval = datetime.utcnow()
        else:
            fdate = image_id.split("_")[0]
            dateval = datetime(int(fdate[0:4]),int(fdate[4:6]),int(fdate[6:8]),int(fdate[9:11]),int(fdate[11:13]),int(fdate[13:15]))
            logger.debug("Date of image: {}".format(dateval))

        item = add_item(footprint, bbox, dateval, url, image_id)
        catalog.add_item(item)

        # JSON dump item
        logger.debug(json.dumps(item.to_dict(), indent=4))

        # Set HREFs
        catalog.normalize_hrefs(cat_folder)
        # Save catalog
        catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)

        # Show catalog
        with open(catalog.get_self_href()) as f:
            print(f.read())
    else:
        logger.info("Creating Records Catalog")

        # YML contents
        #dict_file = [{'mcf' : ['version']},{'countries' : ['Pakistan', 'USA', 'India', 'China', 'Germany', 'France', 'Spain']}]

        #with open(out_yaml, 'w') as file:

        #    documents = yaml.dump(dict_file, file)

        # Read YML from disk
        mcf_dict = read_mcf(yaml_file)

        # Choose API Records output schema
        from pygeometa.schemas.ogc_api_records import OGCAPIRecordOutputSchema
        records_os = OGCAPIRecordOutputSchema()

        # Default schema
        xml_string = records_os.write(mcf_dict)
        print(xml_string)

        # Write to disk
        xml_file = os.path.join(cat_folder, os.path.basename(yaml_file.replace("yml","xml")))
        with open(xml_file, 'w') as ff:
                ff.write(xml_string)

    # Clean up
    tmp_dir.cleanup()

    logger.info("Processing completed successfully")


if __name__ == "__main__":
    exit(main())
