import matplotlib
matplotlib.use('Agg')
import numpy as np, scipy as sci, os, pylab as pyl, sys, smtplib
from trippy import pill
from glob import glob
from astropy.io import fits
from astropy.wcs import WCS
from datetime import datetime, timedelta

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

    stkPaths_all = glob("/LWTanaly/{}/neo_stack/*_stack.fits".format(yesterday))
    try:
        neoNames = list(set([path.split('/')[-1].split('-')[0] for path in stkPaths_all]))
        for neoName in neoNames:
            stkPaths_neo = np.sort([path for path in stkPaths_all if neoName in path])
            with open("/LWTanaly/{}/neo_stack/neoPosition_{}.dat".format(yesterday, neoName), 'r') as file:
                positions = file.readlines()
            
            for stkPath, position in zip(stkPaths_neo[:2], positions[:2]):
                with fits.open(stkPath) as hdu:
                    stkData = hdu[0].data
                    stkHeader = hdu[0].header
                
                zp = float(stkHeader['S-ZEROPT'])
                obsTime = stkHeader['S-MIDATE']
                expTime = np.round(stkHeader['S-EXPTIM'])
                tsfFWHM = float(position.split(',')[2])
                motion = float(glob("/LWTdata/LWT_{}/lulinLWT/others/*ephem*".format(yesterday))[0].split('_')[-1].split('.')[0]) # "/hr
                # The length of stacked NEO is estimated to be 2 times the FWHM.
                exptime = tsfFWHM*2 / (motion/3600)

                neoX = float(position.split(',')[0])
                neoY = float(position.split(',')[1])

                # Calculate the moving direction of the NEO.
                with open("/LWTdata/LWT_{0}/lulinLWT/{0}.txt".format(yesterday), 'r') as file:
                    lines = file.readlines()
                ephes = [line for line in lines if '|' in line][0].split('|')
                # The beginning position.
                ephemRA = [float([i for i in ephes[0].split('    ') if '.' in i][0])]
                ephemDec = [float([i for i in ephes[0].split('    ') if '.' in i][1])]
                # The last position.
                ephemRA.append(float(ephes[-1].split('    ')[1]))
                ephemDec.append(float(ephes[-1].split('    ')[2].split('\n')[0]))
                ephemX, ephemY = WCS(stkPath).wcs_world2pix(np.asarray(ephemRA)*15, np.asarray(ephemDec), 1)
                minXidx = ephemX.tolist().index(np.min(ephemX))
                maxXidx = ephemX.tolist().index(np.max(ephemX))
                if (ephemY[minXidx] > ephemY[maxXidx]) and (minXidx == 1):
                    direction = 180 - np.arctan(abs(ephemY[0]-ephemY[1])/abs(ephemX[0]-ephemX[1]))
                elif (ephemY[minXidx] > ephemY[maxXidx]) and (minXidx == 0):
                    direction = 360 - np.arctan(abs(ephemY[0]-ephemY[1])/abs(ephemX[0]-ephemX[1]))
                elif (ephemY[minXidx] < ephemY[maxXidx]) and (minXidx == 1):
                    direction = 180 + np.arctan(abs(ephemY[0]-ephemY[1])/abs(ephemX[0]-ephemX[1]))
                elif (ephemY[minXidx] < ephemY[maxXidx]) and (minXidx == 0):
                    direction = np.arctan(abs(ephemY[0]-ephemY[1])/abs(ephemX[0]-ephemX[1]))
                direction = np.round(direction, 2)

                # Do the pill aperture photometry.
                phot = pill.pillPhot(stkData, repFact=10)
                phot(neoX, neoY, radius=tsfFWHM*1.4, l=(exptime/3600.)*motion/1.22, a=direction, skyRadius=4*tsfFWHM, width=6*tsfFWHM, zpt=zp, exptime=exptime
                    , enableBGSelection=True, display=True, backupMode="smart", trimBGHighPix=3.)
                neoMag = np.round((-2.5)*np.log10(phot.sourceFlux) + zp, 1)
                
                with open("/LWTanaly/{}/ADESelement.dat".format(yesterday), 'a') as file:
                    neoRA, neoDec = WCS(stkPath).wcs_pix2world(neoX, neoY, 1)
                    neoRA = np.round(float(neoRA)/15, 2)
                    neoDec = np.round(float(neoDec), 1)
                    file.write("{}\t{}\t{}\t{}\t{}\t{}\n".format(neoName, obsTime, neoRA, neoDec, neoMag, expTime))

        # Create the ACP report in ADES format.
        os.system("/home/z94624/.conda/envs/py27/bin/python /home/z94624/Desktop/autoMPCreport.py /LWTanaly/{0}/{0}_IANCU-LWT_smoBEE.xml".format(yesterday))
        # Submit the report to the MPC.
        os.system("/anaconda3/bin/curl https://minorplanetcenter.net/submit_xml -F 'ack=Observations of {0} at {1}' -F 'ac2=lwt@gm.astro.ncu.edu.tw' -F 'obj_type=NEOCP' -F 'source=</LWTanaly/{1}/{1}_IANCU-LWT_smoBEE.xml'".format(neoNames, yesterday))

    # If there are errors occur, email users of the error message.
    except Exception as e:
        sendemail(from_addr    = 'lwt@gm.astro.ncu.edu.tw', 
                  to_addr_list = ['smoBEE@astro.ncu.edu.tw'],
                  cc_addr_list = [], 
                  subject      = '[ERROR] Phot_Report.py ({})'.format(datetime.now().strftime("%Y-%b-%d %H:%M:%S")), 
                  message      = "Error on line {}: [{}] {}".format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e),
                  login        = 'lwt@gm.astro.ncu.edu.tw', 
                  password     = '......')
