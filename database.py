# database.py

# Importa a biblioteca para interagir com o banco de dados SQLite.
import sqlite3
# Importa a biblioteca para trabalhar com data e hora.
import datetime
# Importa as configurações definidas no projeto.
import config

def inicializar_db():
    """
    Cria e inicializa o banco de dados e as tabelas, se não existirem.
    """
    # Conecta ao arquivo de banco de dados definido no config.
    conn = sqlite3.connect(config.DB_NAME)
    # Cria um cursor para executar comandos SQL.
    cursor = conn.cursor()

    # Define e executa o comando para criar a tabela 'scans'.
    # Esta tabela armazena um registro para cada vez que a rede é escaneada.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL
        )
    ''')

    # Define e executa o comando para criar a tabela 'devices'.
    # Esta tabela armazena os detalhes de cada dispositivo encontrado em um scan.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER,
            ip TEXT NOT NULL,
            mac TEXT,
            status TEXT,
            producer TEXT,
            latency_ms REAL,
            open_ports TEXT,
            snmp_name TEXT,
            snmp_description TEXT,
            FOREIGN KEY (scan_id) REFERENCES scans (id)
        )
    ''')

    # Confirma (commita) a criação das tabelas no banco de dados.
    conn.commit()
    # Fecha a conexão com o banco de dados.
    conn.close()

def salvar_resultado_scan(devices_list):
    """
    Salva a lista de dispositivos de uma varredura no banco de dados.
    """
    # Conecta ao banco de dados.
    conn = sqlite3.connect(config.DB_NAME)
    # Cria um cursor.
    cursor = conn.cursor()

    # Obtém o timestamp atual para registrar o momento do scan.
    now = datetime.datetime.now()
    # Insere um novo registro na tabela 'scans' e obtém seu ID.
    cursor.execute("INSERT INTO scans (timestamp) VALUES (?)", (now,))
    scan_id = cursor.lastrowid

    # Itera sobre a lista de dispositivos encontrados para salvá-los.
    for device in devices_list:
        # Define a query SQL para inserir um dispositivo.
        query = '''
            INSERT INTO devices (scan_id, ip, mac, status, producer, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        '''
        # Prepara os dados do dispositivo para inserção.
        device_data = (
            scan_id,
            device.get('ip'),
            device.get('mac'),
            device.get('status'),
            device.get('producer'),
            device.get('latency')
        )
        # Executa a query para inserir o dispositivo.
        cursor.execute(query, device_data)

    # Confirma (commita) todas as inserções.
    conn.commit()
    # Fecha a conexão.
    conn.close()

def get_last_scan_devices(only_online=False):
    """
    Busca e retorna os dispositivos do último scan realizado.
    """
    # Conecta ao banco de dados.
    conn = sqlite3.connect(config.DB_NAME)
    # Configura o retorno das linhas como dicionários para facilitar o acesso.
    conn.row_factory = sqlite3.Row
    # Cria um cursor.
    cursor = conn.cursor()

    # Encontra o ID do scan mais recente ordenando por ID em ordem decrescente.
    cursor.execute("SELECT id FROM scans ORDER BY id DESC LIMIT 1")
    last_scan_row = cursor.fetchone()

    # Retorna uma lista vazia se nenhum scan foi encontrado.
    if not last_scan_row:
        return []

    # Extrai o ID do último scan.
    last_scan_id = last_scan_row['id']

    # Monta a query base para buscar os dispositivos do último scan.
    query = "SELECT * FROM devices WHERE scan_id = ?"
    params = [last_scan_id]

    # Adiciona uma condição para filtrar apenas dispositivos online, se solicitado.
    if only_online:
        query += " AND status = 'online'"

    # Executa a query final para buscar os dispositivos.
    cursor.execute(query, params)
    # Obtém todos os resultados da consulta.
    rows = cursor.fetchall()
    # Fecha a conexão.
    conn.close()

    # Converte os resultados (objetos Row) em uma lista de dicionários e retorna.
    return [dict(row) for row in rows]