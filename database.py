# database.py
"""
Módulo de gerenciamento do banco de dados SQLite.
Corrigido para suportar métricas de QoS (TTL, Latência, Perda) e Links.
"""

import sqlite3
from datetime import datetime

DB_FILE = 'network_discovery.db'

def _get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_db():
    """Cria as tabelas do banco de dados se elas não existirem."""
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    # 1. Tabela de Scans
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scans (
            scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL
        )
    ''')
    
    # 2. Tabela de Dispositivos (Definição Única e Completa)
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
            ttl INTEGER,           -- NOVO
            avg_latency REAL,      -- NOVO
            packet_loss REAL,      -- NOVO
            FOREIGN KEY (scan_id) REFERENCES scans (scan_id)
        )
    ''')

    # 3. Tabela de Links (Grafo)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS links (
            link_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            src_mac TEXT NOT NULL,
            dst_mac TEXT NOT NULL,
            type TEXT DEFAULT 'ethernet',
            FOREIGN KEY (scan_id) REFERENCES scans (scan_id)
        )
    ''')

    # 4. Tabela de Histórico de MACs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS known_devices (
            mac TEXT PRIMARY KEY,
            first_seen DATETIME NOT NULL
        )
    ''')
    
    # Commit e Close apenas no final de TUDO
    conn.commit()
    conn.close()
    print("(Database: Banco de dados inicializado com sucesso.)")

def salvar_resultado_scan(devices, links=None):
    """
    Salva o resultado completo de um novo scan no banco de dados.
    """
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now()
    cursor.execute('INSERT INTO scans (timestamp) VALUES (?)', (now,))
    scan_id = cursor.lastrowid
    
    devices_to_insert = []
    known_devices_to_check = []
    
    for dev in devices:
        ports_str = ",".join(map(str, dev.get('open_ports', [])))
        
        # Correção da Tupla: Fechamento de parênteses ajustado
        devices_to_insert.append((
            scan_id, 
            dev.get('ip'), 
            dev.get('mac'), 
            dev.get('status'), 
            dev.get('snmp_name'), 
            dev.get('producer'), 
            dev.get('role'),
            ports_str, 
            dev.get('ttl'),          
            dev.get('avg_latency'),  
            dev.get('packet_loss')
        ))
        
        if dev.get('mac'):
            known_devices_to_check.append((dev.get('mac'), now))

    if devices_to_insert:
        cursor.executemany(
            '''INSERT INTO devices (
                scan_id, ip, mac, status, snmp_name, producer, role, open_ports, 
                ttl, avg_latency, packet_loss
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            devices_to_insert
        )

    if known_devices_to_check:
        cursor.executemany(
            'INSERT OR IGNORE INTO known_devices (mac, first_seen) VALUES (?, ?)',
            known_devices_to_check
        )
    
    if links:
        links_to_insert = []
        for link in links:
            links_to_insert.append((
                scan_id, 
                link['src'], 
                link['dst'], 
                link.get('type', 'ethernet')
            ))
        
        cursor.executemany(
            'INSERT INTO links (scan_id, src_mac, dst_mac, type) VALUES (?, ?, ?, ?)',
            links_to_insert
        )
        
    conn.commit()
    conn.close()
    return scan_id

# --- Mantenha as outras funções de leitura (get_scan_history, etc) iguais ---
def _get_latest_scan_id():
    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT scan_id FROM scans ORDER BY timestamp DESC LIMIT 1')
    result = cursor.fetchone()
    conn.close()
    return result['scan_id'] if result else None

def get_scan_history(limit=10):
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
    if scan_id is None:
        scan_id = _get_latest_scan_id()
        if scan_id is None:
            return []
            
    conn = _get_db_connection()
    cursor = conn.cursor()
    
    # Atenção: Se você quiser ler o TTL na CLI, adicione d.ttl aqui no SELECT
    query = """
        SELECT d.ip, d.mac, d.status, d.snmp_name, d.producer, d.role, d.open_ports, kd.first_seen,
               d.ttl, d.avg_latency, d.packet_loss
        FROM devices d
        LEFT JOIN known_devices kd ON d.mac = kd.mac
        WHERE d.scan_id = ?
        ORDER BY d.ip
    """
    cursor.execute(query, (scan_id,))
    rows = cursor.fetchall()
    conn.close()
    
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
    conn = _get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM devices WHERE scan_id > ?', (scan_id,))
    cursor.execute('DELETE FROM links WHERE scan_id > ?', (scan_id,)) # Limpar links também
    cursor.execute('DELETE FROM scans WHERE scan_id > ?', (scan_id,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count