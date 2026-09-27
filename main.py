import os
from dotenv import load_dotenv
from src.processing import DataProcessor

load_dotenv()

userdb = os.getenv('DB_USER')
passworddb = os.getenv('DB_PWD')
hostdb = os.getenv('DB_HOST')
portdb = os.getenv('DB_PORT')
namedb = os.getenv('DB_NAME')

processor = DataProcessor(userdb, passworddb, hostdb, portdb, namedb)

processor.load_data_sql()
processor.load_data_tenge()
processor.data_to_workable()
processor.create_profile()
processor.anailz()
processor.correl()

print("В выборке 20 609 пользователей, из них 59,6% совершили повторный заказ. Наиболее заметная связь с количеством заказов наблюдается у среднего интервала между заказами. Устройство, тип первого мероприятия и регион практически не связаны с повторными покупками. Проверенные гипотезы о влиянии типа мероприятия и активности региона на Retention не подтвердились.")