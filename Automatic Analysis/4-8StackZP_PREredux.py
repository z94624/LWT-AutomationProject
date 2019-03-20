import os, sys, shutil, pandas as pd, numpy as np, smtplib
from six.moves import urllib
from datetime import datetime, timedelta
from glob import glob
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from photutils import make_source_mask, DAOStarFinder, CircularAperture, aperture_photometry
from astropy.time import Time
from astropy.wcs import WCS
from astroML.crossmatch import crossmatch_angular

# Read a catalog.
def readCat(path):
    with fits.open(path) as hdu:
        catData = hdu[1].data
    return catData

# Send email.
def sendemail(from_addr, to_addr_list, cc_addr_list,
              subject, message,
              login, password,
              smtpserver='smtp.gmail.com:587'):
    header  = 'From: %s\n' % from_addr
    header += 'To: %s\n' % ','.join(to_addr_list)
    header += 'Cc: %s\n' % ','.join(cc_addr_list)
    header += 'Subject: %s\n\n' % subject
    message = header + message
    server = smtplib.SMTP(smtpserver)
    server.starttls()
    server.login(login,password)
    problems = server.sendmail(from_addr, to_addr_list, message)
    server.quit()
    return problems

if __name__ == '__main__':
    # If there is no script created yesterday, then stop running the program.
    yesterday = (datetime.now() - timedelta(days = 1)).strftime("%Y%m%d")
    if [i for i in glob("/LWTanaly/*") if yesterday in i] == []:
        sys.exit()
    else:
        pass

    # Create essential directories.
    dirPaths = ["/LWTanaly/{}/neo_resamp/", "/LWTanaly/{}/neo_stack/"]
    for path in dirPaths:
        directory = os.path.dirname(path.format(yesterday))
        if not os.path.exists(directory):
            os.makedirs(directory)
    # The directory for storing resampled images.
    resampPath = "/LWTanaly/{}/neo_resamp".format(yesterday)

    try:
        # Find astrometric solution of each reduced image.
        redPaths = glob("/LWTanaly/{}/neo_red/*".format(yesterday))
        redPaths_test = glob("/LWTanaly/{}/neo_test_red/*".format(yesterday))
        redPathses = redPaths + redPaths_test
        for path in redPathses:
            ra_dec = os.popen("gethead {} OBJCTRA OBJCTDEC".format(path)).readlines()
            if ra_dec != []:
                raPart = ra_dec[0][:11]
                ra = raPart.split(' ')[0] + ':' + raPart.split(' ')[1] + ':' + raPart.split(' ')[2]
                decPart = ra_dec[0][12:23]
                dec = decPart.split(' ')[0] + ':' + decPart.split(' ')[1] + ':' + decPart.split(' ')[2]
                os.system("/astrometry/bin/solve-field {} -p -O --timestamp --ra {} --dec {} --radius 2 -t 2 -L 1.2 -H 1.25 -u app".format(path, ra, dec))
            else:
                pass

        # Create SExtractor catalogs in "FITS_LDAC" format for SCAMP to read.
        newPaths = glob("/LWTanaly/{}/neo_red/*.new".format(yesterday))
        for path in newPaths:
            os.system("/usr/bin/sextractor -c /home/z94624/Desktop/sextractor/lwt.sex -CATALOG_NAME {}_scamp.cat -CATALOG_TYPE FITS_LDAC {}".format(path.split('.')[0], path))

        # Use SCAMP to convert the SIP distortion convention into the PV distortion convention (".head" extension).
        catPaths = glob("/LWTanaly/{}/neo_red/*.cat".format(yesterday))
        with open("/LWTanaly/{}/neo_red/sexcat.list".format(yesterday), 'w') as file:
            for path in catPaths:
                file.write("{}\n".format(path))
        os.system("/usr/bin/scamp @/LWTanaly/{0}/neo_red/sexcat.list -c /home/z94624/Desktop/lwt.scamp -MERGEDOUTCAT_NAME /LWTanaly/{0}/neo_red/merged.cat -FULLOUTCAT_NAME /LWTanaly/{0}/neo_red/full.cat -CHECKIMAGE_NAME /LWTanaly/{0}/neo_red/check.fits -AHEADER_GLOBAL /LWTanaly/{0}/neo_red/scamp.ahead -XML_NAME /LWTanaly/{0}/neo_red/scamp.xml".format(yesterday))

        # Process NEOs one by one.
        neoNames = list(set([path.split('/')[-1].split('-')[0] for path in newPaths]))
        for neoName in neoNames:
            neoPaths = np.sort([path for path in newPaths if neoName in path])
            
            # Estimate the number of frames as a tracklet on account of the exposure time.
            exptime = fits.getheader(neoPaths[0])['EXPTIME']
            # If the integration time is 60s, it means that the motion of this NEO is fast, so the tracking performance must be very poor.
            if int(exptime) == 60:
                setFrames = 1
            # For other integration times, the stacking limit is 600s.
            else:
                setFrames = int(np.ceil(600 / exptime))
                if setFrames > len(neoPaths):
                    setFrames = len(neoPaths)
                else:
                    pass
            midIdx = int(np.floor(setFrames/2))

            leadIdx = 0
            # Process tracklets one by one.
            while leadIdx <= (len(neoPaths)-setFrames):
                trackletPaths = neoPaths[leadIdx:leadIdx+setFrames]

                # Use SWarp to resample all the images in a tracklet, and it will co-add those by the way.
                with open("/LWTanaly/{}/neo_red/tracklet_{}.list".format(yesterday, setFrames), 'w') as file:
                    for path in trackletPaths:
                        file.write("{}\n".format(path))
                coaddPath = "{}/{}_coadd.fits".format(resampPath, trackletPaths[0].split('/')[-1].split('.')[0])
                os.system("/usr/bin/swarp @/LWTanaly/{0}/neo_red/tracklet_{1}.list -c /home/z94624/Desktop/lwt.swarp -RESAMPLE_DIR {2} -XML_NAME {2}/swarp.xml -IMAGEOUT_NAME {3} -WEIGHTOUT_NAME {2}/coadd_weight.fits".format(yesterday, setFrames, resampPath, coaddPath))

                resampFiles = glob("{}/*_resamp.fits".format(resampPath))
                resampPaths = [path for path in resampFiles if '/LWTanaly/{}/neo_red/'.format(yesterday)+path.split('/')[-1].split('_resamp')[0]+'.new' in trackletPaths]

                # Stack all the resampled images in a tracklet.
                arrLen = 4096
                upper = int(2048 + arrLen/2)
                lower = int(2048 - arrLen/2)
                stkData = np.zeros((arrLen, arrLen))
                for path in resampPaths:
                    stkData += fits.getdata(path)[lower:upper, lower:upper]
                # Continue to use the header of the middle image.
                stkHeader = fits.getheader(trackletPaths[midIdx])

                # Create some useful headers related to the stacked images.
                firstHeader = fits.getheader(trackletPaths[0])
                lastHeader = fits.getheader(trackletPaths[-1])
                startTime = firstHeader['TIME-OBS'].split(':')
                startTime_hr = int(startTime[0]) + int(startTime[1])/60 + int(startTime[2])/3600
                endTime = lastHeader['TIME-OBS'].split(':')
                endTime_hr = int(endTime[0]) + int(endTime[1])/60 + (int(endTime[2])+exptime)/3600
                midTime = (startTime_hr + endTime_hr) / 2
                stkHeader.set('S-MIDATE', "{}T{}:{}:{}Z".format(stkHeader['DATE-OBS'].split('T')[0], str(int(midTime)).zfill(2), str(int(midTime*60%60)).zfill(2), np.round(float(midTime*3600%60), 2)), " UTC mid-date/time of stacked image")
                stkHeader.set('S-MIDTIM', "{}:{}:{}".format(str(int(midTime)).zfill(2), str(int(midTime*60%60)).zfill(2), float(midTime*3600%60)), " UTC mid-time of stacked image")
                stkHeader.set('S-EXPTIM', (endTime_hr-startTime_hr)*3600, " [sec] Duration of exposure")
                time2jd = Time("{} {}:{}:{}".format(stkHeader['DATE-OBS'].split('T')[0], str(int(midTime)).zfill(2), str(int(midTime*60%60)).zfill(2), float(midTime*3600%60)), format='iso', scale='utc')
                stkHeader.set('S-JD-OBS', time2jd.jd, " Julian Date at mid of exposure")
                stkHeader.set('S-MJDOBS', time2jd.mjd, " Modified Julian Date at mid of exposure")

                stkPath = "/LWTanaly/{}/neo_stack/{}_stack.fits".format(yesterday, trackletPaths[0].split('/')[-1].split('.')[0])
                fits.writeto(stkPath, stkData, header=stkHeader, overwrite=True)

                # Use the coadded images to create SExtractor catalogs for calculating the photometric zero point.
                os.system("/usr/bin/sextractor -c /home/z94624/Desktop/sextractor/lwt.sex -CATALOG_NAME {}_zp.cat -DETECT_THRESH 10.0 -ANALYSIS_THRESH 10.0 {}".format(coaddPath.split('.')[0], coaddPath))
                sexData = readCat("{}_zp.cat".format(coaddPath.split('.')[0]))
                sexRA = sexData['ALPHA_J2000']
                sexDec = sexData['DELTA_J2000']
                sexMag = sexData['MAG_AUTO']
                sexMagerr = sexData['MAGERR_AUTO']
                coaddFWHM = np.median(sexData['FWHM_IMAGE'])

                # Download the APASS catalogs.
                ra_dec = os.popen("gethead {} OBJCTRA OBJCTDEC".format(trackletPaths[midIdx])).readlines()
                raPart = ra_dec[0][:11]
                ra = raPart.split(' ')[0] + '%3A' + raPart.split(' ')[1] + '%3A' + raPart.split(' ')[2]
                decPart = ra_dec[0][12:23]
                if decPart.split(' ')[0][0] == '+':
                    dec = '%2B' + decPart.split(' ')[0][1:] + '%3A' + decPart.split(' ')[1] + '%3A' + decPart.split(' ')[2]
                else:
                    dec = decPart.split(' ')[0] + '%3A' + decPart.split(' ')[1] + '%3A' + decPart.split(' ')[2]
                response = urllib.request.urlopen("https://www.aavso.org/cgi-bin/apass_download.pl?ra={}&dec={}&radius=2&outtype=1".format(ra, dec))
                with open("{}.csv".format(trackletPaths[midIdx].split('.')[0]), 'wb') as file:
                    shutil.copyfileobj(response, file)

                # Read the APASS catalogs.
                apass = pd.read_csv(open("{}.csv".format(trackletPaths[midIdx].split('.')[0]), 'r'))
                notNAN = np.asarray([num for num, (v, ve) in enumerate(zip(apass['Johnson_V'].values, apass['Verr'].values)) if (str(v) != 'nan') and (str(ve) != 'nan')])
                apassRA = apass['radeg'].values[notNAN]
                apassDec = apass['decdeg'].values[notNAN]
                apassMag = apass['Johnson_V'].values[notNAN]
                apassMagerr = abs(apass['Verr'].values[notNAN])

                # Cross-match the sources between SExtractor catalogs and APASS catalogs.
                apassTable = np.column_stack((apassRA, apassDec))
                sexTable = np.column_stack((sexRA, sexDec))
                dist, ind = crossmatch_angular(apassTable, sexTable, coaddFWHM*1.22*2/3600)
                match = ~np.isinf(dist)
                sexMag_mat = sexMag[ind[match]]
                sexMagerr_mat = sexMagerr[ind[match]]

                # Calculate the zero point and its error.
                zp = np.mean(apassMag[match] - sexMag_mat)
                zperr = (np.sum(apassMagerr[match]**2)+np.sum(sexMagerr_mat**2))**(0.5) / len(sexMag_mat)

                # Store the zero point as new headers.
                hdu = fits.open(stkPath, mode='append')
                hdu[0].header.set("S-ZEROPT", str(zp), " sexInstMag+ZP=apassCalibMag")
                hdu[0].header.set("S-ZEROER", str(zperr), " sexZPerr+apassZPerr")
                fits.writeto(stkPath, hdu[0].data, header=hdu[0].header, overwrite=True)

                # Create SExtractor catalogs for the resampled images.
                resampFWHMs = []
                reX_df, reY_df, reRA_df, reDec_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
                for path in resampPaths:
                    # Set the detection threshold to 5 especially for bright stars.
                    os.system("/usr/bin/sextractor -c /home/z94624/Desktop/sextractor/lwt.sex -CATALOG_NAME {}_neo.cat -DETECT_THRESH 5.0 -ANALYSIS_THRESH 5.0 {}".format(path.split('.')[0], path))
                    sexData = readCat("{}_neo.cat".format(path.split('.')[0]))
                    sexFlag = sexData['FLAGS_WIN']
                    goodIdx = [idx for idx, i in enumerate(sexFlag) if i == 0]
                    sexX = sexData['XWIN_IMAGE'][goodIdx]
                    sexY = sexData['YWIN_IMAGE'][goodIdx]
                    sexRA = sexData['ALPHA_J2000'][goodIdx]
                    sexDec = sexData['DELTA_J2000'][goodIdx]
                    sexFWHM = sexData['FWHM_IMAGE'][goodIdx]
                    resampFWHMs.append(np.median(sexFWHM))
                    # Store different informations of all the resampled images separately.
                    reX_df = pd.concat([reX_df, pd.DataFrame(sexX.byteswap().newbyteorder())], ignore_index=True, axis=1)
                    reY_df = pd.concat([reY_df, pd.DataFrame(sexY.byteswap().newbyteorder())], ignore_index=True, axis=1)
                    reRA_df = pd.concat([reRA_df, pd.DataFrame(sexRA.byteswap().newbyteorder())], ignore_index=True, axis=1)
                    reDec_df = pd.concat([reDec_df, pd.DataFrame(sexDec.byteswap().newbyteorder())], ignore_index=True, axis=1)

                # Cross-match all the catalogs with respect to the middle one, because the common sources are known objects.
                reX_mat, reY_mat = [], []
                refTable = np.column_stack((reRA_df[midIdx].values, reDec_df[midIdx].values))
                for idx in range(setFrames):
                    if idx != midIdx:
                        comTable = np.column_stack((reRA_df[idx].values, reDec_df[idx].values))
                        dist, ind = crossmatch_angular(refTable, comTable, resampFWHMs[idx]*1.22/3600)
                        match = ~np.isinf(dist)
                        reX_mat += reX_df[idx].values[ind[match]].tolist()
                        reY_mat += reY_df[idx].values[ind[match]].tolist()
                    else:
                        reX_mat += reX_df[midIdx].values.tolist()
                        reY_mat += reY_df[midIdx].values.tolist()

                # Create SExtractor catalogs again for the purpose of finding all possible sources including very faint ones.
                # Set the detection threshold to 2 especially for faint objects.
                os.system("/usr/bin/sextractor -c /home/z94624/Desktop/sextractor/lwt.sex -CATALOG_NAME {}_neo.cat -DETECT_THRESH 2.0 -ANALYSIS_THRESH 2.0 {}".format(stkPath.split('.')[0], stkPath))
                sexData = readCat("{}_neo.cat".format(stkPath.split('.')[0]))
                stkX = sexData['XWIN_IMAGE']
                stkY = sexData['YWIN_IMAGE']
                stkRA = sexData['ALPHA_J2000']
                stkDec = sexData['DELTA_J2000']
                stkFWHM = sexData['FWHM_IMAGE']

                # Cross-match the catalog containing known objects with the catalog including all possible sources.
                refTable = np.column_stack((stkX, stkY))
                comTable = np.column_stack((np.asarray(reX_mat), np.asarray(reY_mat)))
                dist, ind = crossmatch_angular(refTable, comTable, 0)
                # Sort out sources which are not matched. => Sources probably are unknown objects.
                nomatch = np.isinf(dist)
                # Narrow down to the sources locating in the central 500*500 region.
                candies = [(x, y, f) for (x, y, f) in zip(stkX[nomatch], stkY[nomatch], stkFWHM[nomatch]) if (1798 <= x < 2298) and (1798 <= y < 2298)]
                # Choose a source whose FWHM is the largest as the most probable NEO candidate.
                target = candies[[i[2] for i in candies].index(np.max([i[2] for i in candies]))]

                # Store X, Y and FWHM of this candidate.
                with open("/LWTanaly/{}/neo_stack/neoPosition_{}.dat".format(yesterday, neoName), 'a') as file:
                    file.write("{},{},{}\n".format(target[0], target[1], np.max([i[2] for i in candies])))

                leadIdx += setFrames

    # If there are errors occur, email users of the error message.
    except Exception as e:
        sendemail(from_addr    = 'lwt@gm.astro.ncu.edu.tw', 
                  to_addr_list = ['smoBEE@astro.ncu.edu.tw'],
                  cc_addr_list = [], 
                  subject      = '[ERROR] ZP_Positioning.py ({})'.format(datetime.now().strftime("%Y-%b-%d %H:%M:%S")), 
                  message      = "Error on line {}: [{}] {}".format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e),
                  login        = 'lwt@gm.astro.ncu.edu.tw', 
                  password     = '')
