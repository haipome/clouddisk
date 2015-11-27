import os
import sys

abspath = os.path.dirname(__file__)
sys.path.append(abspath)
os.chdir(abspath)

from app import app as application
