# database.py
"""
Módulo de gerenciamento do banco de dados SQLite.

Implementa camada de abstração para operações de persistência:
- Criação e inicialização de schema (tabelas Scans e Dispositivos)
- CRUD de scans e dispositivos de rede
- Queries para histórico e análise comparativa
- Gestão de snapshots com suporte a rollback

Banco: SQLite com foreign keys e relacionamento 1:N (Scan -> Dispositivos)
"""

import sqlite3
from datetime import datetime

DB_FILE = 'network_discovery.db'

def _get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DB_FILE)
    # Retorna as linhas como dicionários para facilitar o acesso por nome de coluna
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_db():
    """Cria as tabelas do banco de dados se elas não existirem."""
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scans (
            scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            device_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            ip TEXT,
            mac TEXT NOT NULL,
            status TEXT NOT NULL,
            snmp_name TEXT,
            producer TEXT, 
            role TEXT,
            open_ports TEXT,
            FOREIGN KEY (scan_id) REFERENCES scans (scan_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS known_devices (
            mac TEXT PRIMARY KEY,
            first_seen DATETIME NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("(Database: Banco de dados inicializado com sucesso.)")

def salvar_resultado_scan(devices):
    """
    Salva o resultado completo de um novo scan no banco de dados, criando um novo snapshot.
    """
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now()
    cursor.execute('INSERT INTO scans (timestamp) VALUES (?)', (now,))
    scan_id = cursor.lastrowid
    
    devices_to_insert = []
    known_devices_to_check = []
    
    for dev in devices:
        # Converte a lista de portas em uma string separada por vírgulas
        ports_str = ",".join(map(str, dev.get('open_ports', [])))
        devices_to_insert.append(
            (scan_id, dev.get('ip'), dev.get('mac'), dev.get('status'), 
             dev.get('snmp_name'), dev.get('producer'), dev.get('role'),
             ports_str)
        )
        if dev.get('mac'):
            known_devices_to_check.append((dev.get('mac'), now))

    if devices_to_insert:
        cursor.executemany(
            '''INSERT INTO devices (scan_id, ip, mac, status, snmp_name, producer, role, open_ports) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            devices_to_insert
        )

    if known_devices_to_check:
        cursor.executemany(
            'INSERT OR IGNORE INTO known_devices (mac, first_seen) VALUES (?, ?)',
            known_devices_to_check
        )
        
    conn.commit()
    conn.close()
    return scan_id


def _get_latest_scan_id():
    """Função auxiliar para obter o ID do scan mais recente."""
    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT scan_id FROM scans ORDER BY timestamp DESC LIMIT 1')
    result = cursor.fetchone()
    conn.close()
    return result['scan_id'] if result else None


def get_scan_history(limit=10):
    """
    Lista os últimos scans (snapshots) com contagens de dispositivos.
    Esta função substitui e unifica `list_snapshots` e a antiga `get_scan_history`.
    """
    conn = _get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT
            s.scan_id,
            s.timestamp,
            COUNT(d.device_id) AS total,
            SUM(CASE WHEN d.status = 'online' THEN 1 ELSE 0 END) AS online_count
        FROM scans s
        LEFT JOIN devices d ON s.scan_id = d.scan_id
        GROUP BY s.scan_id
        ORDER BY s.timestamp DESC
        LIMIT ?
    """
    cursor.execute(query, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_devices_for_scan_with_first_seen(scan_id=None):
    """
    Busca os dispositivos de um scan específico ou do último scan se o ID não for fornecido.
    Junta com a tabela known_devices para adicionar a data 'first_seen'.
    """
    if scan_id is None:
        scan_id = _get_latest_scan_id()
        if scan_id is None:
            return []
            
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT d.ip, d.mac, d.status, d.snmp_name, d.producer, d.role, d.open_ports, kd.first_seen
        FROM devices d
        LEFT JOIN known_devices kd ON d.mac = kd.mac
        WHERE d.scan_id = ?
        ORDER BY d.ip
    """
    cursor.execute(query, (scan_id,))
    rows = cursor.fetchall()
    conn.close()
    
    # Converte a string de portas de volta para lista
    devices = []
    for row in rows:
        device = dict(row)
        if device.get('open_ports'):
            device['open_ports'] = [int(p) for p in device['open_ports'].split(',') if p]
        else:
            device['open_ports'] = []
        devices.append(device)
    
    return devices

def get_changes_for_last_scan():
    """
    Compara os dois últimos scans para identificar dispositivos novos e que ficaram offline.
    """
    conn = _get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT scan_id FROM scans ORDER BY timestamp DESC LIMIT 2')
    scan_ids = [row['scan_id'] for row in cursor.fetchall()]
    
    if len(scan_ids) < 2:
        return {'new': get_devices_for_scan_with_first_seen(), 'offline': []}

    last_scan_id, prev_scan_id = scan_ids
    
    query_new = """
        SELECT d.ip, d.mac, d.status, d.snmp_name, d.producer, d.role, d.open_ports, kd.first_seen
        FROM devices d
        LEFT JOIN known_devices kd ON d.mac = kd.mac
        WHERE d.scan_id = ? AND d.mac NOT IN (SELECT mac FROM devices WHERE scan_id = ?)
    """
    cursor.execute(query_new, (last_scan_id, prev_scan_id))
    new_devices = []
    for row in cursor.fetchall():
        device = dict(row)
        if device.get('open_ports'):
            device['open_ports'] = [int(p) for p in device['open_ports'].split(',') if p]
        else:
            device['open_ports'] = []
        new_devices.append(device)
    
    query_offline = """
        SELECT d.ip, d.mac, d.status, d.snmp_name, d.producer, d.role, d.open_ports, kd.first_seen
        FROM devices d
        LEFT JOIN known_devices kd ON d.mac = kd.mac
        WHERE d.scan_id = ? AND d.status = 'online' AND d.mac NOT IN 
              (SELECT mac FROM devices WHERE scan_id = ? AND status = 'online')
    """
    cursor.execute(query_offline, (prev_scan_id, last_scan_id))
    offline_devices = []
    for row in cursor.fetchall():
        device = dict(row)
        if device.get('open_ports'):
            device['open_ports'] = [int(p) for p in device['open_ports'].split(',') if p]
        else:
            device['open_ports'] = []
        offline_devices.append(device)
    
    conn.close()
    return {'new': new_devices, 'offline': offline_devices}

def rollback_to_scan(scan_id):
    """
    Apaga todos os scans e dados de dispositivos mais recentes que o scan_id fornecido.
    """
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    # Apaga os registros de dispositivos dos scans mais novos
    cursor.execute('DELETE FROM devices WHERE scan_id > ?', (scan_id,))
    # Apaga os registros dos próprios scans
    cursor.execute('DELETE FROM scans WHERE scan_id > ?', (scan_id,))
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count