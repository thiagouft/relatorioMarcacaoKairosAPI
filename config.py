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

def get_local_now():
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(Config.APP_TIMEZONE)
        return datetime.datetime.now(tz)
    except Exception:
        tz = datetime.timezone(datetime.timedelta(hours=Config.TIMEZONE_OFFSET))
        return datetime.datetime.now(tz)

def fix_utf8_mojibake(text: str) -> str:
    """
    Corrige textos que sofreram codificação dupla UTF-8 (mojibake)
    Exemplo: 'ImportaÃ§Ã£o' -> 'Importação', 'CONSÃ“RCIO' -> 'CONSÓRCIO', 'FÃ©rias' -> 'Férias'
    """
    if not text or not isinstance(text, str):
        return text
    
    mojibake_indicators = ('Ã§', 'Ã£', 'Ã©', 'Ã“', 'Ã¡', 'Ã³', 'ÃŠ', 'Ãª', 'Ã¢', 'Ãµ', 'Ã\xa0', 'Ã\x87', 'Ã\x83', 'Ã\x81', 'Ã\x89', 'Ã\x8d', 'Ã\x93', 'Ã\x9a', 'Ãº', 'Ã\xba', 'Ã\xad')
    
    if any(m in text for m in mojibake_indicators):
        try:
            return text.encode('cp1252').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            try:
                return text.encode('latin1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    return text

