import pandas as pd
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
import seaborn as sns
from phik import phik_matrix

class DataProcessor:

    def create_revenue_rub(self, raw):
        if raw['currency_code'] == 'rub':
            return raw['revenue']
        else:
            rate = self.kzt_to_rub.loc[self.kzt_to_rub['data'] == raw['order_dt'], 'curs'].values
            return raw['revenue'] * rate[0]/100


    def __init__(self, userdb, passworddb, hostdb, portdb, namedb):
        self.userdb = userdb
        self.passworddb = passworddb
        self.hostdb = hostdb
        self.portdb = portdb
        self.namedb = namedb
        self.rates_path = "data/final_tickets_tenge_df.csv"


    def load_data_sql(self):
        db_config = {'user': self.userdb, # имя пользователя
                    'pwd': self.passworddb, # пароль
                    'host': self.hostdb,
                    'port': self.portdb, # порт подключения
                    'db': self.namedb # название базы данных
                    }

        connection_string = 'postgresql+psycopg2://{}:{}@{}:{}/{}'.format(
            db_config['user'],
            db_config['pwd'],
            db_config['host'],
            db_config['port'],
            db_config['db'],
        )

        engine = create_engine(connection_string)

        query = '''
        SELECT
        p.user_id,
        p.device_type_canonical,
        p.order_id,
        p.created_dt_msk AS order_dt,
        p.created_ts_msk AS order_ts,
        p.currency_code,
        p.revenue,
        p.tickets_count,
        (p.created_dt_msk::date - LAG(p.created_dt_msk::date) OVER (PARTITION BY p.user_id ORDER BY p.created_ts_msk)) AS days_since_prev,
        p.event_id,
        p.service_name,
        e.event_type_main,
        r.region_name,
        c.city_name
        FROM afisha.purchases p
        INNER JOIN afisha.events e ON p.event_id = e.event_id
        LEFT JOIN afisha.city c ON e.city_id = c.city_id
        LEFT JOIN afisha.regions r ON c.region_id = r.region_id
        WHERE e.event_type_main != 'фильм'
        AND p.device_type_canonical IN ('mobile', 'desktop')
        '''
        self.df = pd.read_sql_query(query, con=engine)

        self.df.info()
        self.origin_size = self.df.shape[0]
        self.df.head()

    def load_data_tenge(self):
        self.kzt_to_rub = pd.read_csv(self.rates_path)
        self.kzt_to_rub.info()
        self.kzt_to_rub.head()


    def data_to_workable(self):
        self.kzt_to_rub['data'] = pd.to_datetime(self.kzt_to_rub['data'])
        self.df['revenue_rub'] = self.df.apply(self.create_revenue_rub, axis=1)
        self.df.isna().sum()
        
        self.df['tickets_count'] = pd.to_numeric(self.df['tickets_count'], downcast = 'integer')
        self.df['event_id'] = pd.to_numeric(self.df['event_id'], downcast = 'integer')
        self.df['order_id'] = pd.to_numeric(self.df['order_id'], downcast = 'integer')
        for column in ['device_type_canonical', 'event_type_main', 'service_name']:
            print(f'\n Столбец: {column}')
            print('Уникальные значения:', self.df[column].unique())
            print('Количество пропусков:', self.df[column].isna().sum())
            print('Распределение значений:', self.df[column].value_counts(dropna=False))

        f, (ax_box, ax_hist) = plt.subplots(2, sharex=True,
            gridspec_kw={"height_ratios": (.15, .85)})
        sns.boxplot(data=self.df["revenue_rub"], orient="h", ax=ax_box)
        sns.histplot(data=self.df, x="revenue_rub", ax=ax_hist)
        ax_box.set_title('Диаграмма размаха для выручки')
        ax_box.set_ylabel('Выручка, руб.')
        plt.show()

        f, (ax_box, ax_hist) = plt.subplots(2, sharex=True, gridspec_kw={"height_ratios": (.15, .85)})
        sns.boxplot(data=self.df["tickets_count"], orient="h", ax=ax_box)
        sns.histplot(data=self.df, x="tickets_count", ax=ax_hist)
        ax_box.set_title('диаграмма размаха для количества купленных билетов')
        ax_box.set_ylabel('выручка')
        plt.show()
        
        self.df = self.df[self.df['revenue_rub'] < self.df['revenue_rub'].quantile(0.99)]
        self.df = self.df[self.df['tickets_count'] < self.df['tickets_count'].quantile(0.99)]
        f, (ax_box, ax_hist) = plt.subplots(2, sharex=True, gridspec_kw={"height_ratios": (.15, .85)})
        sns.boxplot(data=self.df["revenue"], orient="h", ax=ax_box)
        sns.histplot(data=self.df, x="revenue", ax=ax_hist)
        ax_box.set_title('диаграмма размаха для выручки')
        ax_box.set_ylabel('выручка')
        plt.show()
        
        self.zero_revenue = self.df[self.df['revenue_rub'] == 0]
        print(f"Количество заказов с нулевой выручкой: {len(self.zero_revenue)}")
        print(f"Доля от общего числа: {len(self.zero_revenue) / len(self.df) * 100:.2f}%")

        self.negative_revenue = self.df[self.df['revenue'] < 0]
        print(f"Количество записей с отрицательной выручкой: {len(self.negative_revenue)}")
        print(f"Процент от общего числа: {len(self.negative_revenue)/len(self.df)*100}%")

        self.df = self.df[self.df['revenue'] >= 0]
        full_duplicates = self.df.duplicated().sum()
        print(f"Полных дубликатов строк: {full_duplicates}")

        order_duplicates = self.df[self.df.duplicated(subset=['order_id'])]
        print(f"Дубликатов по order_id: {len(order_duplicates)}")

        order_duplicates = self.df[self.df.duplicated(subset=['order_ts', 'user_id'])]
        print(f"Дубликатов по времени заказа и id пользователя: {len(order_duplicates)}")

        self.df = self.df.drop_duplicates(subset=['order_ts', 'user_id'])


        print(f'Исходный размер: {self.origin_size}')
        print(f'Текущий размер: {self.df.shape[0]}')
        print(f'Отфильтровано {self.origin_size-self.df.shape[0]} строк ({round((1-self.df.shape[0]/self.origin_size)*100, 2)}%)')
        

    def create_profile(self):
        self.df = self.df.sort_values(by='order_ts')

        self.users = self.df.groupby('user_id').agg({
            'order_dt': ['first', 'last'],
            'device_type_canonical': 'first',
            'region_name': 'first',
            'event_type_main': 'first',
            'order_id': 'count',
            'revenue_rub': 'mean',
            'days_since_prev': 'mean'
        })

        self.users.columns = [
            'first_order_dt',
            'last_order_dt',
            'first_device_type_canonical',
            'first_region_name',
            'first_event_type_main',
            'num_of_orders',
            'avg_revenue',
            'avg_days_between_orders'
        ]

        self.users = self.users.assign(
            is_two=(self.users['num_of_orders'] >= 2).astype(int)
        ).reset_index()

        self.users.head()

        print(f'Общее число пользователей в выборке: {self.users.shape[0]}')
        total_revenue = (self.users['avg_revenue'] * self.users['num_of_orders']).sum()
        total_orders = self.users['num_of_orders'].sum()
        avg_revenue_per_order_correct = total_revenue / total_orders
        print(f'Средняя выручка с одного заказа (общая выручка / общее число заказов): {avg_revenue_per_order_correct:.2f} руб.')
        print(f'Доля пользователей, совершивших 2 и более заказа: {self.users["is_two"].mean():.2f}')

        self.users['num_of_orders'].describe()
        self.users['avg_days_between_orders'].describe()

        percentile_95 = self.users['num_of_orders'].quantile(0.95)
        size_before_filter = self.users.shape[0]
        print(f"95 процентиль: {percentile_95:.0f} заказов")  
        self.users = self.users[self.users['num_of_orders'] <= percentile_95]
        size_after = self.users.shape[0]
        print(f"Количество отфильтрованных пользователей: {size_before_filter-size_after} ({(1-size_after/size_before_filter)*100:.2f})%")
        self.users['num_of_orders'].describe()



    def anailz(self):
        group_by_first_event = self.users.groupby('first_event_type_main')['user_id'].count()
        pd.concat([group_by_first_event.rename('count'), (group_by_first_event / self.users.shape[0])], axis=1).sort_values(by='count', ascending=False)

        group_by_first_device = self.users.groupby('first_device_type_canonical')['user_id'].count()
        pd.concat([group_by_first_device, (group_by_first_device / self.users.shape[0])], axis=1)

        group_by_first_region = self.users.groupby('first_region_name')['user_id'].count()
        pd.concat([group_by_first_region.rename('count'), (group_by_first_region / self.users.shape[0])], axis=1).sort_values(by='count', ascending=False)

        event_retention = self.users.groupby('first_event_type_main').agg({
            'user_id': 'count',
            'is_two': 'mean'
        }).rename(columns={'user_id': 'total_users', 'is_two': 'retention_rate'})
        event_retention = event_retention.sort_values('retention_rate', ascending=False)
        print("Доля возвратов по жанрам:")
        print(event_retention)
        avg_retention = self.users['is_two'].mean()
        print(f"Среднее по выборке: {avg_retention:.1%}")

        device_retention = self.users.groupby('first_device_type_canonical').agg({
            'user_id': 'count',
            'is_two': 'mean'
        }).rename(columns={'user_id': 'total_users', 'is_two': 'retention_rate'})

        print("\nДоля возвратов по устройствам:")
        print(device_retention)

        region_retention = self.users.groupby('first_region_name').agg({
            'user_id': 'count',
            'is_two': 'mean'
        }).rename(columns={'user_id': 'total_users', 'is_two': 'retention_rate'})

        region_retention = region_retention.sort_values(by='total_users', ascending=False)
        region_retention = region_retention[:10]
        region_retention = region_retention.sort_values(by='retention_rate', ascending=False)

        print("\nДоля возвратов по регионам (топ-10):")
        print(region_retention)

        fig, axes = plt.subplots(2, 2, figsize=(20, 12))

        ax1 = axes[0, 0]
        ax1.bar(event_retention.index, event_retention['retention_rate'] * 100)
        ax1.set_ylabel('Доля возвратов (%)')
        ax1.set_title('По жанру мероприятия')

        ax2 = axes[0, 1]
        ax2.bar(device_retention.index, device_retention['retention_rate'] * 100)
        ax2.set_ylabel('Доля возвратов (%)')
        ax2.set_title('По типу девайса')

        ax3 = axes[1, 0]
        ax3.barh(region_retention.index, region_retention['retention_rate'] * 100)
        ax3.set_xlabel('Доля возвратов (%)')
        ax3.set_title('По региону')

        plt.show()

        region_retention = region_retention.sort_values(by='retention_rate', ascending=False)
        print(region_retention)
        region_retention = region_retention.sort_values(by='total_users', ascending=False)
        print('\n', region_retention)

        one_order_users = self.users[self.users['num_of_orders'] == 1]

        repeat_users = self.users[self.users['num_of_orders'] >= 2]

        print(f"Пользователей с 1 заказом: {len(one_order_users)}")
        print(f"Пользователей с 2+ заказами: {len(repeat_users)}")
        print(f"Всего пользователей: {len(self.users):,}")

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        ax1 = axes[0]
        ax1.hist(one_order_users['avg_revenue'], bins=25, alpha=0.5, label=f'1 заказ (n={len(one_order_users)})', color='red')
        ax1.hist(repeat_users['avg_revenue'], bins=25, alpha=0.5, label=f'2+ заказа (n={len(repeat_users)})', color='blue')
        ax1.set_xlabel('Средняя выручка с заказа (руб.)')
        ax1.set_ylabel('Количество пользователей')
        ax1.set_title('Распределение средней выручки (абсолютные значения)')
        ax1.legend()
        ax1.grid(True)

        ax2 = axes[1]
        ax2.hist(one_order_users['avg_revenue'], bins=25, alpha=0.5, density=True, label='1 заказ', color='red')
        ax2.hist(repeat_users['avg_revenue'], bins=25, alpha=0.5, density=True, label='2+ заказа', color='blue')
        ax2.set_xlabel('Средняя выручка с заказа (руб.)')
        ax2.set_ylabel('Плотность распределения')
        ax2.set_title('Распределение средней выручки (распределение)')
        ax2.legend()
        ax2.grid(True)
        plt.show()

        self.users['first_order_dayofweek'] = self.users['first_order_dt'].dt.dayofweek
        weekday_names = {
            0: 'Понедельник',
            1: 'Вторник', 
            2: 'Среда',
            3: 'Четверг',
            4: 'Пятница',
            5: 'Суббота',
            6: 'Воскресенье'
        }
        def create_weekday_name(num_of_day):
            return weekday_names[num_of_day]
        self.users['first_order_dayofweek'] = self.users['first_order_dayofweek'].apply(create_weekday_name)

        weekday_analysis = self.users.groupby('first_order_dayofweek').agg({
            'user_id': 'count',
            'is_two': 'mean'
        }).rename(columns={'user_id': 'total_users', 'is_two': 'retention_rate'})

        weekday_analysis['share'] = weekday_analysis['total_users'] / len(self.users) * 100
        weekday_analysis.sort_values(by='retention_rate', ascending=False, inplace=True)

        fig, axes = plt.subplots(2, 1, figsize=(14, 10))
        ax1 = axes[0]
        ax1.bar(weekday_analysis.index, weekday_analysis['total_users'])
        ax1.set_xlabel('День недели')
        ax1.set_ylabel('Количество пользователей')
        ax1.set_title('Распределение пользователей по дню первой покупки')
        ax1.grid(True)

        ax2 = axes[1]
        ax2.bar(weekday_analysis.index, weekday_analysis['retention_rate'] * 100)
        ax2.set_xlabel('День недели')
        ax2.set_ylabel('Доля возвратов (%)')
        ax2.set_title('Доля повторных покупок по дню первой покупки')
        plt.show()
        weekday_analysis


    def correl(self):
        df_corr = self.users[['num_of_orders', 
                        'first_device_type_canonical',
                        'first_event_type_main', 
                        'first_region_name',
                        'avg_revenue',
                        'avg_days_between_orders']].copy()
        corr_matrix = df_corr.phik_matrix()
        corr_matrix = corr_matrix.loc[corr_matrix.index != 'num_of_orders'][['num_of_orders']]
        corr_matrix = corr_matrix.sort_values(by='num_of_orders', ascending=False)
        plt.figure(figsize=(4, 8))

        sns.heatmap(corr_matrix,
                    annot=True, 
                    fmt='.3f', 
                    cmap='coolwarm', 
                    linewidths=0.5, 
                    cbar=False,
                )

        plt.title('Тепловая карта коэффициента phi_k \n для признаков с количеством заказов')
        plt.xlabel('Количество заказов')
        plt.ylabel('Признаки')
        plt.show()

        self.users.loc[self.users['num_of_orders'] == 1, 'order_segment'] = '1 заказ'
        self.users.loc[self.users['num_of_orders'] == 2, 'order_segment'] = '2 заказа'
        self.users.loc[self.users['num_of_orders'].between(3, 4), 'order_segment'] = '3-4 заказа'
        self.users.loc[self.users['num_of_orders'] >= 5, 'order_segment'] = '5+ заказов'

        segments = ['3-4 заказа', '5+ заказов']

        fig, axes = plt.subplots(1, 2, figsize=(12, 6))
        for i, segment in enumerate(segments):
            seg_data = self.users[self.users['order_segment'] == segment][[
                'num_of_orders',
                'first_device_type_canonical',
                'first_event_type_main',
                'first_region_name',
                'avg_revenue',
                'avg_days_between_orders'
            ]].copy()

            corr_seg = seg_data.phik_matrix()
            corr_seg = corr_seg.loc[
                corr_seg.index != 'num_of_orders'
            ][['num_of_orders']]

            corr_seg = corr_seg.sort_values(
                by='num_of_orders',
                ascending=False
            )
            sns.heatmap(corr_seg, annot=True, fmt='.3f', cmap='coolwarm',linewidths=0.5,
                        cbar=False, ax=axes[i], vmin=0, vmax=0.5)
            axes[i].set_title(f'Сегмент: {segment}')
        plt.tight_layout()
        plt.show()