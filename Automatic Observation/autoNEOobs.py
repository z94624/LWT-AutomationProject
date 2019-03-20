import pywinauto, time, ephem, smtplib, sys
from datetime import datetime
from glob import glob

# Obtain the present time in hours.
def nowHour():
    nowHr = int(datetime.now().strftime("%H"))
    nowMin = int(datetime.now().strftime("%M"))
    nowSec = int(datetime.now().strftime("%S"))
    return nowHr + nowMin/60 + nowSec/3600

# Connect to the window of opened software.
def appConnect(winTitle, winClass):
    win_app = pywinauto.Application().connect(title_re=winTitle, class_name=winClass)
    win_dlg = win_app[winTitle]
    return win_app, win_dlg

# If software is not running, then open the software and connect to it; otherwise, just connect to it.
def appCheck(winKey, backEnd, appPath, winTitle):
    win = [window for window in windows if winKey in str(window)]
    if win == []:
        win_app = pywinauto.Application(backend=backEnd).start(appPath)
        time.sleep(5)
    else:
        win_app = pywinauto.Application(backend=backEnd).connect(path=appPath)
    win_dlg = win_app[winTitle]
    return win_app, win_dlg

# Restart the ACP script which was interrupted thanks to the bad weather.
def reboot():
    try:
        # Click "Run" button of the ACP to select a script from "Select a plan file" dialog.
        acp_dlg.Run.click_input()
        time.sleep(3)
        run_app, run_dlg = appConnect('Select a plan file', '#32770')
        
        # If the ToO script exists, store the beginning time of the ToO observation.
        if glob("D:/LWTdata/LWT_{}/lulinLWT/*_TOO.txt".format(date)) != []:
            with open("D:/LWTdata/LWT_{}/lulinLWT/*_TOO.txt".format(date), 'r') as file:
                lines = file.readlines()
            tooBegin = int([line for line in lines if '|' in line][0].split('|')[0].split(' ')[-9])
        else:
            tooBegin = obsStart

        hr_now = nowHour()
        if int(datetime.now().strftime("%H")) <= 16:
            hr_now += 24
        else:
            pass
        
        # If the present time is before the beginning time of the ToO observation, keep running the NEO scipt;
        # besides, if it is before the beginning of dawn, then run other user's script; 
        # otherwise, stop continuing the observations.
        if (glob("D:/LWTdata/LWT_{0}/lulinLWT/{0}-000.txt".format(date)) != []) and (hr_now < tooBegin+8):
            run_dlg['ComboBoxEx'].type_keys("D:\\LWTdata\\LWT_{0}\\lulinLWT\\{0}-000.txt".format(date))
            run_dlg['&Open'].Click()
            time.sleep(300)
            reboot()
        elif (glob("C:/Users/USER/Documents/ACP Astronomy/Plans/cngeow*LWT.txt") != []) and (hr_now < obsEndH+8):
            cngeow = glob("C:/Users/USER/Documents/ACP Astronomy/Plans/cngeow*LWT.txt")[0].split('\\')[1]
            run_dlg['ComboBoxEx'].type_keys(cngeow)
            time.sleep(3)
            run_dlg['&Open'].Click()
            time.sleep(300)
            reboot()
        else:
            run_dlg['Cancel'].Click()
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
    # List all the windows of softwares.
    windows = pywinauto.findwindows.find_elements()

    # Different formats of today's date.
    date = datetime.now().strftime("%Y%m%d")
    dateDash = datetime.now().strftime("%m-%d-%Y")

    # Set basic information of the LWT and Sun
    longitude = "120:52:23.7"
    latitude = "23:28:07.6"
    altitude = "2860."
    LWT = ephem.Observer()
    LWT.lon, LWT.lat, LWT.elevation, LWT.horizon = longitude, latitude, float(altitude), "-18" 
    Sun = ephem.Sun()
    Sun.compute(epoch='2000')

    # The beginning time of astronomical dawn = it's time to take dawn flat.
    obsEnd_hr = int(str(LWT.next_rising(Sun)).split(' ')[1].split(':')[0])
    obsEnd_min = int(str(LWT.next_rising(Sun)).split(' ')[1].split(':')[1])
    obsEnd_sec = int(str(LWT.next_rising(Sun)).split(' ')[1].split(':')[2])
    obsEndH = obsEnd_hr + obsEnd_min/60 + obsEnd_sec/3600

    # The time when Sun rises = time to close the LWT.
    LWT.horizon = "0"
    obsStop_hr = int(str(LWT.next_rising(Sun)).split(' ')[1].split(':')[0])
    obsStop_min = int(str(LWT.next_rising(Sun)).split(' ')[1].split(':')[1])
    obsStop_sec = int(str(LWT.next_rising(Sun)).split(' ')[1].split(':')[2])
    obsStopH = obsStop_hr + obsStop_min/60 + obsStop_sec/3600

    # It's time to take dusk flat.
    LWT.horizon = "-5"
    duskBegin = str(LWT.next_setting(Sun)).split(' ')[1].split(':')[0]

    try:
        # Officina Stellare ATC02 Remote: connect to COM4 port and then open the shutter of primary mirror.
        officina_app, officina_dlg = appCheck('Officina Stellare - ATC Remote', 'win32', r"C:\Program Files (x86)\Officina Stellare\ATC-GUI.exe", 'Officina Stellare - ATC Remote v. 4.0.4.1')
        try:
            officina_dlg.Minimize()
            officina_dlg.Restore()
            officina_dlg['ComboBox2'].select('COM4')
            officina_dlg.Connect.Click()
        except:
            pass
        time.sleep(3)
        officina_dlg.Open.Click()

        # Connect to TheSky.
        sky_app, sky_dlg = appCheck('TheSkyX Professional Edition', 'uia', r"C:\Program Files (x86)\Software Bisque\TheSkyX Professional Edition\TheSkyX.exe", 'Lulin_20171215_RMS_7b* - TheSkyX Professional Edition')

        # ACP Observatory Control Software: connect to MaxIm DL ("Camera" tab) and TheSky ("Telescope" tab).
        acp_app, acp_dlg = appCheck('ACP Observatory Control Software', 'uia', r"C:\Program Files (x86)\ACP Obs Control\acp.exe", 'ACP Observatory Control Software')
        acp_dlg['Camera'].select()
        acp_camera = acp_dlg['Camera'].items()[0].texts()[0]
        if acp_camera == 'Connect':
            acp_dlg['Connect'].select()
            time.sleep(3)
        else:
            pass
        acp_dlg['Telescope'].select()
        acp_telescope = acp_dlg['Telescope'].items()[0].texts()[0]
        if acp_telescope == 'Connect':
            acp_dlg['Connect'].select()
            time.sleep(20)
        else:
            acp_dlg['Unpark'].select()

        # Connect to SkyAlert Weather Data System.
        skyalert_app, skyalert_dlg = appCheck('SkyAlert', 'win32', r"C:\Users\USER\AppData\Local\Apps\2.0\LN6Y3AZB.LZP\AY836CG1.8XC\skya..tion_c2ae2720de41edca_0001.0000_4b5dd41c1cfb41c9\SkyAlert.exe", 'SkyAlert')
        skyalert_dlg.Minimize()
        skyalert_dlg.Restore()
        time.sleep(1)
        
        # Open "Settings" tab and then "Program Settings" window of SkyAlert.
        skyalert_dlg.SetFocus()
        skyalert_dlg.TypeKeys("%s")
        skyalert_dlg.TypeKeys("P")
        time.sleep(1)
        
        # Open the "Save to..." dialog for saving Weather/Data File.
        skyset_app, skyset_dlg = appConnect(' Settings', 'WindowsForms10.Window.8.app.0.141b42a_r9_ad1')
        skyset_dlg['Save to...'].Click()
        time.sleep(1)

        # Save today's Weather/Data file.
        skydata_app, skydata_dlg = appConnect('Choose a path and file name to save the weather data file.', '#32770')
        skydata_dlg['ComboBox'].type_keys('{}'.format(dateDash))
        time.sleep(1)
        skydata_dlg['Save'].Click()
        skyset_dlg['Done'].Click()

        # Control the ACP to connect to today's Weather/Data file and keep monitoring the weather.
        acp_dlg['Weather'].select()
        acp_weather = acp_dlg['Weather'].items()[0].texts()[0]
        if acp_weather == 'Connect':
            acp_dlg['Setup...'].select()
            time.sleep(1)
            acppre_app, acppre_dlg = appConnect('ACP Preferences', 'ThunderRT6FormDC')
            acppre_dlg['Setup Weather Server...'].click_input()
            time.sleep(1)
            wea_app, wea_dlg = appConnect('Select Clarity log file', '#32770')
            wea_dlg['ComboBox2'].select('All files (*.*)')
            time.sleep(1)
            wea_dlg['ComboBoxEx'].type_keys('{}.txt'.format(dateDash))
            time.sleep(1)
            wea_dlg['&Open'].Click()
            acppre_dlg['OK'].Click()
            time.sleep(1)
            acp_dlg['Weather'].select()
            acp_dlg['Connect'].select()
        else:
            pass

        # Open the "Dome Control" panel of the ACP.
        acp_dlg['Dome Control'].click_input()

        # FocusMax: connect to MaxIm DL.
        focus_app, focus_dlg = appCheck('FocusMax', 'win32', r"C:\Program Files (x86)\FocusMax\FocusMax.exe", 'FocusMax   LWT_20171017')
        focus_stat = focus_dlg['Edit7'].texts()[0]
        if focus_stat == 'Not Connected':
            focus_dlg['Connect'].Click()
            focus_dlg['Connect'].Click()
        else:
            pass

        # It's time for dusk flat.
        nowHR = nowHour()
        if (int(duskBegin)+8+1 - nowHR) > 0: # 1hr bearable time
            if (int(duskBegin)+8 - nowHR) > 0:
                time.sleep((int(duskBegin)+8 - nowHR)*3600)
            else:
                pass
            
            # Open dome.
            dome_app, dome_dlg = appConnect('ACP Dome Control', 'ThunderRT6FormDC')
            try:
                dome_dlg['Unpark/Unhome'].Click()
                time.sleep(1)
            except:
                pass
            dome_dlg['Open'].Click()
            
            # Run the AutoFlat system of the ACP.
            acp_dlg['Select the Script ...'].click_input()
            time.sleep(3)
            script_app, script_dlg = appConnect('ACP Observatory Control Software - Select script to run', '#32770')
            script_dlg['ComboBoxEx'].type_keys('AutoFlat.vbs')
            script_dlg['&Open'].Click()
            acp_dlg.Run.click_input()
        else:
            pass

        # It's time to follow up the NEOs.
        hr_now = nowHour()
        if glob("D:/LWTdata/LWT_{0}/lulinLWT/{0}-000.txt".format(date)) != []:
            with open("D:/LWTdata/LWT_{0}/lulinLWT/{0}-000.txt".format(date)) as file:
                lines = file.readlines()
            obsStart = int([line for line in lines if '|' in line][0].split('|')[0].split(' ')[-9])
        else:
            obsStart = 12
        if int(datetime.now().strftime("%H")) > 16:
            if (obsStart+8-0.25 - hr_now) > 0:
                time.sleep((obsStart+8-0.25 - hr_now)*3600)
            else:
                pass
        else:
            if ((obsStart+8-0.25) - (hr_now+24)) > 0:
                time.sleep(((obsStart+8-0.25) - (hr_now+24))*3600)
            else:
                pass
        
        # Abort the auto-flat process, and then run the NEO script.
        acp_dlg.Abort.click_input()
        try:
            acp_dlg['Select the Script ...'].click_input()
            time.sleep(3)
            script_app, script_dlg = appConnect('ACP Observatory Control Software - Select script to run', '#32770')
            
            script_dlg['ComboBoxEx'].type_keys('AcquireImages.js')
            time.sleep(1)
            script_dlg['&Open'].Click()
            
            reboot()
        except:
            pass

        # It's time for dawn flat.
        hr_now = nowHour()
        if int(datetime.now().strftime("%H")) > 16:
            if (obsEndH+8 - hr_now) > 0:
                time.sleep((obsEndH+8 - hr_now)*3600)
            else:
                pass
        else:
            if ((obsEndH+8) - (hr_now+24)) > 0:
                time.sleep(((obsEndH+8) - (hr_now+24))*3600)
            else:
                pass
        try:
            dome_dlg['Open'].Click()
        except:
            acp_dlg.Abort.click_input()
        
        # Run the AutoFlat system of the ACP.
        acp_dlg['Select the Script ...'].click_input()
        time.sleep(3)
        script_app, script_dlg = appConnect('ACP Observatory Control Software - Select script to run', '#32770')
        script_dlg['ComboBoxEx'].type_keys('AutoFlat.vbs')
        script_dlg['&Open'].Click()
        acp_dlg.Run.click_input()

        # It's time to close the LWT (before sunrise).
        hr_now = nowHour()
        if int(datetime.now().strftime("%H")) > 16:
            if (obsStopH+8 - hr_now) > 0:
                time.sleep((obsStopH+8 - hr_now)*3600)
            else:
                pass
        else:
            if ((obsStopH+8) - (hr_now+24)) > 0:
                time.sleep(((obsStopH+8) - (hr_now+24))*3600)
            else:
                pass
        acp_dlg.Abort.click_input()

        # Close dome.
        acp_dlg['Dome Control'].click_input()
        dome_app, dome_dlg = appConnect('ACP Dome Control', 'ThunderRT6FormDC')
        dome_dlg['Close'].Click()

        # Park telescope.
        acp_dlg['Telescope'].select()
        acp_dlg['Park'].select()

    # If there are errors occur, emailing users about the error message encountered in Python.
    except Exception as e:
        sendemail(from_addr    = 'lwt@astro.ncu.edu.tw', 
                  to_addr_list = ['smoBEE@astro.ncu.edu.tw'],
                  cc_addr_list = [], 
                  subject      = '[ERROR] autoNEOobs ({})'.format(datetime.now().strftime("%Y-%b-%d %H:%M:%S")), 
                  message      = "Error on line {}: [{}] {}".format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e),
                  login        = 'lwt@gm.astro.ncu.edu.tw', 
                  password     = '')
