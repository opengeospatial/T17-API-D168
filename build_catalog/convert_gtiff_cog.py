import os
import sys
import subprocess
from argparse import Namespace, ArgumentParser
import glob

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
        print("Could not find any input files in {}".format(args.indir))
        sys.exit(1)
    for infile in infiles:
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
