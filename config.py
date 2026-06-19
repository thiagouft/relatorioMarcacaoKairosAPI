import os
import urllib
import datetime
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'uma_chave_secreta_muito_dificil'
    
    # Timezone Configuration (default: America/Sao_Paulo, UTC-3)
    APP_TIMEZONE = os.environ.get('APP_TIMEZONE', 'America/Sao_Paulo')
    TIMEZONE_OFFSET = int(os.environ.get('TIMEZONE_OFFSET', -3))

def get_local_now():
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(Config.APP_TIMEZONE)
        return datetime.datetime.now(tz)
    except Exception:
        tz = datetime.timezone(datetime.timedelta(hours=Config.TIMEZONE_OFFSET))
        return datetime.datetime.now(tz)
    
    # SQL Server Connection
    SERVER = os.environ.get('DB_SERVER')
    DATABASE = os.environ.get('DB_NAME')
    USERNAME = os.environ.get('DB_USER')
    PASSWORD = os.environ.get('DB_PASSWORD')
    DRIVER = '{ODBC Driver 17 for SQL Server}'
    
    # SQLAlchemy URI
    params = urllib.parse.quote_plus(f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD}')
    SQLALCHEMY_DATABASE_URI = f"mssql+pyodbc:///?odbc_connect={params}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Kairos API
    KAIROS_API_URL = "https://www.dimepkairos.com.br/RestServiceApi/Appointment/GetAppointmentsV2"
    KAIROS_SEARCH_PEOPLE_URL = "https://www.dimepkairos.com.br/RestServiceApi/People/SearchPeople"
    KAIROS_HEADERS = {
        "Content-Type": "application/json",
        "key": os.environ.get('KAIROS_KEY'),
        "identifier": os.environ.get('KAIROS_IDENTIFIER'),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
