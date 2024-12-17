import pendulum
from datetime import datetime, timedelta
from airflow.decorators import dag, task


@dag(
    schedule=timedelta(days=1),
    start_date=pendulum.datetime(2024, 12, 4, tz="UTC"),
    catchup=False,
    tags=["bgg"],
)
def bgg_top_games_list_z3():
    """
    ### Zadania polegające na pobraniu aktualnego zestawienia najlepiej ocenianych gier planszowych
    z serwisu BoardGameGeek.com w postaci dokumentu HTML, parsowanie i zapisanie w konkretnym formacie
    danych.
    Adres zestawienia: https://boardgamegeek.com/browse/boardgame
    """

    # @task.bash(cwd='../data/bgg/raw/')
    # powyższa linia nie zadziała w naszym przypadku, gdyż narzędzie cwd nie jest zainstalowane w naszym obrazie dockerowym
    # będzie więc używana pełna ścieżka
    @task.bash
    def extract():
        """
        #### Zadanie ekstrakcji danych. Tu można podejść do tego na kilka sposobów. Np. pobrać
        dane bezpośrednio z poziomu Pythona, ale dla, żeby pokazać szersze spektrum zadań,
        użyte zostanie inne podejście. Dane zostaną pobrane z pomocą BashOperator i polecenia curl.
        """
        base_path = '/home/spark/airflow/data/bgg/raw/'
        filepath = f'{base_path}bgg_z3_{datetime.strftime(datetime.now(), "%Y-%m-%d")}.html'
        command = f'curl -s https://boardgamegeek.com/browse/boardgame > {filepath} && echo {filepath}'

        return command

    @task()
    def transform(bgg_page_file: str):
        """
        #### Zadanie transformacji danych.
        """
        from bs4 import BeautifulSoup
        import csv
        import re

        csv_path = '/home/spark/airflow/data/bgg/csv/'

        print("-" * 100)
        print(f"Processing file: {bgg_page_file}")

        try:
            with open(bgg_page_file, 'r') as file:
                parsed_html = BeautifulSoup(file, 'html.parser')
        except OSError as err:
            raise OSError()

        # parsowanie tabeli i zapisanie danych jako json
        table_html = parsed_html.body.find('table', attrs={'class': 'collection_table'})

        rows = table_html.find_all('tr')
        data = []
        col_names = []
        for row_id, row in enumerate(rows):
            if row_id == 0:
                col_names = [ele.text.strip() for ele in row.find_all('th')]
                col_names.append('Description')
                col_names.remove('Shop')
                continue
            cols = [ele.text.strip() for ele in row.find_all('td')]

            if not cols or len(cols) < len(col_names) - 1:
                continue

            thumbnail = row.find('img')['src'] if row.find('img') else ''
            title = cols[col_names.index('Title')] if 'Title' in col_names else ''
            regex = re.search(r'\)\s*(.*)', title)
            description = regex.group(1) if regex else ''

            cols[col_names.index('Thumbnail image')] = thumbnail
            cols.append(description)
            if 'Shop' in col_names:
                del cols[col_names.index('Shop')]
            data.append([ele for ele in cols if ele])

        # zapisanie danych w formacie csv
        csv_filename = bgg_page_file.split('/')[-1].split('.')[0] + '.csv'
        try:
            with open(csv_path + csv_filename, 'w') as csvfile:
                bggwriter = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                bggwriter.writerow(col_names)
                bggwriter.writerows(data)
        except OSError as err:
            raise OSError()

        return csv_path + csv_filename

    @task
    def load(bgg_csv_file: str):
        import pandas as pd

        df = pd.read_csv(bgg_csv_file, header=0)
        print(df.info())
        print(df.head())

    @task.bash
    def move_processed_csv(bgg_csv_file: str):
        target_path = '/home/spark/airflow/data/bgg/processed/'
        command = f'mkdir -p {target_path} && mv {bgg_csv_file} {target_path}'
        return command

    bgg_page_of_the_day = extract()
    bgg_csv = transform(bgg_page_of_the_day)
    load(bgg_csv)
    move_processed_csv(bgg_csv)


bgg_top_games_list_z3()
