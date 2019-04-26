import os, requests, time, ephem, sys, smtplib, shutil, pywinauto, pandas as pd, numpy as np
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from glob import glob

# Obtain ephemerides of the NEO by scrawling the NEOCP.
def scrawlPost(neoName, obsAlt, motion, motForm):
    payload = {'mb':'-30', 'mf':'30', 'dl':'-90', 'du':'+90', 'nl':'0', 'nu':'100', 'sort':'d', 'W':'j', 'obj':neoName, 'obscode':'D37', 'Parallax':'1'
                , 'long':'', 'lat':'', 'alt':'', 'int':'0', 'start':'0', 'raty':'d', 'mot':motion, 'dmot':motForm, 'out':'f', 'sun':'x', 'oalt':obsAlt}
    res = requests.post("https://cgi.minorplanetcenter.net/cgi-bin/confirmeph2.cgi", data = payload)
    soup = BeautifulSoup(res.text, 'lxml')
    ephemerides = soup.select('pre')[0].text.split('\n')[3:-1]
    return ephemerides

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
    # Different formats of today's date.
    date = datetime.now().strftime("%Y%m%d")
    dateDash = datetime.now().strftime("%Y-%m-%d")
    day = datetime.now().strftime("%d")

    # "obsBegin": the end of astronomical dusk. "obsStop": 5 minutes before astronomical dawn.
    longitude = "120:52:23.7"
    latitude = "23:28:07.6"
    altitude = "2860."
    altitudeObs = "40"
    LWT = ephem.Observer()
    LWT.lon, LWT.lat, LWT.elevation, LWT.horizon = longitude, latitude, float(altitude), "-18" 
    Sun = ephem.Sun()
    Sun.compute(epoch='2000')
    obsBegin = str(LWT.next_setting(Sun)).split(' ')[1].split(':')[0]
    LWT.horizon = "-19.25"
    obsStop = str(int(str(LWT.next_rising(Sun)).split(' ')[1].split(':')[0])+1)

    # Create directories.
    dirPaths = ["D:/LWTdata/LWT_{}/lulinLWT/".format(date), "D:/LWTdata/LWT_{}/lulinLWT/neo/".format(date), "D:/LWTdata/LWT_{}/lulinLWT/others/".format(date)]
    for dirPath in dirPaths:
        directory = os.path.dirname(dirPath)
        os.makedirs(directory, exist_ok = True)

    try:
        # Scrawling daily NEOs from the NEOCP section in "Data Available from the Minor Planet Center" page of the MPC.
        res = requests.get("https://www.minorplanetcenter.net/iau/NEO/neocp.txt")
        neos = res.text.split('\n')[:-1]
        params = {'DESIGNATION':[], 'SCORE':[], 'DISCOVERY':[], 'RA':[], 'DEC':[], 'V_MAG':[], 'UPDATE':[], 'OBSERVATION':[]
                  , 'ARC':[], 'H_MAG':[], 'NONE_SEEN':[]}
        for neo in neos:
            eles = neo.split()
            params['DESIGNATION'].extend([eles[0]])
            params['SCORE'].extend([eles[1]])
            params['DISCOVERY'].extend([eles[2] + eles[3] + eles[4]])
            params['RA'].extend([eles[5]])
            params['DEC'].extend([eles[6]])
            params['V_MAG'].extend([eles[7]])
            params['UPDATE'].extend([eles[8] + eles[9] + eles[10] + eles[11]])
            params['OBSERVATION'].extend([eles[12]])
            params['ARC'].extend([eles[13]])
            params['H_MAG'].extend([eles[14]])
            params['NONE_SEEN'].extend([eles[15]])

        # Select the NEOs by "Score >= 70" and "V <= 18".
        scoreThres = 70
        vmagThres = 18
        label_df = ['DESIGNATION', 'SCORE', 'DISCOVERY', 'RA', 'DEC', 'V_MAG', 'UPDATE', 'OBSERVATION', 'ARC', 'H_MAG', 'NONE_SEEN']
        df = pd.DataFrame(params)[label_df]
        df_new = df[(pd.to_numeric(df['SCORE']) >= scoreThres) & (pd.to_numeric(df['V_MAG']) <= vmagThres)]
        df_new.to_csv(os.path.join("D:/LWTdata/LWT_{}/lulinLWT/others/".format(date), 'candidates.csv'), index = False)
        tempDesig = df_new['DESIGNATION'].values

        # Sort the NEOs which do have ephemerise.
        tempDesigSort = list(tempDesig)
        tempDesig = []
        for desig in tempDesigSort:
            if len(scrawlPost(desig, altitudeObs, 'h', 'r')) != 1:
                tempDesig.append(desig)
            else:
                pass
        
        # Record the beginning time and the end time of observable ephemerise and the moving speed of the NEOs.
        ini_fin, motions = [], []
        for candidate in tempDesig:
            try:
                begin_end_1 = []
                for ephemeris in scrawlPost(candidate, altitudeObs, 'h', 'r'):
                    if (ephemeris[8:10] == day) and (ephemeris[11:13] >= obsBegin) and (ephemeris[11:13] <= obsStop):
                        begin_end_1.append(ephemeris)
                if begin_end_1 != []:
                    ini_fin.append(begin_end_1[0][11:13] + begin_end_1[-1][11:13])
                else:
                    ini_fin.append('0000')
                
                begin_end_2 = []
                for ephemeris in scrawlPost(candidate, altitudeObs, 'm', 'p'):
                    if (ephemeris[8:10] == day) and (ephemeris[11:13] >= obsBegin) and (ephemeris[11:13] <= obsStop):
                        begin_end_2.append(ephemeris)
                if begin_end_2 != []:
                    motions.append((float(begin_end_2[0].split('   ')[4].split('  ')[0])+float(begin_end_2[-1].split('   ')[4].split('  ')[0]))/2)
                else:
                    motions.append(0)
            except IndexError:
                pass
        
        # Email users of no observable NEOs today, and the automation system will run Prof. Ngeow's script instead.
        if ini_fin == []:
            shutil.rmtree("D:/LWTdata/LWT_{}/lulinLWT".format(date))
            sendemail(from_addr    = 'lwt@gm.astro.ncu.edu.tw', 
                      to_addr_list = ['lwtgroup@astro.ncu.edu.tw'],
                      cc_addr_list = [], 
                      subject      = 'LWT has "NO" observation today!', 
                      message      = 'Bonjour,\n\nPlease run the script of Prof. Ngeow today!\nMerci beaucoup!\n\nAmuse-toi bien,\nJian-Fong Huang (smoBEE)\nemail: smoBEE@astro.ncu.edu.tw', 
                      login        = 'lwt@gm.astro.ncu.edu.tw', 
                      password     = 'lulin1478963')
            sys.exit()
        else:
            pass

        # Choose a main NEO whose observable time is the longest.
        tempDesig_ok, epheSpan = [], []
        for infn in ini_fin:
            epheSpan.append(int(infn[2:]) - int(infn[:2]))
        tempDesig_ok.append(tempDesig[epheSpan.index(max(epheSpan))])
        iniSeque = ini_fin[epheSpan.index(max(epheSpan))][2:]
        
        # Choose some bonus NEOs whose beginning time is equal to the end time of the former one. (Observe in series.)
        while iniSeque < obsStop:
            try:
                group_max = max([i for i in ini_fin if i[:2] == iniSeque])
                tempDesig_ok.append(tempDesig[ini_fin.index(group_max)])
                iniSeque = group_max[2:]
            except ValueError:
                break
        ini_fin_ok = []
        for candy in tempDesig_ok:
            ini_fin_ok.append(ini_fin[list(tempDesig).index(candy)])
        
        # Choose a bonus NEO whose ephemerides are not totally within the main one and moving speed is the lowest when the above selection process leave only the main one.
        for motion in np.sort(motions):
            idx = motions.index(motion)
            if (len(tempDesig_ok) == 1) and (ini_fin[idx][2:] > iniSeque) and (tempDesig[idx] != tempDesig_ok[0]):
                tempDesig_ok.append(tempDesig[idx])
                if ini_fin[idx][:2] < ini_fin[list(tempDesig).index(tempDesig_ok[0])][2:]:
                    ini_fin_ok.append(ini_fin[list(tempDesig).index(tempDesig_ok[0])][2:] + ini_fin[idx][2:])
                else:
                    ini_fin_ok.append(ini_fin[idx])

        # Basic information of the ACP script.
        TITLE = "; Near-Earth Objects Follow-ups"
        NAME = "; Jian-Fong Huang (smoBEE)"
        INSTITUTE = "; IANCU, Taoyuan, TAIWAN"
        DATE = "; {}".format(datetime.now().strftime("%Y-%b-%d %H:%M:%S"))
        
        # Essential directives of the ACP script.
        FILTER = "#FILTER V_Astrodon_2019"
        BINNING = "#BINNING 1"
        INTERVAL_test = "#INTERVAL 300"
        COUNT_test = "#COUNT 1"
        READOUT = "#READOUTMODE 1 MHz"
        AUTOFOCUS = "#AUTOFOCUS"
        TRACKON = "#TRACKON"
        TRACKOFF = "#TRACKOFF"

        # Create a script which includes the ephemerides of all the NEOs for the auto-bias/dark program to take needed exposures.
        totScriptPath = "D:/LWTdata/LWT_{0}/lulinLWT/{0}.txt".format(date)
        with open(totScriptPath, 'w') as file:
            file.write(TITLE+'\n'+NAME+'\n'+INSTITUTE+'\n'+DATE+'\n;\n'+FILTER+'\n'+BINNING+'\n'+READOUT+'\n'+AUTOFOCUS+'\n'+TRACKON+'\n;\n')

        timeSpan = []
        for num, candy in enumerate(tempDesig_ok):
            # Create a script for each NEO with index number from 000 in file name.
            script_path = "D:/LWTdata/LWT_{0}/lulinLWT/{0}-{1}.txt".format(date, str(num).zfill(3))
            with open(script_path, 'w') as file:
                file.write(TITLE+'\n'+NAME+'\n'+INSTITUTE+'\n'+DATE+'\n;\n'+FILTER+'\n'+BINNING+'\n'+READOUT+'\n'+AUTOFOCUS+'\n'+TRACKON+'\n;\n')
            
            # "3.5*4": define 4 times the FWHM (an average value for the LWT) as the streaking length of stars which is still detectable by SExtractor.
            idx = [num for num, i in enumerate(tempDesig) if i == candy][0]
            exp_nostreak = 3.5*4 / (motions[idx]/60)
            if exp_nostreak > 600: # Slow Motion = Faint Object
                exp_nostreak = 600
            elif exp_nostreak < 60: # Fast Motion = Bright Object
                exp_nostreak = 60
            else:
                pass
            INTERVAL = "#INTERVAL {}".format(int(np.ceil(exp_nostreak)))
            
            # Create a line of orbital elements in target specification format.
            line = ""
            for ephemeris in scrawlPost(candy, altitudeObs, 'h', 'r'):
                if (ephemeris[8:10] == day) and (ephemeris[11:13] >= obsBegin) and (ephemeris[11:13] <= obsStop):
                    with open("D:/LWTdata/LWT_{}/lulinLWT/others/{}_ephem_{}.txt".format(date, candy, motions[idx]*60), 'a') as file:
                        file.write(ephemeris + '\n')
                    line = line + ephemeris[0:35] + "|"
            line = line[:-1]
            
            # Set three pause time for taking a frame as reference image at the beginning, the middle and the end of observation.
            epheOn = ini_fin_ok[num][:2]
            epheOff = ini_fin_ok[num][2:]
            epheMid = str(int(np.floor((int(epheOn) + int(epheOff)) / 2)))
            if (num == 0) or (epheOn >= ini_fin_ok[num-1][2:]):
                waitOn = "#WAITUNTIL 1, {}:00:00".format(epheOn)
                waitOff = "#WAITUNTIL 1, {}:55:00".format(str(int(epheOff)-1))
                epheOn_hour = float(epheOn)
                epheOff_hour = float(epheOff)
            else:
                waitOn = "#WAITUNTIL 1, {}:00:00".format(ini_fin_ok[num-1][2:])
                waitOff = "#WAITUNTIL 1, {}:55:00".format(str(int(epheOff)-1))
                epheOn_hour = float(ini_fin_ok[num-1][2:])
                epheOff_hour = float(epheOff)
            WAIT_mid = "#WAITUNTIL 1, {}:00:00".format(epheMid)
            
            # Create a directory for reference images.
            directory = os.path.dirname("D:/LWTdata/LWT_{}/lulinLWT/neo/{}_test/".format(date, candy))
            os.makedirs(directory, exist_ok = True)
            DIRECTORY_test = "#DIR D:/LWTdata/LWT_{}/lulinLWT/neo/{}_test".format(date, candy)
            with open(script_path, 'a') as file:
                file.write(waitOn + '\n' + INTERVAL_test + '\n' + COUNT_test + '\n' + DIRECTORY_test + '\n' + candy + ' '*(11-len(candy)) + line + '\n;\n')
            with open(totScriptPath, 'a') as file:
                file.write(waitOn + '\n' + INTERVAL_test + '\n' + COUNT_test + '\n' + DIRECTORY_test + '\n' + candy + ' '*(11-len(candy)) + line + '\n;\n')
            
            # Create a directory for target images.
            directory = os.path.dirname("D:/LWTdata/LWT_{}/lulinLWT/neo/{}/".format(date, candy))
            os.makedirs(directory, exist_ok = True)
            DIRECTORY = "#DIR D:/LWTdata/LWT_{}/lulinLWT/neo/{}".format(date, candy)
            # First half of the observation.
            FRAMEs_fh = int((int(epheMid) - epheOn_hour)*(3600*(float(INTERVAL[10:])/(float(INTERVAL[10:])+60))) / float(INTERVAL[10:]))
            COUNT_fh = "#COUNT {}".format(str(FRAMEs_fh))
            if FRAMEs_fh != 0:
                with open(script_path, 'a') as file:
                    file.write(INTERVAL + '\n' + COUNT_fh + '\n' + DIRECTORY + '\n' + candy + ' '*(11-len(candy)) + line + '\n;\n' + WAIT_mid + '\n' + INTERVAL_test + '\n' + COUNT_test + '\n' + DIRECTORY_test + '\n' + candy + ' '*(11-len(candy)) + line + '\n;\n')
                with open(totScriptPath, 'a') as file:
                    file.write(INTERVAL + '\n' + COUNT_fh + '\n' + DIRECTORY + '\n' + candy + ' '*(11-len(candy)) + line + '\n;\n' + WAIT_mid + '\n' + INTERVAL_test + '\n' + COUNT_test + '\n' + DIRECTORY_test + '\n' + candy + ' '*(11-len(candy)) + line + '\n;\n')
            else:
                with open(totScriptPath, 'a') as file:
                    file.write('#WAITUNTIL empty\n' + INTERVAL_test + '\n' + COUNT_test + '\n' + DIRECTORY_test + '\n' + candy + ' '*(11-len(candy)) + line + '\n;\n')
            # Last half of the observation.
            FRAMEs_lh = int((epheOff_hour - int(epheMid))*(3600*(float(INTERVAL[10:])/(float(INTERVAL[10:])+60))) / float(INTERVAL[10:]))
            COUNT_lh = "#COUNT {}".format(str(FRAMEs_lh))
            with open(script_path, 'a') as file:
                file.write(INTERVAL + '\n' + COUNT_lh + '\n' + DIRECTORY + '\n' + candy + ' '*(11-len(candy)) + line + '\n;\n' + waitOff + '\n' + INTERVAL_test + '\n' + COUNT_test + '\n' + DIRECTORY_test + '\n' + candy + ' '*(11-len(candy)) + line + '\n;\n' + TRACKOFF + '\n')
            with open(totScriptPath, 'a') as file:
                file.write(INTERVAL + '\n' + COUNT_lh + '\n' + DIRECTORY + '\n' + candy + ' '*(11-len(candy)) + line + '\n;\n' + waitOff + '\n' + INTERVAL_test + '\n' + COUNT_test + '\n' + DIRECTORY_test + '\n' + candy + ' '*(11-len(candy)) + line + '\n;\n' + TRACKOFF + '\n')
            
            timeSpan.append(str(epheOff_hour - epheOn_hour))
            
            # If this NEO is not the last one, continue observing the next NEO; otherwise, run Prof. Ngeow's script.
            if num != len(tempDesig_ok)-1:
                with open(script_path, 'a') as file:
                    file.write(';\n#CHAIN D:/LWTdata/LWT_{0}/lulinLWT/{0}-{1}.txt'.format(date, str(num+1).zfill(3)))
            else:
                cngeowPaths = glob("C:/Users/User/Documents/ACP Astronomy/Plans/cngeow*LWT.txt")
                cngeowModTimes = [os.path.getctime(i) for i in cngeowPaths]
                cngeow = cngeowPaths[cngeowModTimes.index(max(cngeowModTimes))].split('\\')[1]
                with open(script_path, 'a') as file:
                    file.write(";\n#CHAIN C:/Users/User/Documents/ACP Astronomy/Plans/{}".format(cngeow))

        with open(totScriptPath, 'a') as file:
            file.write(';\n; End of Plan\n')
        
        # Email users of today's observation.
        with open('D:/LWTdata/LWT_{0}/lulinLWT/{0}-{1}.txt'.format(date, '000'), 'r') as file:
            lines = file.readlines()
        breaks = [line for line in lines if '#WAITUNTIL' in line]
        breakOn = int(breaks[0].split(', ')[1].split(':')[0])
        with open('D:/LWTdata/LWT_{0}/lulinLWT/{0}-{1}.txt'.format(date, str(len(tempDesig_ok)-1).zfill(3)), 'r') as file:
            lines = file.readlines()
        breaks = [line for line in lines if '#WAITUNTIL' in line]
        breakOff = int(breaks[-1].split(', ')[1].split(':')[0])+1
        sendemail(from_addr    = 'lwt@gm.astro.ncu.edu.tw', 
                  to_addr_list = ['lwtgroup@astro.ncu.edu.tw'],
                  cc_addr_list = [], 
                  subject      = '{} - LWT NEO Observation'.format(datetime.now().strftime("%Y-%b-%d %H:%M:%S")),
                  message      = 'Bonjour,\n\nI will have an observation from UTC {} to UTC {} tonight!\nOBJECT: {}\nMerci beaucoup!\n\nAmuse-toi bien,\nJian-Fong Huang (smoBEE)\nemail: smoBEE@astro.ncu.edu.tw'.format(breakOn, breakOff, tempDesig_ok), 
                  login        = 'lwt@gm.astro.ncu.edu.tw', 
                  password     = 'lulin1478963')
        
        # Wait until tomorrow morning (9 am).
        nowH = datetime.now().strftime("%H")
        nowM = datetime.now().strftime("%M")
        nowS = datetime.now().strftime("%S")
        logwebWait = (9+24)*3600 - (int(nowH)*3600 + int(nowM)*60 + int(nowS))
        time.sleep(logwebWait)
        
        # Login the LWT's website.
        driver = webdriver.Firefox()
        driver.implicitly_wait(30)
        driver.get("https://accounts.google.com/signin/v2/identifier?continue=https%3A%2F%2Fsites.google.com%2Fa%2Fgm.astro.ncu.edu.tw%2Flulin-wt%2Fhome%2Fneo-history&followup=https%3A%2F%2Fsites.google.com%2Fa%2Fgm.astro.ncu.edu.tw%2Flulin-wt%2Fhome%2Fneo-history&hd=gm.astro.ncu.edu.tw&service=jotspot&sacu=1&rip=1&flowName=GlifWebSignIn&flowEntry=ServiceLogin")
        driver.find_element_by_id("identifierId").clear()
        driver.find_element_by_id("identifierId").send_keys("lwt@gm.astro.ncu.edu.tw")
        driver.find_element_by_id("identifierId").send_keys(Keys.ENTER)
        time.sleep(3)
        driver.find_element_by_name("password").clear()
        driver.find_element_by_name("password").send_keys("lulin1478963")
        driver.find_element_by_name("password").send_keys(Keys.ENTER)
        time.sleep(10)
        
        # Insert observation information of yesterday's NEOs.
        for num, desig in enumerate(tempDesig_ok):
            neoFiles = glob("D:/LWTdata/LWT_{}/lulinLWT/neo/{}/*".format(date, desig))
            if neoFiles != []:
                ctimes = []
                for path in neoFiles:
                    ctimes.append(os.path.getctime(path))
                spanS = max(ctimes) - min(ctimes)
                
                driver.find_element_by_id("sites-list-page-add-item-btn").click()
                driver.find_element_by_name("9451658628950361").clear()
                driver.find_element_by_name("9451658628950361").send_keys(desig) # DESIGNATION
                driver.find_element_by_name("175286879084108").click()
                driver.find_element_by_name("175286879084108").clear()
                driver.find_element_by_name("175286879084108").send_keys(dateDash) # DATE
                driver.find_element_by_name("01692577855132127").click()
                driver.find_element_by_name("01692577855132127").clear()
                driver.find_element_by_name("01692577855132127").send_keys(len(neoFiles)) # FRAMEs
                driver.find_element_by_name("1507081724651984").click()
                driver.find_element_by_name("1507081724651984").clear()
                driver.find_element_by_name("1507081724651984").send_keys(str(spanS/3600)) # TIME SPAN (hr)
                driver.find_element_by_name("80802864192836").click()
                driver.find_element_by_name("80802864192836").clear()
                driver.find_element_by_name("80802864192836").send_keys("{}.txt".format(date)) # DESCRIPTION
                driver.find_element_by_class_name("jfk-button-primary").click()
                time.sleep(3)
            else:
                pass
        
        # Upload yesterday's ACP script.
        neoFiles = []
        for desig in tempDesig_ok:
            neoFiles += glob("D:/LWTdata/LWT_{}/lulinLWT/neo/{}/*".format(date, desig))
        if neoFiles != []:
            driver.find_element_by_xpath("//div[@id='sites-attachments-add-file-btn']/a/div[2]").click()
            # driver.find_element_by_xpath("//input[@type='file']").clear()
            # driver.find_element_by_xpath("//input[@type='file']").send_keys("D:\\LWTdata\\LWT_{0}\\lulinLWT\\{0}.txt".format(date))
            time.sleep(3)

            app = pywinauto.Application().connect(title_re=r'上傳檔案')
            dlg = app[r'上傳檔案']
            dlg['ComboBoxEx'].type_keys('D:\\LWTdata\\LWT_{0}\\lulinLWT\\{0}.txt'.format(date))
            dlg['&Open'].Click()
            try:
                dlg['&Open'].Click()
            except:
                pass
            time.sleep(10)
        else:
            pass
        driver.quit()

    # If there are errors occur, email users of the error message.
    except Exception as e:
        sendemail(from_addr    = 'lwt@gm.astro.ncu.edu.tw', 
                  to_addr_list = ['smoBEE@astro.ncu.edu.tw'],
                  cc_addr_list = [], 
                  subject      = '[ERROR] autoACPscript ({})'.format(datetime.now().strftime("%Y-%b-%d %H:%M:%S")), 
                  message      = "Error on line {}: [{}] {}".format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e),
                  login        = 'lwt@gm.astro.ncu.edu.tw', 
                  password     = 'lulin1478963')
