import os, ccdproc, numpy as np, time, sys, smtplib
from datetime import datetime, timedelta
from glob import glob
from astropy import units as u
from astropy.io import fits
from astropy.time import Time

# Adopt the algorithm of the "CCD Noise Model Clipping" introduced in PixInsight Reference Documentation.
def ccdclip(flat_bd_data, readnoise, gain, sigma_low, sigma_high):
    N = len(flat_bd_data)
    mask = np.zeros(flat_bd_data.shape, dtype=bool)
    i_idx = 0
    for i in flat_bd_data:
        mask_row = np.zeros(i.shape, dtype=bool)
        n = 1
        while (n > 0) and (N > 0):
            n = 0
            signal = np.ma.median(np.ma.MaskedArray(i, mask_row))
            k_idx = 0
            for k in np.ma.MaskedArray(i, mask_row):
                if k < signal:
                    sigma = ((readnoise/gain)**2 + k/gain)**0.5
                    dist_low = (signal - k) / sigma
                    if dist_low > sigma_low:
                        mask[i_idx, k_idx] = True
                        mask_row[k_idx] = True
                        n += 1
                        k_idx += 1
                    else:
                        k_idx += 1
                elif k > signal:
                    sigma = ((readnoise/gain)**2 + k/gain)**0.5
                    dist_high = (k - signal) / sigma
                    if dist_high > sigma_high:
                        mask[i_idx, k_idx] = True
                        mask_row[k_idx] = True
                        n += 1
                        k_idx += 1
                    else:
                        k_idx += 1
                else:
                    k_idx += 1
            N -= n
        i_idx += 1
    return np.ma.MaskedArray(flat_bd_data, mask)

# Real-time reduction of raw images.
def realtimeRed(storePath, analyPath, masterDark):
    neos = ccdproc.ImageFileCollection(location=analyPath)
    neoList = []
    for neo, fname in neos.hdus(return_fname=True):
        meta = neo.header
        meta['filename'] = fname
        neoList.append(ccdproc.CCDData(data=neo.data, header=meta, unit="adu"))
    masterBias_e = ccdproc.gain_correct(masterBias, gain=1 * u.electron / u.adu)
    masterDark_e = ccdproc.gain_correct(masterDark, gain=1 * u.electron / u.adu)
    masterFlat_e = ccdproc.gain_correct(masterFlat, gain=1 * u.electron / u.adu)
    for neo in neoList:
        neo_red = ccdproc.ccd_process(neo, master_bias=masterBias_e, dark_frame=masterDark_e, master_flat=masterFlat_e
                                       , gain=1 * u.electron / u.adu, readnoise=readnoise, min_value=1.
                                      , dark_exposure=darkExp * u.second, data_exposure=neo.header['exptime'] * u.second
                                      , exposure_unit=u.second, dark_scale=True)
        baseName = os.path.basename(neo.header['filename'])
        fits.writeto("{}{}_red.fits".format(storePath, baseName.split('.')[0]), neo_red.data, header=neo_red.header, overwrite=False)

# Real time check if there are raw images which are older than 5 minutes and have not been reduced yet.
def realtimeCheck(neoPath, backupPath, analyPath, today, tomorrow, timeUTC, masterDark):
    nowMJD = Time(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), format='iso', scale='utc').mjd
    mjd_1970 = Time("1970-01-01 00:00:00", format='iso', scale='utc').mjd
    now = (nowMJD - mjd_1970) * 24 * 3600
    # A new list of images including newly synchronized ones.
    neoPaths_inhand = glob("{}/*".format(neoPath))
    # A list of images which have been processed and backed up.
    neoPaths_backup = [os.path.basename(i) for i in glob("{}*".format(backupPath))]
    # Cross-match to sort out new images.
    neoPaths_new = [i for i in neoPaths_inhand if os.path.basename(i) not in neoPaths_backup]
    for path in neoPaths_new:
        timeModify = os.path.getmtime(path)
        minuteElapse = (now - timeModify) / 60
        if minElapse >= 5:
            # Copy to an analyzing directory.
            os.system("cp {} {}.".format(path, analyPath))
            # Copy to a back-up directory.
            os.system("cp {} {}.".format(path, backupPath))
        else:
            pass
    realtimeRed("/LWTanaly/{}/neo_red/".format(today), analyPath, masterDark)
    for path in glob("{}*".format(analyPath)):
        os.remove(path)
    if datetime.now().strftime("%Y%m%d%H") < (tomorrow + timeUTC):
        time.sleep(300)
        realtimeCheck(neoPath, backupPath, analyPath, today, tomorrow, timeUTC, masterDark)
    else:
        pass

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
    # Different format of dates.
    date = datetime.now().strftime("%Y%m%d")
    dateDash = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days = 1)).strftime("%Y%m%d")
    tomorrowDash = (datetime.now() + timedelta(days = 1)).strftime("%Y-%m-%d")

    # If there is no script created yesterday, then stop running the program.
    if glob("/LWTdata/LWT_{0}/lulinLWT/{0}.txt".format(date)) == []:
        sys.exit()
    else:
        pass

    # Create essential directories.
    dirPaths = ["/LWTanaly/{}/", "/LWTanaly/{}/bias/", "/LWTanaly/{}/dark_test/", "/LWTanaly/{}/flat/", "/LWTanaly/{}/neo_check/", "/LWTanaly/{}/neo_red/"
                , "/LWTanaly/{}/neo_test_red/", "/LWTanaly/{}/neo_backup/", ]
    for path in dirPaths:
        directory = os.path.dirname(path.format(date))
        os.makedirs(directory, exist_ok = True)

    try:
        # Search for bias frames.
        LWTdata_biasPaths = glob("/LWTdata/LWT_{}/bias-dark/*bias*1MHz*".format(date))
        # Keep searching for bias frames taken on previous days if no usable bias found.
        i = 1
        while LWTdata_biasPaths == []:
            yesterday = (datetime.now() - timedelta(days = i)).strftime("%Y%m%d")
            LWTdata_biasPaths = glob("/LWTdata/LWT_{}/bias-dark/*bias*1MHz*".format(yesterday))
            i += 1
        for path in LWTdata_biasPaths:
            os.system("cp {} /LWTanaly/{}/bias/.".format(path, date))

        with open("/LWTdata/LWT_{0}/lulinLWT/{0}.txt".format(date), 'r') as file:
            lines = file.readlines()
        # Lines in script which contain ephemerides of NEOs.
        neoLines = [i for i in lines if '|' in i]
        # Lines in script which contain interval directive.
        expLines = [i for i in lines if '#INTERVAL' in i]

        # Search for dark frames for science images.
        neoNum = 1
        while neoNum < len(neoLines):
            darkExp = int(expLines[neoNum].split(' ')[1].split('\n')[0])
            LWTdata_darkPaths = glob("/LWTdata/LWT_{}/bias-dark/*dark*{}s*1MHz*".format(date, darkExp))
            i = 0
            while LWTdata_darkPaths == []:
                yesterday = (datetime.now() - timedelta(days = i)).strftime("%Y%m%d")
                newDarks = glob("/LWTdata/LWT_{}/bias-dark/*dark*s*1MHz*".format(yesterday))
                if newDarks != []:
                    # If there are many kinds of exposures taken at previous day, choose an exposure whose difference with originally needed one is the smallest.
                    diffExp = min([abs(int(i.split('/')[-1].split('_')[2].split('s')[0])-darkExp) for i in newDarks])
                    # Check the difference is within 30 seconds and the new exposure is longer than the needed one.
                    if (diffExp <= 30) and ([i for i in newDarks if str(darkExp+diffExp)+'s' in i] != []):
                        LWTdata_darkPaths = [i for i in newDarks if str(darkExp+diffExp)+'s' in i]
                    else:
                        pass
                else:
                    pass
                i += 1
            # If the usable dark frames are found, store them into a dark directory of this NEO.
            directory = os.path.dirname("/LWTanaly/{}/dark_{}/".format(date, neoLines[neoNum][:11].strip(' ')))
            os.makedirs(directory, exist_ok = True)
            for path in LWTdata_darkPaths[:10]:
                os.system("cp {} /LWTanaly/{}/dark_{}/.".format(path, date, neoLines[neoNum][:11].strip(' ')))
            neoNum += 5

        # Search for dark frames for reference images (test images).
        darkExp_test = int(expLines[0].split(' ')[1].split('\n')[0])
        LWTdata_darkPaths_test = glob("/LWTdata/LWT_{}/bias-dark/*dark*{}s*1MHz*".format(date, darkExp_test))
        i = 0
        while LWTdata_darkPaths_test == []:
            yesterday = (datetime.now() - timedelta(days = i)).strftime("%Y%m%d")    
            newDarks = glob("/LWTdata/LWT_{}/bias-dark/*dark*s*1MHz*".format(yesterday))
            if newDarks != []:
                diffExp = min([abs(int(i.split('/')[-1].split('_')[2].split('s')[0])-darkExp_test) for i in newDarks])
                if (diffExp <= 30) and ([i for i in newDarks if str(darkExp_test+diffExp)+'s' in i] != []):
                    LWTdata_darkPaths_test = [i for i in newDarks if str(darkExp_test+diffExp)+'s' in i]
                else:
                    pass
            else:
                pass
            i += 1
        for path in LWTdata_darkPaths_test[:10]:
            os.system("cp {} /LWTanaly/{}/dark_test/.".format(path, date))

        # Search for flat frames.
        LWTdata_flatPaths = glob("/LWTdata/LWT_{}/flat/*V_Astrodon*".format(date))
        if LWTdata_flatPaths == []:
            i = 1
            while LWTdata_flatPaths == []:
                yesterday = (datetime.now() - timedelta(days = i)).strftime("%Y%m%d")
                LWTdata_flatPaths = glob("/LWTdata/LWT_{}/flat/*V_Astrodon*".format(yesterday))
                i += 1
            if len(LWTdata_flatPaths) < 5:
                os.system("cp /LWTdata/LWT_{}/flat/*V_Astrodon* /LWTanaly/{}/flat/.".format(yesterday, date))
            else:
                for path in LWTdata_flatPaths[:5]:
                    os.system("cp {} /LWTanaly/{}/flat/.".format(path, date))
        else:
            if len(LWTdata_flatPaths) < 5:
                os.system("cp /LWTdata/LWT_{0}/flat/*V_Astrodon* /LWTanaly/{0}/flat/.".format(date))
            else:
                for path in LWTdata_flatPaths[:5]:
                    os.system("cp {} /LWTanaly/{}/flat/.".format(path, date))

        gain = 1.4 * u.electron / u.adu
        gainValue = 1.4
        readnoise = 8.2 * u.electron
        readnoiseValue = 8.2
        biasPath = "/LWTanaly/{}/bias/".format(date)
        darkPath_test = "/LWTanaly/{}/dark_test/".format(date)
        flatPath = "/LWTanaly/{}/flat/".format(date)

        # Create master bias frame.
        biases = ccdproc.ImageFileCollection(location=biasPath)
        biasList = []
        for bias, fname in biases.hdus(return_fname=True):
            meta = bias.header
            meta['filename'] = fname
            biasList.append(ccdproc.CCDData(data=bias.data, meta=meta, unit='adu'))
        masterBias = ccdproc.combine(biasList, output_file="/LWTanaly/{}/bias/Master_Bias.fits".format(date), method='median'
                                      , clip_extrema=True, nlow=0, nhigh=1)

        # Create master dark frame for each NEO.
        darkPaths = [i for i in glob("/LWTanaly/{}/dark_*".format(date)) if 'test' not in i]
        masterDark = []
        for path in darkPaths:
            darks = ccdproc.ImageFileCollection(location=path+'/')
            darkList = []
            for dark, fname in darks.hdus(return_fname=True):
                meta = dark.header
                meta['filename'] = fname
                darkList.append(ccdproc.CCDData(data=dark.data, meta=meta, unit="adu"))
            darkList_b = []
            for dark in darkList:
                dark_b = ccdproc.subtract_bias(dark, masterBias)
                darkList_b.append(dark_b)
            masterDark.append(ccdproc.combine(darkList_b, output_file="{}/Master_Dark_{}.fits".format(path, path.split('dark_')[-1]), method='median', clip_extrema=True, nlow=0, nhigh=1))

        # Create master dark frame for reference images.
        darks = ccdproc.ImageFileCollection(location=darkPath_test)
        darkList = []
        for dark, fname in darks.hdus(return_fname=True):
            meta = dark.header
            meta['filename'] = fname
            darkList.append(ccdproc.CCDData(data=dark.data, meta=meta, unit="adu"))
        darkList_b = []
        for dark in darkList:
            dark_b = ccdproc.subtract_bias(dark, masterBias)
            darkList_b.append(dark_b)
        masterDark_test = ccdproc.combine(darkList_b, output_file="/LWTanaly/{}/dark_test/Master_Dark_test.fits".format(date), method='median'
                                      , clip_extrema=True, nlow=0, nhigh=1)

        # If the present time does not exceed UTC19, create master flat frame;
        # otherwise, use the master flat frame which is created previously in case of no time for real-time reduction of raw images.
        if datetime.now().strftime("%H") < '19':
            flats = ccdproc.ImageFileCollection(location=flatPath)
            flatList = []
            for flat, fname in flats.hdus(return_fname=True):
                meta = flat.header
                meta['filename'] = fname
                flatList.append(ccdproc.CCDData(data=flat.data, meta=meta, unit="adu"))
            flatList_bd = []
            for flat in flatList:
                flat_b = ccdproc.subtract_bias(flat, masterBias)
                flat_b_exp = flat_b.header['exptime']
                flat_bd = ccdproc.subtract_dark(flat_b, masterDark[0], dark_exposure=darkExp * u.second, data_exposure=flat_b_exp * u.second
                                                , exposure_unit=u.second, scale=True)
                flatList_bd.append(flat_bd)
            # Use the clipping method to process flat frames.
            flatList_clip = []
            for flat_bd in flatList_bd:
                flat_bd_data = np.asarray(flat_bd)
                flat_clipped = ccdclip(flat_bd_data, readnoiseValue, gainValue, 3., 3.)
                flatList_clip.append(flat_clipped)
            flat_bdArrays = np.ma.array([i for i in flatList_clip])
            masterFlat_array = np.ma.median(flat_bdArrays, axis=0)
            for i, j in zip(np.where(masterFlat_array.data == 0)[0], np.where(masterFlat_array.data == 0)[1]):
                masterFlat_array[i, j] = np.ma.median(masterFlat_array)
            masterFlat = ccdproc.CCDData(masterFlat_array, unit='adu')
            masterFlat.write("/LWTanaly/{0}/flat/Master_Flat_{0}.fits".format(date))
        else:
            masterFlat_path = []
            i = 1
            while masterFlat_path == []:
                yesterday = (datetime.now() - timedelta(days = i)).strftime("%Y%m%d")
                masterFlat_path = glob("/LWTanaly/{}/flat/Master_Flat*".format(yesterday))
            os.system("cp {} /LWTanaly/{}/flat/.".format(masterFlat_path[0], date))
            masterFlat = ccdproc.CCDData.read(masterFlat_path[0], unit='adu')

        # Wait until the beginning time of NEO observation.
        waitLines = [line for line in lines if '#WAITUNTIL' in line]
        neoBegin = int(waitLines[0].split(', ')[1].split(':')[0]) + 8
        neoBegin_mjd = Time("{} {}:00:00".format(dateDash, neoBegin), format='iso', scale='utc').mjd
        nowMJD = Time(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), format='iso', scale='utc').mjd
        wait = (neoBegin_mjd - nowMJD) * 24 * 3600
        if wait > 0:
            time.sleep(wait)
        else:
            pass

        # Set higher recursion limit in case the program is killed by system.
        sys.setrecursionlimit(5000)

        # Real time check and reduce science images.
        neoPath = [i for i in glob("/LWTdata/LWT_{}/lulinLWT/neo/*".format(date)) if 'test' not in i]
        # Only one NEO to be observed.
        if len(neoPath) == 1:
            realtimeCheck(neoPath[0], "/LWTanaly/{}/neo_backup/".format(date), "/LWTanaly/{}/neo_check/".format(date), date, tomorrow, '07', masterDark[0])
        # More than one NEO to be observed.
        else:
            neoList = list(set([line.split(' ')[0] for line in lines if '|' in line]))
            neoOrder = []
            for neo in neoList:
                neoOrder.append(lines.index([line for line in lines if neo in line][0]))
            # Real-time reduction follows the order of NEOs.
            for num, (idx, order) in enumerate(zip(np.arange(2, len(waitLines), 3), np.sort(neoOrder))):
                untilUTC = int(waitLines[idx].split(', ')[1].split(':')[0])
                if untilUTC + 9 + 1 >= 24:
                    realtimeCheck([i for i in neoPath if neoList[neoOrder.index(order)] in i][0], "/LWTanaly/{}/neo_backup/".format(date), "/LWTanaly/{}/neo_check/".format(date), date, tomorrow, str(untilUTC+9+1-24).zfill(2), masterDark[num])
                else:
                    realtimeCheck([i for i in neoPath if neoList[neoOrder.index(order)] in i][0], "/LWTanaly/{}/neo_backup/".format(date), "/LWTanaly/{}/neo_check/".format(date), date, date, str(untilUTC+9+1).zfill(2), masterDark[num])

        # Real time reduce reference images.
        neoPaths_test = [i for i in glob("/LWTdata/LWT_{}/lulinLWT/neo/*".format(date)) if 'test' in i]
        for path in neoPaths_test:
            realtimeRed("/LWTanaly/{}/neo_test_red/".format(date), path+'/', masterDark_test)

        # Wait until tomorrow's 9 am.
        nowMJD = Time(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), format='iso', scale='utc').mjd
        endMJD = Time("{} {}:00:00".format(tomorrowDash, '09'), format='iso', scale='utc').mjd
        wait = (endMJD - nowMJD) * 24 * 3600
        if wait > 0:
            time.sleep(wait)
        else:
            pass

        # If there is no observation done yesterday, remove all of yesterday's data.
        neoPaths_red = glob("/LWTanaly/{}/neo_red/*".format(date))
        if neoPaths_red == []:
            os.system("rm -r /LWTanaly/{}/".format(date))
        else:
            pass
        
        sys.exit()

    # If there are errors occur, email users of the error message.
    except Exception as e:
        sendemail(from_addr    = 'lwt@gm.astro.ncu.edu.tw', 
                  to_addr_list = ['smoBEE@astro.ncu.edu.tw'],
                  cc_addr_list = [], 
                  subject      = '[ERROR] ImgCalib.py ({})'.format(datetime.now().strftime("%Y-%b-%d %H:%M:%S")), 
                  message      = "Error on line {}: [{}] {}".format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e),
                  login        = 'lwt@gm.astro.ncu.edu.tw', 
                  password     = 'lulin1478963')
