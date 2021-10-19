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
import pyproj
from osgeo import osr, gdal
import logging

home = os.path.expanduser("~")
print("Home directory: {}".format(home))
gdal_home = os.path.join(home, "anaconda3/envs/rsgislib_dev/bin")
python = os.path.join(home, "anaconda3/envs/rsgislib_dev/bin/python")

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


def writeNetCDF(infile, outdir, description, logger, datelist=False):
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
    print('Data array: {}'.format(data.shape))
    bands, ydim, xdim = data.shape

    # Calculate four corners of image
    minx = gt[0]
    maxx = gt[0] + xdim * gt[1] + ydim * gt[2]
    miny = gt[3] + xdim * gt[4] + ydim * gt[5]
    maxy = gt[3]

    cs = osr.SpatialReference()
    cs.ImportFromWkt(wkt)
    zone = cs.GetAttrValue("PROJCS").split(" ")[5]
    if zone[-1:] == "S":
        correction = -1.0
    else:
        correction = 1.0
    utmz = int(zone[:-1]) * correction
    prj = cs.GetAttrValue("AUTHORITY", 1)
    sref = cs.ExportToWkt()
    print("Spatial Ref: {}".format(sref))
    print("EPSG Projection: {} Zone: {}".format(prj, utmz))
    lons = np.linspace(minx, maxx, num=xdim)
    lats = np.linspace(miny, maxy, num=ydim)

    nc_fid.title = "OGC API: {}".format(description)
    nc_fid.summary = "Product from the OGC API project, produced using an approached developed by Pixalytics Ltd."
    nc_fid.description = description
    nc_fid.history = 'Created ' + time.ctime(time.time())
    nc_fid.time_coverage_start = sub_element
    nc_fid.time_coverage_end = sub_element
    if datelist:
        nc_fid.time_coverage_duration = "{} days".format(len(datelist))
    else:
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
    nc_fid.acknowledgment = "Testbed 17 activity supported by OGC"
    nc_fid.creator_name = "Pixalytics Ltd"
    nc_fid.creator_email = "helpdesk@pixalytics.com"
    nc_fid.creator_url = "https://www.pixalytics.com"

    # Dimensions - 3D, time plus number of rows and columns
    if datelist:
        nc_fid.createDimension('time', len(datelist))
    else:
        nc_fid.createDimension('time', 1)

    nc_fid.createDimension('x0', lons.shape[0])
    nc_fid.createDimension('y0', lats.shape[0])

    print("Data X(min,max): {:.2f} {:.2f} Y(min,max): {:.2f} {:.2f}".format(minx, maxx, miny, maxy))
    print("writeNetCDF, Dimensions YX: {} {}".format(len(lats), len(lons)))

    # Variable Attributes for each projection type
    x = nc_fid.createVariable('x0', 'f8', ('x0',))
    x[:] = lons
    y = nc_fid.createVariable('y0', 'f8', ('y0',))
    y[:] = lats
    x.long_name = 'x coordinate of projection'
    x.standard_name = 'projection_x_coordinate'
    x.units = 'm'
    y.long_name = 'y coordinate of projection'
    y.standard_name = 'projection_y_coordinate'
    y.units = 'm'
    x.reference_datum = "cartesian coordinates, UTM projection"
    y.reference_datum = "cartesian coordinates, UTM projection"

    # Temporal attribute setting
    times = nc_fid.createVariable('time', 'f8', ('time',))
    times.units = 'hours since 0001-01-01 00:00:00'
    if datelist:
        times[:] = datelist[:]
    else:
        ctime = date2num(date, times.units, calendar='gregorian')
        times[:] = [ctime]
    times.calendar = 'gregorian'  # variables
    times.axis = 'T'
    times.standard_name = 'time'

    # Global attributes are set up for each variable
    # CF Standard Names: http://cfconventions.org/standard-names.html
    # Use zlib option to apply compression
    nc_var = nc_fid.createVariable('data', 'u1', ('time', 'y0', 'x0'), fill_value=null_value, zlib=True)
    nc_var.setncatts({'long_name': u"{}".format(description),
                      'units': u'None',
                      'level_desc': u'Surface',
                      'var_desc': u"Surface Classification"})

    # Defining the parameters and metadata for UTM aprojections
    crs = nc_fid.createVariable('crs', 'i4')
    nc_var.grid_mapping = "crs"
    # Converting the projection grid to WGS84
    srcproj = pyproj.CRS("EPSG:{}".format(prj))
    dstproj = pyproj.CRS("EPSG:4326")
    transformer = pyproj.Transformer.from_crs(srcproj, dstproj)
    minlat, minlon = transformer.transform(minx, miny)
    maxlat, maxlon = transformer.transform(maxx, maxy)
    lons = np.linspace(minlon, maxlon, num=xdim)
    lats = np.linspace(minlat, maxlat, num=ydim)
    print("Lon(min,max): {:.2f} {:.2f} Lat(min,max): {:.2f} {:.2f}".format(minlon, maxlon,minlat, maxlat))

    # Defining the parameters and metadata for UTM projection
    longitudes = nc_fid.createVariable('lon', 'f8', ('x0',))
    longitudes[:] = lons[:]
    latitudes = nc_fid.createVariable('lat', 'f8', ('y0',))
    latitudes[:] = lats[:]
    longitudes.long_name = 'longitude'
    longitudes.units = 'degree_east'
    latitudes.long_name = 'latitude'
    latitudes.units = 'degree_north'
    crs.grid_mapping_name = "transverse_mercator"
    crs.crs_type = "projected_2d"
    crs.false_easting = 500000.0
    crs.false_northing = 10000000.0
    crs.latitude_of_projection_origin = 0.0
    crs.scale_factor_at_central_meridian = 0.9996
    crs.longitude_of_central_meridian = 39.0
    crs.spatial_ref = sref
    crs.GeoTransform = gt

    # Scale data according to acceptable min max range
    print("writeNetCDF, {} Variable range: {} {}".format(ofile, np.amin(data[0,:,:]), np.amax(data[0,:,:])))

    if datelist:
        nc_var[:, :, :] = data[:, :, :]
    else:
        nc_var[0, :, :] = data[0,:,:]
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
            "-r",
            "--rgb",
            help="Convert RGB version of file",
            action="store_true",
            default=False,
        )
        parser.add_argument(
            "-s",
            "--single",
            help="Convert to single NetCDF rather than one per GeoTIFF.",
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

    # Create output directory if does not exist
    if not os.path.exists(args.outdir):
        os.mkdir(args.outdir)

    # Reform any input GeoTIFFs to COGs
    if args.rgb:
        searchstr = os.path.join(args.indir, "*_rgb_classification.tif")
        infiles = glob.glob(searchstr)
    else:
        searchstr = os.path.join(args.indir, "*_classification.tif")
        infiles = [fn for fn in glob.glob(searchstr) if "rgb" not in os.path.basename(fn)]
    if len(infiles) == 0:
        logger.info("Could not find any input files in {}".format(args.indir))
        sys.exit(1)

    if args.netcdf or args.single:
        logger.info("Converting TIFFs to NetCDF format")
    else:
        logger.info("Converting TIFFs to COG format")

    # Merge GeoTiFFs into stacked array
    if args.single:
        intiffs = ""
        datelist = []
        for count,infile in enumerate(infiles):
            intiffs += " {}".format(infile)

            # Extract date from filename
            elements = os.path.basename(infile).split("_")
            sub_element = elements[0]
            if count == 0:
                start_element = elements[0]
            date = dt.datetime(int(sub_element[0:4]), int(sub_element[4:6]), int(sub_element[6:8]))
            ctime = date2num(date, 'hours since 0001-01-01 00:00:00', calendar='gregorian')
            print("Date: {} as {}".format(sub_element, ctime))
            datelist.append(ctime)

        outfile = os.path.join(args.outdir,"{}-{}_{}".format(start_element, elements[0], elements[1]))
        cmd = "{} {}/gdal_merge.py -separate -o {} {}".format(python, gdal_home, outfile, intiffs)
        if not os.path.exists(outfile):
            print(cmd)
            execmd(cmd)
        infiles = []
        infiles.append(outfile)

    # Convert input files to COGs or NetCDFs
    for infile in infiles:
        if args.netcdf or args.single: # Conversion to NetCDF
            if args.single:
                print("Creating NetCDF from {}".format(outfile))
                writeNetCDF(outfile, args.outdir, 'EO4SAS Land Cover Classification', logger, datelist=datelist)
            else:
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
