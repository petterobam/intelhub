import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app
application = create_app()
