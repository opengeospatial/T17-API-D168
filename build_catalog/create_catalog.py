import shutil
import sys

# pystac 1.1.0 installed
import pystac
from pystac.extensions.projection import ProjectionExtension
import os
from argparse import ArgumentParser
from urllib.request import urlretrieve
from urllib.error import URLError
from tempfile import TemporaryDirectory
import rasterio
from rasterio.warp import transform_bounds
from shapely.geometry import Polygon, mapping
from datetime import datetime
import json
import ast
import re
# Pixalytics version of repository, from https://github.com/geopython/pygeometa
from pygeometa.core import read_mcf
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
    endstr = os.path.splitext(url)[1]
    img_path = os.path.join(tmp_dir.name, 'image' + endstr)

    try:
        urlretrieve(url, img_path)
    except URLError:
        logger.warning("Failed to retrieve {} to {}".format(url, img_path))
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

    # Add projection metadata using projection extension
    ProjectionExtension.add_to(item)
    proj_ext = ProjectionExtension.ext(item)
    proj_ext.epsg = int(epsg)

    # Add image
    if os.path.splitext(image_id)[1] == ".nc":
        file_type = pystac.MediaType.HDF5
    else:
        file_type = pystac.MediaType.COG
    item.add_asset(
        key='image',
        asset=pystac.Asset(
            href=img_path + image_id,
            media_type=file_type
        )
    )

    # Validate item
    item.validate()

    return item


def main():
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
        "-T",
        "--tds",
        help="Create Test Data Set catalog",
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
        "-n",
        "--netcdf",
        help="Create records for NetCDFs rather than COGs",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-ns",
        "--netcdfsingle",
        help="Create record for single NetCDF that has stacked GeoTIFFs",
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
    code_dir, program = os.path.split(__file__)
    logger = logging.getLogger(program)
    logger.setLevel(logging.DEBUG if "verbose" in args and args.verbose else logging.INFO)

    # Configuration to be loaded from main directory
    if args.test:
        CONFIGURATION_FILE_PATH = os.path.join(code_dir, "test-configuration.yaml")
    elif args.tds:
        CONFIGURATION_FILE_PATH = os.path.join(code_dir, "tds-configuration.yaml")
    elif args.netcdf:
        CONFIGURATION_FILE_PATH = os.path.join(code_dir, "configuration-nc.yaml")
    elif args.netcdfsingle:
        CONFIGURATION_FILE_PATH = os.path.join(code_dir, "configuration-nc-single.yaml")
    else:
        CONFIGURATION_FILE_PATH = os.path.join(code_dir, "configuration.yaml")

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
            provider_name = config["provider_name"]
            provider_url = config["provider_url"]

            logging.debug("Configuration was loaded from '{}'.".format(CONFIGURATION_FILE_PATH))
    except (FileNotFoundError, IOError):
        logging.warning("Unable to load default configuration from '{}', relying on input variables.".format(
            CONFIGURATION_FILE_PATH))
        sys.exit(1)

    # Setup S3 bucket url
    if args.url:
        urlpath = args.url
    else:
        urlpath = url

    # Temp directory
    tmp_dir = TemporaryDirectory()

    # Setup output folder
    if args.outdir:
        outdir = args.outdir
    else:
        outdir = out_default

    if not os.path.exists(outdir):
        if not os.path.islink(outdir):
            print("Output folder {} does not exists, creating".format(outdir))
            os.makedirs(outdir)

    # Version
    f = open(os.path.join(os.path.dirname(__file__), '__init__.py'), "r")
    version_file = f.read()
    version_line = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    logger.info("Running {}".format(version_line.group()))
    version = version_line.group().split("'")[1]

    # Date range
    # Add item to catalog
    if args.test:
        dateval = datetime.utcnow()
        end_dateval = dateval
    else:
        fdate = files[0].split("_")[0]
        dateval = datetime(int(fdate[0:4]), int(fdate[4:6]), int(fdate[6:8]), int(fdate[9:11]), int(fdate[11:13]),
                           int(fdate[13:15]))

        if args.netcdfsingle:
            fdate = fdate.split("-")[1]
        elif len(files) > 1:  # If more than one file
            fdate = files[len(files) - 1].split("_")[0]
        end_dateval = datetime(int(fdate[0:4]), int(fdate[4:6]), int(fdate[6:8]), int(fdate[9:11]), int(fdate[11:13]), int(fdate[13:15]))

    print("Date range {} to {}".format(dateval, end_dateval))

    # Include netcdf in sub_folder name
    if args.netcdf:
        netcdf = "-nc"
    elif args.netcdfsingle:
        netcdf = "-nc-single"
    else:
        netcdf = ""
    # Create catalog sub_folder - delete if exists
    if args.stac or args.collection:
        cat_folder = os.path.join(outdir, "{}-stac{}-v{}".format(catalog_id, netcdf, version))
    else:
        cat_folder = os.path.join(outdir, "{}-records{}-v{}".format(catalog_id, netcdf, version))

    if os.path.exists(cat_folder):
        shutil.rmtree(cat_folder)
    os.mkdir(cat_folder)

    # Get image and then extract information from first object
    img_path = pull_s3bucket(logger, tmp_dir, urlpath + files[0], catalog_id, catalog_desc)
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
            catalog = pystac.Collection(id=catalog_id, title=catalog_title, description=catalog_desc,
                                        extent=collection_extent)

            # Setup provider information
            catalog.providers = [
                pystac.Provider(name=provider_name, roles=[pystac.ProviderRole.PRODUCER], url=provider_url)]

        else:
            catalog = pystac.Catalog(id=catalog_id, title=catalog_title, description=catalog_desc)

        for count, file in enumerate(files):
            item = add_item(footprint, bbox, src_crs.split(":")[1], gsd, url, file)
            if count == 0:
                # JSON dump item
                logger.debug(json.dumps(item.to_dict(), indent=4))

            catalog.add_item(item)

        # Update extents in catalog from items
        if args.collection:
            catalog.update_extent_from_items()

        # Set HREFs
        catalog.normalize_hrefs(cat_folder)

        # Validate, which needs: pip install pystac[validation]
        catalog.validate_all()

        # Save catalog
        catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)

        # Show catalog
        with open(catalog.get_self_href()) as f:
            print(f.read())

    else:  # OGC Records
        logger.info("Creating OGC Records Catalog")

        # Create catalog information
        catalog_dict = {}
        catalog_dict.update({'cat_id': catalog_id})
        catalog_dict.update({'cat_description': catalog_desc})
        cat_begin = dateval.strftime("%Y-%m-%d")
        cat_end = end_dateval.strftime("%Y-%m-%d")
        catalog_dict.update({'cat_begin': cat_begin})
        catalog_dict.update({'cat_end': cat_end})

        # Loop for each file to create an OGC record for each
        link_dict = {}
        for count, file in enumerate(files):

            # For each file, update generic record yaml
            out_yaml = os.path.join(os.path.dirname(__file__), os.path.splitext(os.path.basename(yaml_file))[0] + "-updated.yml")

            # Read YML contents
            with open(os.path.join(os.path.dirname(__file__), yaml_file)) as f:
                # use safe_load instead load
                dataMap = yaml.safe_load(f)
                f.close()

            # Update bounding box
            logger.info("dataMap: {} ".format(dataMap['identification']['extents']['spatial']))
            yaml_dict = {}
            float_bbox = '[{:.3f},{:.3f},{:.3f},{:.3f}]'.format(bbox[0], bbox[1], bbox[2], bbox[3])
            yaml_dict.update({'bbox': ast.literal_eval(float_bbox)})
            yaml_dict.update({'crs': ast.literal_eval(dst_crs.split(":")[1])})
            # remove single quotes
            res = {key.replace("'", ""): val for key, val in yaml_dict.items()}
            dataMap['identification']['extents']['spatial'] = [res]
            logger.info("Modified dataMap: {} ".format(dataMap['identification']['extents']['spatial']))

            # Update dates
            logger.debug("dataMap: {} ".format(dataMap['identification']['extents']['temporal']))
            fdate = file.split("_")[0]
            dateval = datetime(int(fdate[0:4]), int(fdate[4:6]), int(fdate[6:8]), int(fdate[9:11]), int(fdate[11:13]),
                               int(fdate[13:15]))
            date_string = dateval.strftime("%Y-%m-%d")
            if args.netcdfsingle:
                end_date_string = end_dateval.strftime("%Y-%m-%d")
            else:
                end_date_string = date_string

            yaml_dict = {}
            yaml_dict.update({'begin': date_string})
            yaml_dict.update({'end': end_date_string})
            dataMap['identification']['extents']['temporal'] = [yaml_dict]
            logger.debug("Modified dataMap: {} ".format(dataMap['identification']['extents']['temporal']))

            # Update filename
            logger.debug("dataMap: {} ".format(dataMap['metadata']['dataseturi']))
            dataMap['metadata']['dataseturi'] = url + file
            logger.debug("Modified dataMap: {} ".format(dataMap['metadata']['dataseturi']))

            # Updated url and file type
            dataMap['distribution']['s3']['url'] = url + file
            if os.path.splitext(file) == "tif":
                dataMap['distribution']['s3']['type'] = 'GeoTIFF'
            else:
                dataMap['distribution']['s3']['type'] = 'NetCDF'
            logger.debug("Modified dataMap type: {} ".format(dataMap['distribution']['s3']['type']))
            logger.debug("Modified dataMap url: {} ".format(dataMap['distribution']['s3']['url']))

            # Remove single quotes
            dataDict = {re.sub("'", "", key): val for key, val in dataMap.items()}

            # Output modified version of YAML
            with open(out_yaml, 'w') as f:
                yaml.dump(dataDict, f)
                f.close()

            # Read modified YAML into dictionary
            mcf_dict = read_mcf(out_yaml)

            # JSON dataset files
            dataset = "{}{}".format(os.path.basename(yaml_file).split(".")[0], count + 1)
            # create dataset folder
            dset_folder = os.path.join(cat_folder, dataset)
            os.mkdir(dset_folder)
            json_file = os.path.join(dset_folder, dataset + ".json")
            link_dict.update({dataset: "{}/".format(dataset) + os.path.basename(json_file)})

            # Choose API Records output schema
            records_os = OGCAPIRecordOutputSchema()

            # Default schema
            json_string = records_os.write(mcf_dict)

            # Write to disk
            with open(json_file, 'w') as ff:
                ff.write(json_string)
                ff.close()

            # Last loop
            if files[-1] == files[count]:

                # For the catalog, update generic record yaml
                cat_yaml = yaml_file.replace("record","catalog")
                out_yaml = os.path.join(os.path.dirname(__file__), os.path.splitext(os.path.basename(cat_yaml))[0] + "-updated.yml")

                # Read original YML contents
                print(out_yaml)
                with open(os.path.join(os.path.dirname(__file__), cat_yaml)) as f:
                    # use safe_load instead of load
                    dataMap = yaml.safe_load(f)
                    f.close()

                # Update details
                dataMap['identification']['extents']['spatial'] = [res]
                yaml_dict = {}
                yaml_dict.update({'begin': date_string})
                yaml_dict.update({'end': end_date_string})
                dataMap['identification']['extents']['temporal'] = [yaml_dict]

                # Remove single quotes
                dataDict = {re.sub("'", "", key): val for key, val in dataMap.items()}

                # Output modified version of YAML
                with open(out_yaml, 'w') as f:
                    yaml.dump(dataDict, f)
                    f.close()

                # Read modified YAML into dictionary
                mcf_dict = read_mcf(out_yaml)

                # Add record links
                catalog_dict.update({'cat_file': link_dict})
                mcf_dict.update(catalog_dict)

                # Catalog adjustments
                mcf_dict['metadata']['identifier'] = catalog_id
                mcf_dict['identification']['title'] = catalog_title
                mcf_dict['identification']['name'] = 'sam'
                mcf_dict['identification']['abstract'] = catalog_desc

                now_dateval = datetime.utcnow().strftime("%Y-%m-%d")

                mcf_dict['identification']['dates']['creation'] = now_dateval
                mcf_dict['identification']['dates']['revision'] = now_dateval
                mcf_dict['distribution']['s3']['url'] = link_dict
                print("Links: ",mcf_dict)
                # Choose API Dataset Record as catalog
                # https://github.com/cholmes/ogc-collection/blob/main/ogc-dataset-record-spec.md - see examples
                records_os = OGCAPIRecordOutputSchema()

                # Default catalog schema
                #print(mcf_dict)
                json_string = records_os.write(mcf_dict)
                logging.debug(json_string)

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
