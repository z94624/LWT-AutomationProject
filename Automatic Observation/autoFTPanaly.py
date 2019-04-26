import shutil, sys
from glob import glob
from datetime import datetime, timedelta

yesterday = (datetime.now() - timedelta(days = 1)).strftime("%Y%m%d")

lwtDir = glob("/AutoFTP/LWT_{}/*LWT*".format(yesterday))
if lwtDir != []:
	shutil.copytree(lwtDir[0], "/LWTdata/LWT_{}/lulinLWT".format(yesterday))
else:
	sys.exit()
