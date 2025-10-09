# config.py

# --- Configurações do Banco de Dados ---
# Define o nome do arquivo para o banco de dados SQLite.
DB_NAME = "network_data.db"

# --- Configurações do Polling Adaptativo ---
# Define o intervalo de tempo (em segundos) para o scan quando a rede está estável.
POLLING_INTERVAL_STABLE = 600  # 10 minutos

# Define o intervalo de tempo (em segundos) para o scan após detectar uma mudança.
POLLING_INTERVAL_CHANGE = 60  # 1 minuto

# Define o tempo de espera inicial (em segundos) antes do primeiro scan.
INITIAL_DELAY = 5

# --- Configurações de Descoberta de Rede ---
# Define um valor padrão para o timeout de scans (ex: ping, port scan).
SCAN_TIMEOUT = 1

# --- Configurações da CLI ---
# Define o prompt que será exibido no shell interativo.
CLI_PROMPT = "(discovery-shell) "

# --- Configurações de Log (Opcional, mas recomendado) ---
# Define o nome do arquivo de log.
LOG_FILE = "discovery.log"

# Define o nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL).
LOG_LEVEL = "INFO"

# --- Configurações SNMP ---
# Versão: '2c' (padrão) ou '3' (SNMPv3). Por ora, 2c com community.
SNMP_VERSION = "2c"
# Community padrão (ambiente de laboratório). Em produção, melhor SNMPv3.
SNMP_COMMUNITY = "public"
# Timeout (seg) e tentativas para consultas SNMP básicas
SNMP_TIMEOUT = 3
SNMP_RETRIES = 0
# Porta SNMP padrão
SNMP_PORT = 161