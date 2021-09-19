import shutil
import sys

# pystac 1.1.0 installed
import pystac
from pystac.extensions.projection import ProjectionExtension
import os
from argparse import Namespace, ArgumentParser
import urllib.request
from tempfile import TemporaryDirectory
import rasterio
from rasterio.warp import transform_bounds
from shapely.geometry import Polygon, mapping
from datetime import datetime
import json
import ast
import re
# Pixalytics version of repository, from https://github.com/geopython/pygeometa
from pygeometa.core import read_mcf, render_j2_template
from pygeometa.schemas.ogc_api_dataset_record import OGCAPIDRecordOutputSchema
from pygeometa.schemas.ogc_api_records import OGCAPIRecordOutputSchema

import yaml
import logging

# Need to transform to EPSG4326 as other projections not allowed by GeoJSON format
def get_bbox_and_footprint(logger, raster_uri):
    dst_crs = 'EPSG:4326'
    with rasterio.open(raster_uri) as src:
        logger.debug("Source map projection: {}".format(src.crs))
        if src.crs == dst_crs:
            bounds = src.bounds

            bbox = [bounds.left, bounds.bottom, bounds.right, bounds.top]
            footprint = Polygon([
                [bounds.left, bounds.bottom],
                [bounds.left, bounds.top],
                [bounds.right, bounds.top],
                [bounds.right, bounds.bottom]
            ])
            logger.debug("Bounds: {}".format(bounds))

        else:
            # Transform to Lat & Lon
            bounds = transform_bounds(src.crs, dst_crs, *src.bounds)
            logger.debug("Transformed Bounds: {}".format(bounds))

            bbox = [bounds[0], bounds[1], bounds[2], bounds[3]]
            footprint = Polygon([
                [bounds[0], bounds[1]],
                [bounds[2], bounds[1]],
                [bounds[2], bounds[3]],
                [bounds[0], bounds[3]]
            ])

        return bbox, mapping(footprint), str(src.crs), dst_crs


def pull_s3bucket(logger, tmp_dir, url, catalog_id, catalog_desc):
    img_path = os.path.join(tmp_dir.name, 'image.tif')

    try:
        urllib.request.urlretrieve(url, img_path)
    except:
        logger.warning("Failed to retrieve {}".format(url))
        sys.exit(1)
    logger.debug(pystac.Catalog.__doc__)

    catalog = pystac.Catalog(id=catalog_id, description=catalog_desc)
    logger.debug(list(catalog.get_children()))
    logger.debug(list(catalog.get_items()))
    logger.debug(pystac.Item.__doc__)

    return img_path


def add_item(footprint, bbox, epsg, gsd, img_path, image_id):

    fdate = image_id.split("_")[0]
    dateval = datetime(int(fdate[0:4]), int(fdate[4:6]), int(fdate[6:8]), int(fdate[9:11]), int(fdate[11:13]),
                       int(fdate[13:15]))

    # Add item to catalog and apply timestamp
    item = pystac.Item(id=image_id.split(".")[0],
                       geometry=footprint,
                       bbox=bbox,
                       datetime=dateval,
                       properties={})

    # Add common metadata
    item.common_metadata.gsd = float(gsd)

    # Add projection metadata
    ProjectionExtension.add_to(item)
    proj_ext = ProjectionExtension.ext(item)
    print(item.stac_extensions)
    proj_ext.epsg = int(epsg)

    # Add image
    item.add_asset(
        key='image',
        asset=pystac.Asset(
            href=img_path+image_id,
            media_type=pystac.MediaType.COG
        )
    )

    # Validate item
    item.validate()

    return item


def main(args: Namespace = None) -> int:
    if args is None:
        parser = ArgumentParser(
            description="Creates STAC Catalog (as Collection or Catalog) or OGC Records Catalog",
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
            "-c",
            "--collection",
            help="Create STAC collection",
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
        parser.add_argument(
            "-y",
            "--yml",
            help="Update input yaml for API-Records.",
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
            catalog_id = config["catalog_id"]
            catalog_title = config["catalog_title"]
            catalog_desc = config["catalog_desc"]
            url = config["url"]
            temp = config["files"]
            files = temp.split(",")
            out_default = config["output_dir"]
            gsd = config["gsd"]
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
    else:
        ofolder = out_default

    if not os.path.exists(ofolder):
        if not os.path.islink(ofolder):
            print("Output folder {} does not exists, creating".format(ofolder))
            os.makedirs(ofolder)

    # Version
    f = open(os.path.join(os.path.dirname(__file__),'__init__.py'), "r")
    version_file = f.read()
    version_line = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",version_file, re.M)
    logger.info("Running {}".format(version_line.group()))
    version = version_line.group().split("'")[1]

    # Date range
    # Add item to catalog
    if args.test:
        dateval = datetime.utcnow()
    else:
        fdate = files[0].split("_")[0]
        dateval = datetime(int(fdate[0:4]), int(fdate[4:6]), int(fdate[6:8]), int(fdate[9:11]), int(fdate[11:13]),
                           int(fdate[13:15]))

    if len(files) > 1: # If more than one file
        fdate = files[len(files) - 1].split("_")[0]
        end_dateval = datetime(int(fdate[0:4]), int(fdate[4:6]), int(fdate[6:8]), int(fdate[9:11]),
                               int(fdate[11:13]),
                               int(fdate[13:15]))

    else:
        end_dateval = dateval

    # Create catalog sub_folder - delete if exists
    if args.stac or args.collection:
        cat_folder = os.path.join(ofolder,catalog_id + "-stac-v" + version)
    else:
        cat_folder = os.path.join(ofolder,catalog_id + "-records-v" + version)

    if os.path.exists(cat_folder):
        shutil.rmtree(cat_folder)
    os.mkdir(cat_folder)

    # Get image and then extract information from first object
    img_path = pull_s3bucket(logger, tmp_dir, urlpath+files[0], catalog_id, catalog_desc)
    bbox, footprint, src_crs, dst_crs = get_bbox_and_footprint(logger, img_path)
    logger.debug("Footprint: {}".format(footprint))

    if args.stac or args.collection:
        logger.info("Creating STAC Catalog or Collection")

        # Create collection extent
        spatial_extent = pystac.SpatialExtent([bbox])
        temporal_extent = pystac.TemporalExtent([[dateval, end_dateval]])
        collection_extent = pystac.Extent(spatial_extent, temporal_extent)

        # Create catalog
        if args.collection:
            catalog = pystac.Collection(id=catalog_id, title=catalog_title, description=catalog_desc, extent=collection_extent)

            # Setup provider information
            catalog.providers = [
                pystac.Provider(name='Pixalytics Ltd', roles=['producer'], url='https://www.pixalytics.com/')]

        else:
            catalog = pystac.Catalog(id=catalog_id, title=catalog_title, description=catalog_desc)

        for file in files:
            item = add_item(footprint, bbox, src_crs.split(":")[1], gsd, url, file)
            catalog.add_item(item)

        # Update extents in catalog from items
        if args.collection:
            catalog.update_extent_from_items()

        # JSON dump item
        logger.debug(json.dumps(item.to_dict(), indent=4))

        # Set HREFs
        catalog.normalize_hrefs(cat_folder)

        # Validate, which needs: pip install pystac[validation]
        catalog.validate_all()

        # Save catalog
        catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)

        # Show catalog
        with open(catalog.get_self_href()) as f:
            print(f.read())

    else: # OGC Records
        logger.info("Creating Records Catalog")

        # Create catalog information
        catalog_dict = {}
        catalog_dict.update({'cat_id': catalog_id})
        catalog_dict.update({'cat_description': catalog_desc})
        catalog_dict.update({'cat_begin': dateval.strftime("%Y-%m-%d")})
        catalog_dict.update({'cat_end': end_dateval.strftime("%Y-%m-%d")})

        # Loop for each file to create a record for
        count = 0
        link_dict = {}
        for file in files:

            # For each file, update generic record yaml
            out_yaml = os.path.join(os.path.dirname(__file__), os.path.splitext(yaml_file)[0] + "-updated.yml")

            # Read YML contents
            with open(os.path.join(os.path.dirname(__file__),yaml_file)) as f:
                # use safe_load instead load
                dataMap = yaml.safe_load(f)
                f.close()

            # Update bounding box
            logger.debug("dataMap: {} ".format(dataMap['identification']['extents']['spatial']))
            yaml_dict = {}
            yaml_dict['bbox'] = '[{},{},{},{}]'.format(bbox[0],bbox[1],bbox[2],bbox[3])
            yaml_dict.update({'crs': ast.literal_eval(dst_crs.split(":")[1])})
            dataMap['identification']['extents']['spatial'] = yaml_dict
            logger.debug("Modified dataMap: {} ".format(dataMap['identification']['extents']['spatial']))

            # Update dates
            logger.debug("dataMap: {} ".format(dataMap['identification']['extents']['temporal']))
            fdate = file.split("_")[0]
            dateval = datetime(int(fdate[0:4]), int(fdate[4:6]), int(fdate[6:8]), int(fdate[9:11]), int(fdate[11:13]),
                               int(fdate[13:15]))
            datestr = dateval.strftime("%Y-%m-%d")

            yaml_dict = {}
            yaml_dict.update({'begin': datestr})
            yaml_dict.update({'end': datestr})
            dataMap['identification']['extents']['temporal'] = yaml_dict
            logger.debug("Modified dataMap: {} ".format(dataMap['identification']['extents']['temporal']))

            # Update filename
            logger.debug("dataMap: {} ".format(dataMap['metadata']['dataseturi']))
            dataMap['metadata']['dataseturi'] = url+file
            logger.debug("Modified dataMap: {} ".format(dataMap['metadata']['dataseturi']))

            # Remove single quotes
            dataDict = {re.sub("'", "", key): val for key, val in dataMap.items()}

            # Output modified version
            if args.yml:
                with open(out_yaml, 'w') as f:
                    yaml.dump(dataDict, f)
                    f.close()

            # Read YML from disk
            mcf_dict = read_mcf(out_yaml)

            # JSON dataset files
            dataset = "{}{}".format(os.path.basename(yaml_file).split(".")[0],count+1)
            json_file = os.path.join(cat_folder, dataset + ".json")
            link_dict.update({dataset: "./" + os.path.basename(json_file)})

            # Choose API Records output schema
            records_os = OGCAPIRecordOutputSchema()

            # Default schema
            json_string = records_os.write(mcf_dict)
            print(json_string)

            # Write to disk
            with open(json_file, 'w') as ff:
                ff.write(json_string)
                ff.close()

            # Increment for each file
            count += 1

        # Add record links
        if count == 1:
            catalog_dict.update({'cat_file': "./" + os.path.basename(json_file)})
        else:
            catalog_dict.update({'cat_file': link_dict})
        mcf_dict.update(catalog_dict)

        # Choose API Dataset Record as catalog
        # https://github.com/cholmes/ogc-collection/blob/main/ogc-dataset-record-spec.md - see examples
        records_os = OGCAPIDRecordOutputSchema()

        # Default catalog schema
        json_string = records_os.write(mcf_dict)
        print(json_string)

        # Write catalog to disk
        cat_file = os.path.join(cat_folder, "catalog.json")
        with open(cat_file, 'w') as ff:
            ff.write(json_string)
            ff.close()

    # Clean up
    tmp_dir.cleanup()

    logger.info("Processing completed successfully for {}".format(cat_folder))


if __name__ == "__main__":
    exit(main())
