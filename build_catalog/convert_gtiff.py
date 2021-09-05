import os
import sys
import subprocess
from argparse import Namespace, ArgumentParser
import glob
import numpy as np
import re
import datetime as dt
import time
import uuid
from netCDF4 import Dataset, date2num
from osgeo import osr, gdal
import logging

home = os.path.expanduser("~")
print("Home directory: {}".format(home))
gdal_home = os.path.join(home, "anaconda3/envs/rsgislib_dev/bin")

# Run external shell command
def execmd(command):

        # Replaced due to shell=True being a security hazard
        p = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
        output = p.stdout.read()
        p.stdin.close()
        p.stdout.close()
        # p.communicate()

        if output:
            return output

        else:
            return None

def read_geotiff(file):

        ds = gdal.Open(file)
        layers = ds.RasterCount
        xsize, ysize = ds.RasterXSize, ds.RasterYSize
        geotransform = ds.GetGeoTransform()

        # Get projection
        wkt = ds.GetProjection()

        # Setup array
        darray = np.zeros((layers, ysize, xsize), dtype=np.uint8)

        # Read data
        for layer in range(layers):
            tmpdata = ds.GetRasterBand(layer+1).ReadAsArray()
            darray[layer,:,:] = tmpdata

        return darray, geotransform, wkt


def writeNetCDF(infile, outdir, description, logger):
    """
    Writes a data array to a given file along with the relevant metadata for each array being written to file

    :param infile: path to desired input file
    """

    # Extract date from filename
    elements = os.path.basename(infile).split("_")
    sub_element = elements[0]
    date = dt.datetime(int(sub_element[0:4]), int(sub_element[4:6]), int(sub_element[6:8]))
    logger.info("Date: {} as {}".format(sub_element, date))

    # Setup file to write
    ofile = os.path.join(outdir, os.path.basename(infile).split(".")[0]+".nc")
    nc_fid = Dataset(ofile, 'w', format='NETCDF4')

    # Global Attributes & min/max
    null_value = 0
    # Version
    f = open(os.path.join(os.path.dirname(__file__),'__init__.py'), "r")
    version_file = f.read()
    version_line = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",version_file, re.M)
    logger.info("Running {}".format(version_line.group()))
    version = version_line.group().split("'")[1]

    # Load data
    data, gt, wkt = read_geotiff(infile)
    minv = np.amin(data)
    maxv = np.amax(data)
    logger.info('Data array: {}'.format(data.shape))
    bands, xdim, ydim = data.shape

    # Calculate four corners
    minx = gt[0]
    miny = gt[3] + xdim*gt[4] + ydim*gt[5]
    maxx = gt[0] + xdim*gt[1] + ydim*gt[2]
    maxy = gt[3]

    cs = osr.SpatialReference()
    cs.ImportFromWkt(wkt)
    prj = cs.GetAttrValue('geogcs')
    logger.info("Projection: {}".format(prj))
    lons = np.linspace(minx, maxx, num=xdim)
    lats = np.linspace(miny, maxy, num=ydim)

    nc_fid.title = "OGC API: {}".format(description)
    nc_fid.summary = "Product from the OGC API project, produced using an approached developed by Pixalytics Ltd."
    nc_fid.description = description
    nc_fid.history = 'Created ' + time.ctime(time.time())
    nc_fid.time_coverage_start = sub_element
    nc_fid.time_coverage_end = sub_element
    nc_fid.time_coverage_duration = "1 day"
    nc_fid.source = 'Pixalytics Ltd'
    nc_fid.product_version = "Version " + version
    x = uuid.uuid1()
    nc_fid.uuid = str(x)
    # Will be the DOI
    # nc_fid.tracking_id = "xxxx"
    nc_fid.Conventions = 'CF-1.5'
    nc_fid.iso19115_topic_categories = "Environment; GeoscientificInformation"
    nc_fid.standard_name_vocabulary = "NetCDF Climate and Forecast (CF) Metadata Convention"
    nc_fid.acknowledgment = "Funded by OGC"
    nc_fid.creator_name = "Pixalytics Ltd"
    nc_fid.creator_email = "helpdesk@pixalytcs.com"
    nc_fid.creator_url = "http://www.pixalytics.com"

    # Dimensions - 3D, time plus number of rows and columns
    nc_fid.createDimension('time', 1)
    nc_fid.createDimension('lat', lats.shape[0])
    nc_fid.createDimension('lon', lons.shape[0])

    logger.debug("writeNetCDF, Data X(min,max): {:.2f} {:.2f}".format(np.amin(lons), np.amax(lons)))
    logger.debug("writeNetCDF, Data Y(min,max): {:.2f} {:.2f}".format(np.amin(lats), np.amax(lats)))
    logger.debug("writeNetCDF, Dimensions YX: {} {}".format(len(lats), len(lons)))

    # Variable Attributes for each projection type
    longitudes = nc_fid.createVariable('lon', 'f8', ('lon',))
    longitudes[:] = lons[:]
    latitudes = nc_fid.createVariable('lat', 'f8', ('lat',))
    latitudes[:] = lats[:]
    longitudes.long_name = 'longitude'
    longitudes.units = 'degree_east'
    latitudes.long_name = 'latitude'
    latitudes.units = 'degree_north'
    longitudes.axis = "X"
    latitudes.axis = "Y"
    longitudes.reference_datum = "geographical coordinates, WGS84 projection"
    latitudes.reference_datum = "geographical coordinates, WGS84 projection"

    # Temporal attribute setting
    times = nc_fid.createVariable('time', 'f8', ('time',))
    times.units = 'hours since 0001-01-01 00:00:00'
    ctime = date2num(date, times.units, calendar='gregorian')
    times[:] = [ctime]
    times.calendar = 'gregorian'  # variables
    times.axis = 'T'
    times.standard_name = 'time'

    # Global attributes are set up for each file, dependent on input variable
    # CF Standard Names: http://cfconventions.org/standard-names.html
    nc_var = nc_fid.createVariable('data', 'u1', ('time', 'lat', 'lon'), fill_value=null_value)
    nc_var.setncatts({'long_name': u"{}".format(description),
                      'level_desc': u'Surface',
                      'var_desc': u"Surface Classification"})

    # Defining the parameters and metadata for UTM and East Africa
    # model projections
    crs = nc_fid.createVariable('crs', 'i4')
    nc_var.grid_mapping = "crs"
    crs.grid_mapping_name = "latitude_longitude"
    crs.semi_major_axis = 6378137.0
    crs.inverse_flattening = 298.257
    crs.epsg_code = 4326

    # Scale data according to acceptable min max range
    logger.info("writeNetCDF, {} Variable range before scaling: {} {}".format(ofile, np.amin(data[data > null_value]), np.amax(data)))
    data[data > maxv] = maxv
    data[(data > null_value) & (data <= minv)] = minv
    logger.info("writeNetCDF, {} Variable range after scaling: {} {}".format(ofile, np.amin(data[data > null_value]), np.amax(data)))

    nc_var = np.zeros((xdim, ydim), dtype=np.uint8)
    nc_var[:,:] = data[0,:,:]
    nc_fid.close()


def main(args: Namespace = None) -> int:
    if args is None:
        parser = ArgumentParser(
            description="Creates COG from GeoTIFF",
            epilog="Should be run with GDAL installed",
        )
        parser.add_argument(
            "-i",
            "--indir",
            type=str,
            dest="indir",
            help="Input data folder",
        )
        parser.add_argument(
            "-o",
            "--outdir",
            type=str,
            dest="outdir",
            help="Output data folder",
        )
        parser.add_argument(
            "-n",
            "--netcdf",
            help="Convert to NetCDF rather than COG.",
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

    # Reform any input GeoTIFFs to COGs
    infiles = glob.glob(os.path.join(args.indir,"*.tif"))
    if len(infiles) == 0:
        logger.info("Could not find any input files in {}".format(args.indir))
        sys.exit(1)

    if args.netcdf:
        logger.info("Converting TIFFs to NetCDF format")
    else:
        logger.info("Converting TIFFs to COG format")

    for infile in infiles:
        if args.netcdf: # Conversion to NetCDF
            writeNetCDF(infile, args.outdir, 'EO4SAS Land Cover Classification', logger)
        else: # Conversion to COG
            cmd = "{}/gladdo -r nearest {} 2 4 8 16 32 64 128 256 512".format(gdal_home, infile)
            execmd(cmd)
            outfile = os.path.join(args.outdir, os.path.basename(infile))
            if os.path.exists(outfile):
                os.remove(outfile)
            cmd = "{}/gdal_translate -co COMPRESS=DEFLATE -co BIGTIFF=YES -co TILED=YES -co BLOCKXSIZE=512 -co BLOCKYSIZE=512 --config GDAL_TIFF_OVR_BLOCKSIZE 512 -co COPY_SRC_OVERVIEWS=YES {} {}".format(gdal_home, infile,outfile)
            execmd(cmd)

    logger.info("Processing completed successfully for {}".format(args.indir))


if __name__ == "__main__":
    exit(main())
