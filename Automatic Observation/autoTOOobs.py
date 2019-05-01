import requests, time, pywinauto, ephem, smtplib, sys, os
from datetime import datetime
from bs4 import BeautifulSoup
from glob import glob

# Obtain the present time.
def nowTime():
    nowHr = int(datetime.now().strftime("%H"))
    nowMin = int(datetime.now().strftime("%M"))
    nowSec = int(datetime.now().strftime("%S"))
    return nowHr, nowMin,  nowSec

# Connect to the window of opened software.
def appConnect(winTitle, winClass):
    win_app = pywinauto.Application().connect(title_re=winTitle, class_name=winClass)
    win_dlg = win_app[winTitle]
    return win_app, win_dlg

# Restart the ACP script which was interrupted thanks to the bad weather.
def reboot():
    try:
        # Click "Run" button of the ACP to select a script from "Select a plan file" dialog.
        acp_dlg.Run.click_input()
        time.sleep(3)
        run_app, run_dlg = appConnect('Select a plan file', '#32770')
        
        # The end time of the NEO script.
        if glob("D:/LWTdata/LWT_{0}/lulinLWT/{0}-000.txt".format(date)) != []:
            with open("D:/LWTdata/LWT_{0}/lulinLWT/{0}-000.txt".format(date), 'r') as file:
                lines = file.readlines()
            neoEnd = int([line for line in lines if '|' in line][0].split('|')[-1].split(' ')[-9])
        else:
            pass
        
        nowHr, nowMin, nowSec = nowTime()
        hr_now = nowHr + nowMin/60 + nowSec/3600
        if nowHr <= 16:
            hr_now += 24
        else:
            pass
        
        # If the present time does not exceed the end time of the ToO script, restart and continue the ToO observation;
        # besides, if the NEO script exists and the present time does not exceed the end time of it, run it;
        # otherwise, run other user's script.
        if hr_now < (obsEnd+8):
            run_dlg['ComboBoxEx'].type_keys("D:\\LWTdata\\LWT_{0}\\lulinLWT\\{0}-{1}_TOO.txt".format(date, tooNameAbr))
            run_dlg['&Open'].click()
            time.sleep(300)
            reboot()
        elif (glob("D:/LWTdata/LWT_{0}/lulinLWT/{0}-000.txt".format(date)) != []) and (hr_now < neoEnd+8):
            run_dlg['ComboBoxEx'].type_keys("D:\\LWTdata\\LWT_{0}\\lulinLWT\\{0}-000.txt".format(date))
            run_dlg['&Open'].click()
            time.sleep(300)
            reboot()
        elif (glob("C:/Users/User/Documents/ACP Astronomy/Plans/cngeow*LWT.txt") != []) and (hr_now < obsOff+8):
            cngeow = glob("C:/Users/User/Documents/ACP Astronomy/Plans/cngeow*LWT.txt")[0].split('\\')[1]
            run_dlg['ComboBoxEx'].type_keys(cngeow)
            time.sleep(3)
            run_dlg['&Open'].click()
            time.sleep(300)
            reboot()
        else:
            run_dlg['Cancel'].click()
    except:
        time.sleep(300)
        reboot()

# Send an email.
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
    server.login(login, password)
    problems = server.sendmail(from_addr, to_addr_list, message)
    server.quit()
    return problems

if __name__ == '__main__':
    # Collect some useful observational parameters for creating the ToO script.
    usrName = input("What is your name?(ex: smoBEE)\n>>> ")
    usrEmail = input("What is your email?(ex: smoBEE@astro.ncu.edu.tw)\n>>> ")
    tooName = input("What is target's name?(ex: 2004 DV24)\n>>> ")
    tooNote = input('Leave a note?(ex: V17.1 & 0.061-0.064"/s)\n>>> ')
    tooBand = input("Which passband(s)?(ex: B,V,R,I)\n>>> ")
    tooBin = input("What binning(s)?(ex: 1,2,9,1 -> Max=16)[Please follow the sequence of passband(s)]\n>>> ")
    tooRead = input("Which readout mode?(Type: 1 MHz/8 MHz -> Cost: 30s/10s)\n>>> ")
    tooTrack = input("Track target during exposures?(Type: T/F)\n>>> ")
    tooExp = input("Exposure time(s) in sec?(ex: 60,50,40,30 -> PixelScale=1.22\")[Please follow the sequence of passband(s)]\n>>> ")
    tooCnt = input("Frames?(ex: 100,100,100,100)[Please follow the sequence of passband(s)]\n>>> ")

    # Different formats of today's date.
    date = datetime.now().strftime("%Y%m%d")
    dateWP = datetime.now().strftime("%Y %m %d")

    # Set basic information of the LWT and Sun
    long = "120:52:23.7"
    lat = "23:28:07.6"
    alt = "2860."
    LWT = ephem.Observer()
    LWT.lon, LWT.lat, LWT.elevation, LWT.horizon = long, lat, float(alt), "-18" 
    Sun = ephem.Sun()
    Sun.compute(epoch='2000')

    # The beginning and the end of observation time in consideration of astronomical twilight.
    obsOn = str(LWT.next_setting(Sun)).split(' ')[1].split(':')[0]
    obsEnd_hr = int(str(LWT.next_rising(Sun)).split(' ')[1].split(':')[0])
    obsEnd_min = int(str(LWT.next_rising(Sun)).split(' ')[1].split(':')[1])
    obsEnd_sec = int(str(LWT.next_rising(Sun)).split(' ')[1].split(':')[2])
    obsOff = obsEnd_hr + obsEnd_min/60 + obsEnd_sec/3600

    try:
        print("Scrawling 'Minor Planet & Comet Ephemeris Service' webpage of the MPC!")
        payload = {'ty':'e', 'TextArea':tooName, 'd':dateWP, 'l':'', 'i':'1', 'u':'h', 'uto':'0', 'c':'D37', 'long':'', 'lat':'', 'alt':'', 'raty':'d'
                   , 's':'t', 'm':'s', 'igd':'y', 'ibh':'y', 'adir':'N', 'oed':'', 'e':'-2', 'resoc':'', 'tit':'', 'bu':'', 'ch':'c', 'ce':'f', 'js':'f'}
        res = requests.post("https://cgi.minorplanetcenter.net/cgi-bin/mpeph2.cgi", data = payload)
        soup = BeautifulSoup(res.text, 'lxml')

        # Obtain today's observable ephemerides of the target.
        ephems = [i for i in soup.select('pre')[0].text.split('\n') if dateWP in i]
        if '  ' not in ephems[0].split('   ')[6]:
            ephemsOK = [i for i in ephems if (int(i.split('   ')[5].split('  ')[1]) >= 40) and (i.split(' ')[3][:2] >= obsOn)]
        else:
            ephemsOK = [i for i in ephems if (int(i.split('   ')[6].split('  ')[1]) >= 40) and (i.split(' ')[3][:2] >= obsOn)]
        print("Today's ephemeride when altitude is above 40 degrees!\n")
        print(ephemsOK)

        # Email users of the beginning time and the end time of their target's observation.
        obsBegin = int(ephemsOK[0].split(' ')[3].strip('0'))
        obsEnd = int(ephemsOK[-1].split(' ')[3].strip('0'))
        sendemail(from_addr    = 'lwt@gm.astro.ncu.edu.tw', 
                  to_addr_list = [usrEmail],
                  cc_addr_list = [], 
                  subject      = '{} - [{}] LWT ToO Observation'.format(datetime.now().strftime("%Y-%b-%d %H:%M:%S"), usrName),
                  message      = "Dear {},\n\nYour observation of {} will begin from UTC{} to UTC{}!\nMerci beaucoup!\n\nAmuse-toi bien,\nThe LWT Automation System\nemail: lwt@gm.astro.ncu.edu.tw",
                  login        = 'lwt@gm.astro.ncu.edu.tw', 
                  password     = '')
        
        # Basic information of the ACP script.
        TITLE = "; NEO_TOO_OBS\n"
        NAME = "; {}\n".format(usrName)
        INSTTT = "; IANCU, Taoyuan, TAIWAN\n"
        DATE = "; {}\n".format(datetime.now().strftime("%Y-%b-%d %H:%M:%S"))
        NOTE = "; {}\n;\n".format(tooNote)
        
        # Essential directives of the ACP script.
        FILTER = "#FILTER {}\n".format(tooBand)
        BIN = "#BINNING {}\n".format(tooBin)
        READOUT = "#READOUTMODE {}\n".format(tooRead)
        AUTOFOCUS = "#AUTOFOCUS\n;\n"
        if tooTrack == 'T':
            TRACKON = "#TRACKON\n;\n"
            TRACKOFF = "#TRACKOFF\n;\n"
        else:
            TRACKON = ""
            TRACKOFF = ""
        EXP = "#INTERVAL {}\n".format(tooExp)
        CNT = "#COUNT {}\n".format(tooCnt)
        DIR = "#DIR D:/LWTdata/LWT_{}/lulinLWT/neo/{}\n".format(date, tooName)

        # Wait until 15:24 to check whether the NEO script exists or not.
        # If the NEO script exists, set the "CHAIN" directive to it;
        # otherwise, chain to Prof. Ngeow's script.
        nowHour, nowMin, nowSec = nowTime()
        waitTime = 15.4*3600 - (int(nowHour)*3600 + int(nowMin)*60 + int(nowSec))
        if waitTime > 0:
            print("Wait until 15:30 for checking whether there is today's script!")
            time.sleep(waitTime)
        else:
            pass
        if glob("D:/LWTdata/LWT_{0}/lulinLWT/{0}-000.txt".format(date)) != []:
            CHAIN = "#CHAIN D:/LWTdata/LWT_{0}/lulinLWT/{0}-000.txt".format(date)
        elif glob("C:/Users/User/Documents/ACP Astronomy/Plans/cngeow*LWT.txt") != []:
            cngeowPaths = glob("C:/Users/User/Documents/ACP Astronomy/Plans/cngeow*LWT.txt")
            cngeowModTimes = [os.path.getctime(i) for i in cngeowPaths]
            cngeow = cngeowPaths[cngeowModTimes.index(max(cngeowModTimes))].split('\\')[1]
            CHAIN = "#CHAIN C:/Users/User/Documents/ACP Astronomy/Plans/{}".format(cngeow)
        else:
            CHAIN = ''
        
        # Create a line of orbital elements in target specification format.
        tooNameAbr = tooName.replace(' ','')
        orbits = ""
        for ephem in ephemsOK:
            orbits += ephem.split('     ')[0].replace('0000   ', '  ').replace('  ', '    ')+'|'
        neoOrbit = (tooNameAbr + ' '*(11-len(tooNameAbr)) + orbits)[:-1] + '\n;\n'

        # Create a directory for storing the ToO script.
        directory = os.path.dirname("D:/LWTdata/LWT_{}/lulinLWT/".format(date))
        os.makedirs(directory, exist_ok = True)
        with open("D:/LWTdata/LWT_{0}/lulinLWT/{0}-{1}_TOO.txt".format(date, tooNameAbr), 'a') as file:
            file.write(TITLE+NAME+INSTTT+DATE+NOTE+FILTER+BIN+READOUT+AUTOFOCUS+TRACKON+EXP+CNT+DIR+neoOrbit+TRACKOFF+CHAIN)
        print("The script is stored at 'D:/LWTdata/LWT_{0}/lulinLWT/{0}-{1}_TOO.txt'".format(date, tooNameAbr))

        # Wait to begin the ToO observation.
        nowHour, nowMin, nowSec = nowTime()
        waitTime = (obsBegin+8)*3600 - (int(nowHour)*3600 + int(nowMin)*60 + int(nowSec))
        deadLine = (obsEnd+8)*3600 - (int(nowHour)*3600 + int(nowMin)*60 + int(nowSec))
        if deadLine > 0:
            if waitTime > 0:
                print("Please wait for {}s to begin the observation!".format(waitTime))
                time.sleep(waitTime)
            else:
                pass
        else:
            print("Today's observable time had passed!\nPlease choose another TOO or wait until tomorrow.")

        # Connect to the windows of the ACP and the "Dome Control" panel.
        acp_app = pywinauto.Application(backend='uia').connect(path=r"C:\Program Files (x86)\ACP Obs Control\acp.exe")
        acp_dlg = acp_app['ACP Observatory Control Software']
        dome_app, dome_dlg = appConnect('ACP Dome Control', 'ThunderRT6FormDC')

        # If the ACP is not working, open the dome; otherwise, abort the running script.
        try:
            print("Unpark then open the dome!")
            dome_dlg['Unpark/Unhome'].click()
            time.sleep(1)
            dome_dlg['Open'].click()
        except:
            print("Abort the running script!")
            acp_dlg.Abort.click_input()

        # Choose the ToO script to begin the observations.
        print("Select 'AcquireImages.js' mode!")
        acp_dlg['Select the Script ...'].click_input()
        time.sleep(3)
        script_app, script_dlg = appConnect('ACP Observatory Control Software - Select script to run', '#32770')
        script_dlg['ComboBoxEx'].type_keys('AcquireImages.js')
        time.sleep(1)
        script_dlg['&Open'].click()
        print("Choose TOO's script!")

        reboot()

    # If there are errors occur, emailing users about the error message encountered in Python.
    except Exception as e:
        sendemail(from_addr    = 'lwt@gm.astro.ncu.edu.tw', 
                  to_addr_list = [usrEmail],
                  cc_addr_list = [], 
                  subject      = '[ERROR] autoTOOobs ({})'.format(datetime.now().strftime("%Y-%b-%d %H:%M:%S")), 
                  message      = "Error on line {}: [{}] {}\nPlease contact Huang Jian-Fong(smoBEE@astro.ncu.edu.tw) to fix the problem!".format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e),
                  login        = 'lwt@gm.astro.ncu.edu.tw', 
                  password     = '')
