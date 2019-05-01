import shutil, time, os, smtplib, sys
from glob import glob
from datetime import datetime, timedelta

def wait():
	nowH = int(datetime.now().strftime("%H"))
	nowM = int(datetime.now().strftime("%M"))
	nowS = int(datetime.now().strftime("%S"))
	if nowH < 15:
		nowH += 24
	else:
		pass
	return ((9+24)*3600 - (nowH*3600 + nowM*60 + nowS))

def neoSync(neoDirs):
	oldNeos, allNeos = [], []
	for Dir in neoDirs:
		oldNeos += [i.split('\\')[-1] for i in glob(r"\\192.168.8.2\AutoFTP\LWT_{}\lulinLWT\neo\{}\*".format(date, Dir.split('\\')[-1]))]
		allNeos += [i.split('\\')[-1] for i in glob(Dir + '\\*')]

	newNeos = [i for i in allNeos if i not in oldNeos]
	if newNeos != []:
		for neo in newNeos:
			shutil.copyfile("D:/LWTdata/LWT_{}/lulinLWT/neo/{}/{}".format(date, neo.split('-')[0], neo), r"\\192.168.8.2\AutoFTP\LWT_{}\lulinLWT\neo\{}\{}".format(date, neo.split('-')[0], neo))
	else:
		pass

	time.sleep(300)

	if wait() > 0:
		neoSync(neoDirs)
	else:
		pass

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
	date = datetime.now().strftime("%Y%m%d")

	try:
		if glob("D:/LWTdata/LWT_{}/lulinLWT") != []:
			shutil.copytree("D:/LWTdata/LWT_{}/lulinLWT/others", r"\\192.168.8.2\AutoFTP\LWT_{}\lulinLWT\others")
			neoScripts = glob(r"D:\LWTdata\LWT_{0}\lulinLWT\{0}*".format(date))
			for script in neoScripts:
				shutil.copytree(script, r"\\192.168.8.2\AutoFTP\LWT_{}\lulinLWT\{}".format(date, script.split('\\')[-1]))

			neoDirs = [i for i in glob(r"D:\LWTdata\LWT_{}\lulinLWT\neo\*".format(date))]
			for Dir in neoDirs:
				directory = os.path.dirname(r"\\192.168.8.2\AutoFTP\LWT_{}\lulinLWT\neo\{}".format(date, Dir.split('\\')[-1])+'/')
				os.makedirs(directory, exist_ok = True)
			neoSync(neoDirs)
		else:
			if wait() > 0:
				time.sleep(wait())
			else:
				pass

		dirPaths = glob("D:/LWTdata/LWT_{}/*".format(date))
		for path in dirPaths:
			if 'geow' in path:
				shutil.copytree(path, r"\\192.168.8.2\AutoFTP\LWT_{}\cngeow".format(date))
			elif 'txt' in path:
				shutil.copytree(path, r"\\192.168.8.2\AutoFTP\LWT_{}\{}".format(date, path.split('\\')[-1].split('.')[0]))
			elif 'LWT' in path:
				pass
			else:
				shutil.copytree(path, r"\\192.168.8.2\AutoFTP\LWT_{}\{}".format(date, path.split('\\')[-1]))

	except Exception as e:
		sendemail(from_addr    = 'lwt@gm.astro.ncu.edu.tw',
			to_addr_list = ['smoBEE@astro.ncu.edu.tw'],
			cc_addr_list = [],
			subject      = '[ERROR] autoFTPobs ({})'.format(datetime.now().strftime("%Y-%b-%d %H:%M:%S")),
			message      = "Error on line {}: [{}] {}".format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e),
			login        = 'lwt@gm.astro.ncu.edu.tw',
			password     = '')
